import json

from skillhub_eval.execution.adapters.cursor_agent import CursorAgentAdapter, _emit_cursor_text_delta


def test_cursor_build_args_open_design_shape():
    args = CursorAgentAdapter(model="gpt-5").build_args(cwd="/ws")
    assert args[0] == "cursor-agent"
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
