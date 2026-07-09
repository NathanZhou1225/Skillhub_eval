from skillhub_eval.core.schemas.report import ParsedStream
from skillhub_eval.execution.adapters.cursor_agent import _normalize_tool_call_event
from skillhub_eval.execution.stream_abort import (
    PreflightStreamAbortPolicy,
    preflight_abort_reason,
    tool_call_failed,
)


def test_tool_call_failed_honors_is_error_and_exit_code():
    assert tool_call_failed({"is_error": True})
    assert tool_call_failed({"exit_code": 1})
    assert tool_call_failed({"exitCode": 2})
    assert not tool_call_failed({"exit_code": 0})
    assert not tool_call_failed({})


def test_preflight_abort_on_total_tool_budget():
    policy = PreflightStreamAbortPolicy(max_total_tools=3, max_failed_tools=99, max_consecutive_failures=99)
    parsed = ParsedStream(
        tool_results=[
            {"exit_code": 0},
            {"exit_code": 0},
            {"exit_code": 0},
        ]
    )
    assert preflight_abort_reason(parsed, policy) == "runtime_preflight_tool_budget_exceeded"


def test_preflight_abort_on_failed_tool_count():
    policy = PreflightStreamAbortPolicy(max_total_tools=99, max_failed_tools=2, max_consecutive_failures=99)
    parsed = ParsedStream(
        tool_results=[
            {"exit_code": 0},
            {"exit_code": 1},
            {"exit_code": 1},
        ]
    )
    assert preflight_abort_reason(parsed, policy) == "runtime_tool_failures_exceeded"


def test_preflight_abort_on_consecutive_failures():
    policy = PreflightStreamAbortPolicy(max_total_tools=99, max_failed_tools=99, max_consecutive_failures=2)
    parsed = ParsedStream(
        tool_results=[
            {"exit_code": 1},
            {"exit_code": 0},
            {"exit_code": 1},
            {"exit_code": 1},
        ]
    )
    assert preflight_abort_reason(parsed, policy) == "runtime_tool_failures_exceeded"


def test_cursor_tool_call_marks_nonzero_exit_as_error():
    event = {
        "subtype": "completed",
        "tool_call": {
            "shellToolCall": {
                "args": {"command": "python scripts/run.py"},
                "result": {"success": {"exitCode": 1, "stdout": "", "stderr": "boom"}},
            }
        },
    }
    normalized = _normalize_tool_call_event(event)
    assert normalized is not None
    assert normalized["is_error"] is True
    assert normalized["exit_code"] == 1
