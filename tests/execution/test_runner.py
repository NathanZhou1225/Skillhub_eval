import json
import threading
import time
from unittest.mock import patch

import pytest

from skillhub_eval.execution.runner import LocalAgentRunner, _FakeProcess, _kill_process_tree
from skillhub_eval.execution.stream_parser import (
    collect_actual_output,
    extract_fenced_json,
    parse_stream_events,
)


class _StubAdapter:
    agent_id = "stub"

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        return ["stub-agent", "--print"]

    def detect(self) -> bool:
        return True

    def parse_stream(self, lines: list[str]):
        return parse_stream_events(lines)


class _CustomParserAdapter(_StubAdapter):
    def parse_stream(self, lines: list[str]):
        from skillhub_eval.core.schemas.report import ParsedStream

        return ParsedStream(final_text="custom", is_complete=True, duration_ms=7)


def test_runner_completes_on_exit_and_result_event():
    lines = [
        json.dumps({"type": "text", "delta": "hello"}),
        json.dumps({"type": "result", "usage": {"input_tokens": 1}, "duration_ms": 42}),
    ]

    def fake_spawn(args, **kwargs):
        return _FakeProcess(returncode=0, stdout_lines=[ln + "\n" for ln in lines])

    runner = LocalAgentRunner(spawn_fn=fake_spawn)
    outcome = runner.run(_StubAdapter(), "run skill", cwd="/tmp/work")
    assert runner.is_run_complete(outcome)
    assert outcome.parsed_stream is not None
    assert outcome.parsed_stream.final_text == "hello"
    assert outcome.parsed_stream.usage == {"input_tokens": 1}
    assert outcome.duration_ms == 42


def test_runner_uses_adapter_specific_parser():
    def fake_spawn(args, **kwargs):
        return _FakeProcess(returncode=0, stdout_lines=["not json\n"])

    runner = LocalAgentRunner(spawn_fn=fake_spawn)
    outcome = runner.run(_CustomParserAdapter(), "run skill", cwd="/tmp/work")

    assert runner.is_run_complete(outcome)
    assert outcome.parsed_stream is not None
    assert outcome.parsed_stream.final_text == "custom"
    assert outcome.duration_ms == 7


def test_runner_preserves_stderr_on_communicate_path():
    def fake_spawn(args, **kwargs):
        return _FakeProcess(
            returncode=0,
            stdout_lines=[json.dumps({"type": "result", "duration_ms": 1}) + "\n"],
            stderr_text="429 rate limit",
        )

    runner = LocalAgentRunner(spawn_fn=fake_spawn)
    outcome = runner.run(_StubAdapter(), "run skill", cwd="/tmp/work")

    assert outcome.stderr_text == "429 rate limit"
    assert runner.is_run_complete(outcome)


def test_runner_incomplete_without_result_event():
    lines = [json.dumps({"type": "text", "delta": "partial"})]

    def fake_spawn(args, **kwargs):
        return _FakeProcess(returncode=0, stdout_lines=[ln + "\n" for ln in lines])

    runner = LocalAgentRunner(spawn_fn=fake_spawn)
    outcome = runner.run(_StubAdapter(), "run skill", cwd="/tmp/work")
    assert not runner.is_run_complete(outcome)


def test_runner_does_not_complete_on_stream_error_result():
    lines = [
        json.dumps({
            "type": "result",
            "subtype": "error_during_execution",
            "is_error": True,
            "error": "Models is required",
        })
    ]

    def fake_spawn(args, **kwargs):
        return _FakeProcess(returncode=1, stdout_lines=[ln + "\n" for ln in lines])

    runner = LocalAgentRunner(spawn_fn=fake_spawn)
    outcome = runner.run(_StubAdapter(), "run skill", cwd="/tmp/work")

    assert not runner.is_run_complete(outcome)
    assert outcome.stderr_text == "Models is required"


def test_parse_stream_events_collects_tool_result():
    lines = [
        json.dumps({"type": "tool_result", "stdout": "ok", "exit_code": 0}),
        json.dumps({"type": "result", "duration_ms": 10}),
    ]
    parsed = parse_stream_events(lines)
    assert len(parsed.tool_results) == 1
    assert parsed.is_complete


def test_extract_fenced_json_from_final_text():
    text = 'done\n```json\n{"score": 99}\n```'
    assert extract_fenced_json(text) == {"score": 99}


def test_collect_actual_output_prefers_fenced_json():
    from skillhub_eval.core.schemas.report import ParsedStream

    parsed = ParsedStream(final_text='```json\n{"a": 1}\n```', is_complete=True)
    assert collect_actual_output(parsed) == {"a": 1}


def test_collect_actual_output_fallback_to_text_and_tools():
    from skillhub_eval.core.schemas.report import ParsedStream

    parsed = ParsedStream(
        final_text="plain",
        tool_results=[{"stdout": "x"}],
        is_complete=True,
    )
    out = collect_actual_output(parsed, cwd_artifacts=[{"path": "out.json"}])
    assert out["text"] == "plain"
    assert out["tool_results"] == [{"stdout": "x"}]
    assert out["artifacts"] == [{"path": "out.json"}]


class _BlockingStdin:
    """stdin.write() that blocks forever, simulating a wrapper process that
    never starts draining its own stdin pipe."""

    def write(self, data):
        threading.Event().wait()
        return len(data)

    def close(self):
        pass


class _BlockingStdout:
    """stdout iterator that never yields a line and never raises StopIteration."""

    def __iter__(self):
        return self

    def __next__(self):
        threading.Event().wait()
        raise StopIteration


class _HangingProcess:
    """Popen-like fake whose stdin write and stdout read both block forever."""

    def __init__(self):
        self.stdin = _BlockingStdin()
        self.stdout = _BlockingStdout()
        self.stderr = None
        self.pid = 999999
        self.returncode = None

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode if self.returncode is not None else 0


def test_stream_until_complete_enforces_deadline_even_if_stdin_write_blocks():
    """Regression (2026-07-02 real-machine finding): stdin.write() used to run
    synchronously on the main thread *before* the deadline loop even started,
    so a write that blocks (e.g. the wrapper process hasn't started reading
    stdin yet) bypassed timeout_s entirely — two real cursor-agent processes
    hung for 50+ minutes, far past their configured per-case timeout, before
    this fix moved the write onto a background thread."""
    proc = _HangingProcess()
    runner = LocalAgentRunner()
    with patch("skillhub_eval.execution.runner._kill_process_tree", side_effect=lambda p: p.kill()) as mock_kill:
        started = time.monotonic()
        lines, exit_code = runner._stream_until_complete(proc, "prompt", timeout_s=0.2)
        elapsed = time.monotonic() - started
    assert elapsed < 5.0
    mock_kill.assert_called_once_with(proc)
    assert lines == []


def test_kill_process_tree_uses_taskkill_on_windows():
    proc = _HangingProcess()
    with patch("skillhub_eval.execution.runner.sys.platform", "win32"), \
         patch("skillhub_eval.execution.runner.subprocess.run") as mock_run:
        _kill_process_tree(proc)
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args == ["taskkill", "/PID", "999999", "/T", "/F"]
    assert proc.returncode is None  # proc.kill() itself was not called


def test_kill_process_tree_falls_back_to_proc_kill_off_windows():
    proc = _HangingProcess()
    with patch("skillhub_eval.execution.runner.sys.platform", "linux"):
        _kill_process_tree(proc)
    assert proc.returncode == -9
