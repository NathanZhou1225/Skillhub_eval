from skillhub_eval.execution.events import AgentEvent, AgentEventType, ToolResultPayload


def test_agent_event_type_includes_required_normalized_events():
    values = {event_type.value for event_type in AgentEventType}

    assert {
        "text_delta",
        "thinking",
        "tool_call",
        "tool_result",
        "file_write",
        "usage",
        "done",
        "error",
        "raw_unsupported",
    } <= values


def test_agent_event_accepts_enum_or_string_type_with_payload():
    event = AgentEvent(type="text_delta", payload={"text": "hello"})

    assert event.type == AgentEventType.TEXT_DELTA
    assert event.payload == {"text": "hello"}


def test_tool_result_payload_has_adapter_friendly_defaults():
    payload = ToolResultPayload(tool="bash", command="python scripts/run.py")

    assert payload.tool == "bash"
    assert payload.command == "python scripts/run.py"
    assert payload.stdout == ""
    assert payload.stderr == ""
    assert payload.exit_code is None
    assert payload.is_error is False


def test_tool_result_payload_serializes_to_plain_dict():
    payload = ToolResultPayload(
        tool="bash",
        command="python scripts/run.py",
        stdout='{"ok": true}',
        stderr="",
        exit_code=0,
        is_error=False,
    )

    assert payload.to_dict() == {
        "tool": "bash",
        "command": "python scripts/run.py",
        "stdout": '{"ok": true}',
        "stderr": "",
        "exit_code": 0,
        "is_error": False,
    }
