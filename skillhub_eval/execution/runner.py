"""Local CLI agent spawn + stream-json completion detection."""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

from skillhub_eval.core.schemas.report import RunOutcome
from skillhub_eval.execution.stream_parser import parse_stream_events


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Kill proc and all of its descendants.

    On Windows, `proc.kill()` only terminates the immediate child. Local agent
    CLIs resolved to a `.cmd`/`.bat` wrapper (e.g. cursor-agent.CMD) actually
    run as `cmd.exe /c <wrapper> ...`, which in turn spawns the real `node.exe`
    process as a grandchild. Killing just the `cmd.exe` wrapper leaves that
    grandchild running as an orphan indefinitely — confirmed on a real machine
    2026-07-02: two orphaned cursor-agent node.exe processes kept running (with
    their own further child processes) for 50+ minutes, well past their
    configured per-case timeout, until manually killed with `taskkill /T /F`.
    """
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                timeout=5,
            )
            return
        except (OSError, subprocess.SubprocessError):
            pass
    proc.kill()


@runtime_checkable
class AgentAdapter(Protocol):
    agent_id: str

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]: ...

    def detect(self) -> bool: ...

    def parse_stream(self, lines: list[str]): ...


@dataclass
class _FakeProcess:
    returncode: int
    stdout_lines: list[str] = field(default_factory=list)
    stderr_text: str = ""

    def communicate(self, input: str | None = None, timeout: float | None = None):
        return ("".join(self.stdout_lines), self.stderr_text)

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode


SpawnFn = Callable[..., subprocess.Popen | _FakeProcess]


class LocalAgentRunner:
    """Spawn a local agent, feed prompt via stdin, parse stream-json stdout."""

    def __init__(self, spawn_fn: SpawnFn | None = None):
        self._spawn = spawn_fn or subprocess.Popen

    def run(
        self,
        adapter: AgentAdapter,
        prompt: str,
        *,
        cwd: str,
        timeout_s: float = 300.0,
        hardened: bool = False,
    ) -> RunOutcome:
        args = list(adapter.build_args(cwd=cwd, hardened=hardened))
        stdin_prompt = prompt
        if getattr(adapter, "prompt_via_stdin", True) is False and stdin_prompt:
            args.append(stdin_prompt)
            stdin_prompt = ""
        proc = self._spawn(
            args,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stderr_text = ""
        if getattr(proc, "stdout", None) is None:
            stdout, stderr = proc.communicate(input=stdin_prompt or None, timeout=timeout_s)
            stderr_text = stderr or ""
            lines = stdout.splitlines() if stdout else []
            exit_code = proc.returncode if proc.returncode is not None else proc.wait()
        else:
            lines, exit_code = self._stream_until_complete(proc, stdin_prompt, timeout_s)
            if proc.stderr is not None:
                try:
                    stderr_text = proc.stderr.read() or ""
                except OSError:
                    stderr_text = ""
        parsed = adapter.parse_stream(lines)
        if not stderr_text and getattr(parsed, "is_error", False):
            stderr_text = parsed.error_text or ""
        return RunOutcome(
            exit_code=exit_code or 0,
            parsed_stream=parsed,
            duration_ms=parsed.duration_ms,
            stderr_text=stderr_text or None,
        )

    def _stream_until_complete(
        self,
        proc: subprocess.Popen,
        prompt: str,
        timeout_s: float,
    ) -> tuple[list[str], int]:
        if proc.stdin:
            def _write_stdin() -> None:
                try:
                    proc.stdin.write(prompt)
                    proc.stdin.close()
                except (BrokenPipeError, OSError, ValueError):
                    pass

            # Written from a background thread — not the main thread — so a
            # write that blocks (e.g. the wrapper process hasn't started
            # reading stdin yet) can never delay the deadline loop below from
            # starting. Previously this was a blocking call made before the
            # loop existed, so a stuck write bypassed timeout_s entirely.
            threading.Thread(target=_write_stdin, daemon=True).start()

        lines: list[str] = []
        line_queue: queue.Queue[str | None] = queue.Queue()

        def _reader() -> None:
            try:
                assert proc.stdout is not None
                for raw in proc.stdout:
                    line_queue.put(raw.rstrip("\n\r"))
            finally:
                line_queue.put(None)

        threading.Thread(target=_reader, daemon=True).start()
        deadline = time.monotonic() + timeout_s
        stream_complete = False

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                line = line_queue.get(timeout=min(1.0, remaining))
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            if line is None:
                break
            lines.append(line)
            if parse_stream_events(lines).is_complete:
                stream_complete = True
                break

        if proc.poll() is None:
            _kill_process_tree(proc)
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

        while True:
            try:
                extra = line_queue.get_nowait()
            except queue.Empty:
                break
            if extra is None:
                break
            if not stream_complete:
                lines.append(extra)

        exit_code = proc.returncode if proc.returncode is not None else proc.wait()
        return lines, exit_code

    def is_run_complete(self, outcome: RunOutcome) -> bool:
        """Stream-json completion is authoritative (Codex may be killed after turn.completed)."""
        parsed = outcome.parsed_stream
        return parsed is not None and parsed.is_complete and not parsed.is_error

