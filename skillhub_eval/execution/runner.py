"""Local CLI agent spawn + stream-json completion detection."""

from __future__ import annotations

import subprocess
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
        )
        stdout, _stderr = proc.communicate(input=prompt, timeout=timeout_s)
        exit_code = proc.returncode if getattr(proc, "returncode", None) is not None else proc.wait()
        lines = stdout.splitlines() if stdout else []
        parsed = parse_stream_events(lines)
        return RunOutcome(
            exit_code=exit_code or 0,
            parsed_stream=parsed,
            duration_ms=parsed.duration_ms,
        )

    def is_run_complete(self, outcome: RunOutcome) -> bool:
        """Two-layer completion: process exit + stream result event."""
        if outcome.exit_code != 0:
            return False
        parsed = outcome.parsed_stream
        return parsed is not None and parsed.is_complete
