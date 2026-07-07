import json
from unittest.mock import patch

from skillhub_eval.execution.adapters.claude import ClaudeAdapter
from skillhub_eval.execution.events import AgentEventType
from skillhub_eval.execution.exec_result_builder import parsed_stream_from_events


def test_claude_build_args_matches_open_design_shape():
    adapter = ClaudeAdapter(model="claude-sonnet-4-6")
    args = adapter.build_args(cwd="/tmp/work")
    assert args[0] == "claude"
    assert "-p" in args
    assert "--input-format" in args
    assert "stream-json" in args
    assert "--output-format" in args
    assert "--permission-mode" in args
    assert "bypassPermissions" in args
    idx = args.index("--model")
    assert args[idx + 1] == "claude-sonnet-4-6"


def test_claude_build_args_add_dir():
    adapter = ClaudeAdapter(extra_allowed_dirs=["/extra"])
    args = adapter.build_args()
    assert "--add-dir" in args
    assert "/extra" in args


@patch("skillhub_eval.execution.adapters.claude.find_cli_binary", return_value="/usr/bin/claude")
def test_claude_detect_when_on_path(mock_find):
    assert ClaudeAdapter().detect() is True
    mock_find.assert_called_with("claude")


@patch("skillhub_eval.execution.adapters.claude.find_cli_binary", return_value=None)
def test_claude_detect_when_missing(mock_find):
    assert ClaudeAdapter().detect() is False


def test_claude_parse_stream_delegates_to_generic_parser():
    adapter = ClaudeAdapter()
    lines = [
        json.dumps({"type": "result", "duration_ms": 5}),
    ]
    parsed = adapter.parse_stream(lines)
    assert parsed.is_complete
    assert parsed.duration_ms == 5


def test_claude_normalize_events_matches_parse_stream():
    adapter = ClaudeAdapter()
    lines = [
        json.dumps({"type": "text", "text": "hello "}),
        json.dumps({"type": "result", "result": "hello done", "duration_ms": 5, "usage": {"input_tokens": 1}}),
    ]

    events = adapter.normalize_events(lines)
    parsed = adapter.parse_stream(lines)
    from_events = parsed_stream_from_events(events)

    assert any(event.type == AgentEventType.TEXT_DELTA for event in events)
    assert any(event.type == AgentEventType.DONE for event in events)
    assert from_events == parsed


def test_claude_normalize_events_preserves_generic_tool_result_dict():
    adapter = ClaudeAdapter()
    lines = [
        json.dumps({"type": "tool_result"}),
        json.dumps({"type": "result", "duration_ms": 5}),
    ]

    parsed = adapter.parse_stream(lines)

    assert parsed.tool_results == [{"type": "tool_result"}]
    assert parsed.is_complete


def test_claude_normalize_events_preserves_error_duration():
    adapter = ClaudeAdapter()
    lines = [
        json.dumps({"type": "result", "is_error": True, "error": "boom", "duration_ms": 5}),
    ]

    parsed = adapter.parse_stream(lines)

    assert parsed.is_error
    assert not parsed.is_complete
    assert parsed.error_text == "boom"
    assert parsed.duration_ms == 5


def test_claude_normalize_events_preserves_generic_duplicate_result_text():
    adapter = ClaudeAdapter()
    lines = [
        json.dumps({"type": "text", "text": "hello"}),
        json.dumps({"type": "result", "result": "hello"}),
    ]

    parsed = adapter.parse_stream(lines)

    assert parsed.final_text == "hellohello"
