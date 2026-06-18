"""Local CLI agent spawn + stream-json completion detection."""

from __future__ import annotations

import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

from skillhub_eval.core.schemas.report import RunOutcome
from skillhub_eval.execution.stream_parser import parse_stream_events


@runtime_checkable
class AgentAdapter(Protocol):
    agent_id: str

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]: ...

    def detect(self) -> bool: ...


@dataclass
class _FakeProcess:
    returncode: int
    stdout_lines: list[str] = field(default_factory=list)

    def communicate(self, input: str | None = None, timeout: float | None = None):
        return ("".join(self.stdout_lines), "")

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
        args = adapter.build_args(cwd=cwd, hardened=hardened)
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
        if getattr(proc, "stdout", None) is None:
            stdout, _stderr = proc.communicate(input=prompt, timeout=timeout_s)
            lines = stdout.splitlines() if stdout else []
            exit_code = proc.returncode if proc.returncode is not None else proc.wait()
        else:
            lines, exit_code = self._stream_until_complete(proc, prompt, timeout_s)
        parsed = parse_stream_events(lines)
        return RunOutcome(
            exit_code=exit_code or 0,
            parsed_stream=parsed,
            duration_ms=parsed.duration_ms,
        )

    def _stream_until_complete(
        self,
        proc: subprocess.Popen,
        prompt: str,
        timeout_s: float,
    ) -> tuple[list[str], int]:
        if proc.stdin:
            proc.stdin.write(prompt)
            proc.stdin.close()

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
            proc.kill()
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
        return parsed is not None and parsed.is_complete

