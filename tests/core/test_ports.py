from typing import get_type_hints

import pytest

from skillhub_eval.core.ports import ExecutionSource
from skillhub_eval.core.schemas.report import ExecResult, ParsedStream, RunOutcome


def test_exec_result_defaults():
    r = ExecResult()
    assert r.actual_output is None
    assert r.source == "sample_io"
    assert r.confidence == "high"
    assert r.transcript_ref is None
    assert r.usage is None
    assert r.status == "ok"
    assert r.level == "level_1"


def test_exec_result_accepts_local_agent_fields():
    r = ExecResult(
        actual_output={"score": 1},
        source="local_agent",
        confidence="low",
        transcript_ref="/tmp/t.jsonl",
        usage={"input_tokens": 10},
        status="incomplete",
        level="level_2",
    )
    assert r.source == "local_agent"
    assert r.level == "level_2"
    assert r.actual_output == {"score": 1}


def test_run_outcome_defaults():
    o = RunOutcome()
    assert o.exit_code == 0
    assert o.parsed_stream is None
    assert o.transcript_ref is None
    assert o.duration_ms is None


def test_parsed_stream_defaults():
    p = ParsedStream()
    assert p.final_text == ""
    assert p.tool_results == []
    assert p.usage is None
    assert p.duration_ms is None
    assert p.is_complete is False


def test_execution_source_is_runtime_checkable_protocol():
    from skillhub_eval.core.sample_io_source import SampleIoSource

    src = SampleIoSource()
    assert isinstance(src, ExecutionSource)
    hints = get_type_hints(ExecutionSource.get_actual_output)
    assert "bundle_path" in hints
    assert "case_id" in hints
