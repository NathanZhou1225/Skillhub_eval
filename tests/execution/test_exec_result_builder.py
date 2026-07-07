from skillhub_eval.execution.events import AgentEvent, AgentEventType, ToolResultPayload
from skillhub_eval.execution.evidence import verify_entrypoint_evidence
from skillhub_eval.execution.exec_result_builder import parsed_stream_from_events


def test_parsed_stream_from_events_aggregates_text_deltas():
    parsed = parsed_stream_from_events(
        [
            AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": "hello"}),
            AgentEvent(type=AgentEventType.THINKING, payload={"text": "internal"}),
            AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"delta": " world"}),
        ]
    )

    assert parsed.final_text == "hello world"
    assert parsed.tool_results == []


def test_parsed_stream_from_events_converts_tool_result_payloads_to_dicts():
    parsed = parsed_stream_from_events(
        [
            AgentEvent(
                type=AgentEventType.TOOL_RESULT,
                payload=ToolResultPayload(
                    tool="bash",
                    command="python scripts/run.py",
                    stdout='{"status":"success"}',
                    stderr="",
                    exit_code=0,
                    is_error=False,
                ),
            )
        ]
    )

    assert parsed.tool_results == [
        {
            "tool": "bash",
            "command": "python scripts/run.py",
            "stdout": '{"status":"success"}',
            "stderr": "",
            "exit_code": 0,
            "is_error": False,
        }
    ]
    assert verify_entrypoint_evidence(parsed.tool_results, "scripts/run.py")


def test_parsed_stream_from_events_appends_terminal_done_result_text():
    parsed = parsed_stream_from_events(
        [
            AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": "prefix "}),
            AgentEvent(type=AgentEventType.DONE, payload={"result": "terminal"}),
        ]
    )

    assert parsed.final_text == "prefix terminal"
    assert parsed.is_complete


def test_parsed_stream_from_events_preserves_duplicate_terminal_result_text():
    parsed = parsed_stream_from_events(
        [
            AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": "hello"}),
            AgentEvent(type=AgentEventType.DONE, payload={"result": "hello"}),
        ]
    )

    assert parsed.final_text == "hellohello"


def test_parsed_stream_from_events_appends_terminal_done_text_field():
    parsed = parsed_stream_from_events(
        [
            AgentEvent(type=AgentEventType.DONE, payload={"text": "terminal text"}),
        ]
    )

    assert parsed.final_text == "terminal text"


def test_parsed_stream_from_events_collects_usage_and_done_duration():
    parsed = parsed_stream_from_events(
        [
            AgentEvent(type=AgentEventType.USAGE, payload={"input_tokens": 12, "output_tokens": 3}),
            AgentEvent(type=AgentEventType.DONE, payload={"duration_ms": 456}),
        ]
    )

    assert parsed.usage == {"input_tokens": 12, "output_tokens": 3}
    assert parsed.duration_ms == 456
    assert parsed.is_complete
    assert not parsed.is_error


def test_parsed_stream_from_events_marks_error_and_keeps_error_text():
    parsed = parsed_stream_from_events(
        [
            AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": "partial"}),
            AgentEvent(type=AgentEventType.ERROR, payload={"message": "model failed"}),
        ]
    )

    assert parsed.final_text == "partial"
    assert parsed.is_error
    assert not parsed.is_complete
    assert parsed.error_text == "model failed"


def test_parsed_stream_from_events_error_after_done_takes_terminal_precedence():
    parsed = parsed_stream_from_events(
        [
            AgentEvent(type=AgentEventType.DONE, payload={"result": "partial"}),
            AgentEvent(type=AgentEventType.ERROR, payload={"message": "late failure"}),
        ]
    )

    assert parsed.final_text == "partial"
    assert parsed.is_error
    assert not parsed.is_complete
    assert parsed.error_text == "late failure"


def test_parsed_stream_from_events_ignores_unsupported_raw_event():
    parsed = parsed_stream_from_events(
        [
            AgentEvent(type=AgentEventType.RAW_UNSUPPORTED, payload={"raw": {"type": "unknown"}}),
            AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": "ok"}),
            AgentEvent(type=AgentEventType.DONE, payload={}),
        ]
    )

    assert parsed.final_text == "ok"
    assert parsed.is_complete
