import json

import pytest

from skillhub_eval.execution.runner import LocalAgentRunner, _FakeProcess
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


def test_runner_incomplete_without_result_event():
    lines = [json.dumps({"type": "text", "delta": "partial"})]

    def fake_spawn(args, **kwargs):
        return _FakeProcess(returncode=0, stdout_lines=[ln + "\n" for ln in lines])

    runner = LocalAgentRunner(spawn_fn=fake_spawn)
    outcome = runner.run(_StubAdapter(), "run skill", cwd="/tmp/work")
    assert not runner.is_run_complete(outcome)


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
