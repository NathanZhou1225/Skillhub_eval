import json
import os

from skillhub_eval.execution.adapters.cursor_agent import CursorAgentAdapter, _emit_cursor_text_delta
from skillhub_eval.execution.events import AgentEventType
from skillhub_eval.execution.exec_result_builder import parsed_stream_from_events


def _assert_equivalent_to_event_builder(adapter: CursorAgentAdapter, lines: list[str]) -> None:
    parsed = adapter.parse_stream(lines)
    from_events = parsed_stream_from_events(adapter.normalize_events(lines))

    assert from_events.final_text == parsed.final_text
    assert from_events.tool_results == parsed.tool_results
    assert from_events.usage == parsed.usage
    assert from_events.duration_ms == parsed.duration_ms
    assert from_events.is_complete == parsed.is_complete
    assert from_events.is_error == parsed.is_error
    assert from_events.error_text == parsed.error_text


def test_cursor_build_args_open_design_shape():
    args = CursorAgentAdapter(model="gpt-5").build_args(cwd="/ws")
    # args[0] is the resolved binary; on machines with cursor-agent installed it
    # is a full path, so compare the basename without extension.
    assert os.path.basename(args[0]).split(".")[0] == "cursor-agent"
    assert "--print" in args
    assert "--output-format" in args
    assert "stream-json" in args
    assert "--force" in args
    assert "--trust" in args
    assert "--workspace" in args
    assert args[args.index("--workspace") + 1] == "/ws"


def test_cursor_text_delta_dedup():
    state: dict = {}
    assert _emit_cursor_text_delta("hello", state) == "hello"
    assert _emit_cursor_text_delta("hello world", state) == " world"
    assert _emit_cursor_text_delta("hello world", state) == ""


def test_cursor_parse_stream_partial_output():
    adapter = CursorAgentAdapter()
    lines = [
        json.dumps({"type": "text", "text": "hel"}),
        json.dumps({"type": "text", "text": "hello"}),
        json.dumps({"type": "result", "duration_ms": 9}),
    ]
    parsed = adapter.parse_stream(lines)
    assert parsed.final_text == "hello"
    assert parsed.is_complete
    assert parsed.duration_ms == 9


def test_cursor_parse_stream_final_text_from_result_event():
    """Real cursor-agent puts the complete answer in the terminal `result` event's
    `result` field, not in the per-token `assistant` deltas (2026-07-02 real-machine
    finding: assistant deltas nest text under message.content[], which this adapter
    does not parse, so `result` must be the source of truth for final_text)."""
    adapter = CursorAgentAdapter()
    lines = [
        json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "I'll run it"}]}}),
        json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "已执行 scripts/run.py。\n```json\n{\"status\": \"success\", \"ok\": true}\n```",
            "duration_ms": 42,
        }),
    ]
    parsed = adapter.parse_stream(lines)
    assert parsed.is_complete
    assert "```json" in parsed.final_text
    assert '"status": "success"' in parsed.final_text


def test_cursor_parse_stream_captures_shell_tool_call_as_evidence():
    """Real cursor-agent reports tool execution as `type: tool_call` with a nested
    shellToolCall payload, never the flat `tool_result` type this adapter used to
    look for exclusively — so verify_entrypoint_evidence() always saw an empty list
    even when the entrypoint genuinely ran (2026-07-02 real-machine finding)."""
    from skillhub_eval.execution.evidence import verify_entrypoint_evidence

    adapter = CursorAgentAdapter()
    lines = [
        json.dumps({
            "type": "tool_call",
            "subtype": "started",
            "call_id": "tool_1",
            "tool_call": {"shellToolCall": {"args": {"command": "python scripts/run.py"}}},
        }),
        json.dumps({
            "type": "tool_call",
            "subtype": "completed",
            "call_id": "tool_1",
            "tool_call": {
                "shellToolCall": {
                    "args": {"command": "python scripts/run.py"},
                    "result": {"success": {"exitCode": 0, "stdout": '{"status": "success", "ok": true}\n', "stderr": ""}},
                }
            },
        }),
        json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "done"}),
    ]
    parsed = adapter.parse_stream(lines)
    assert len(parsed.tool_results) == 1
    assert verify_entrypoint_evidence(parsed.tool_results, "scripts/run.py") is True


def test_cursor_parse_stream_failed_shell_tool_call_is_not_evidence():
    from skillhub_eval.execution.evidence import verify_entrypoint_evidence

    adapter = CursorAgentAdapter()
    lines = [
        json.dumps({
            "type": "tool_call",
            "subtype": "completed",
            "call_id": "tool_1",
            "tool_call": {
                "shellToolCall": {
                    "args": {"command": "python scripts/run.py"},
                    "result": {"success": {"exitCode": 1, "stdout": "", "stderr": "boom"}},
                }
            },
        }),
        json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "done"}),
    ]
    parsed = adapter.parse_stream(lines)
    assert verify_entrypoint_evidence(parsed.tool_results, "scripts/run.py") is False


def test_cursor_agent_normalize_events_from_real_tool_call_shape():
    lines = [
        json.dumps({
            "type": "tool_call",
            "subtype": "completed",
            "tool_call": {
                "shellToolCall": {
                    "args": {"command": "python scripts/run.py"},
                    "result": {"success": {"exitCode": 0, "stdout": '{"ok": true}\n', "stderr": ""}},
                }
            },
        }),
        json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": '```json\n{"ok": true}\n```',
            "usage": {"input_tokens": 1},
            "duration_ms": 42,
        }),
    ]

    events = CursorAgentAdapter().normalize_events(lines)

    assert any(
        e.type == AgentEventType.TOOL_RESULT and e.payload.command == "python scripts/run.py"
        for e in events
    )
    assert any(e.type == AgentEventType.DONE for e in events)


def test_cursor_agent_normalize_events_matches_parse_stream_result_text_source_of_truth():
    adapter = CursorAgentAdapter()
    lines = [
        json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "partial"}]}}),
        json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "terminal result",
            "usage": {"input_tokens": 2},
            "duration_ms": 8,
        }),
    ]

    _assert_equivalent_to_event_builder(adapter, lines)


def test_cursor_agent_normalize_events_matches_parse_stream_partial_dedup_without_result_text():
    adapter = CursorAgentAdapter()
    lines = [
        json.dumps({"type": "text", "text": "hel"}),
        json.dumps({"type": "text", "text": "hello"}),
        json.dumps({"type": "result", "duration_ms": 9}),
    ]

    _assert_equivalent_to_event_builder(adapter, lines)
