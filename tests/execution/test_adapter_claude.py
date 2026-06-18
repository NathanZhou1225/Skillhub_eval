import json
from unittest.mock import patch

from skillhub_eval.execution.adapters.claude import ClaudeAdapter


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
