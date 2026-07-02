import json
import os
from unittest.mock import patch

from skillhub_eval.execution.adapters.codex import CodexAdapter
from skillhub_eval.execution.evidence import verify_entrypoint_evidence


def test_codex_build_args_hardened_disables_network():
    adapter = CodexAdapter()
    args = adapter.build_args(cwd="/tmp/work", hardened=True)
    # args[0] is the resolved binary; on machines with codex installed it is a
    # full path, so compare the basename without extension.
    assert os.path.basename(args[0]).split(".")[0] == "codex"
    assert "workspace-write" in args
    assert "sandbox_workspace_write.network_access=false" in args
    assert "-C" in args
    assert args[args.index("-C") + 1] == "/tmp/work"


def test_codex_build_args_default_allows_network():
    args = CodexAdapter().build_args(cwd="/tmp/work", hardened=False)
    assert "sandbox_workspace_write.network_access=true" in args


@patch("skillhub_eval.execution.adapters.codex.find_cli_binary", return_value="/bin/codex")
def test_codex_detect(mock_find):
    assert CodexAdapter().detect() is True
    assert CodexAdapter().resolved_bin() == "/bin/codex"


def test_codex_parse_stream_captures_command_execution_as_evidence():
    """Real `codex exec --json` reports every shell command as
    `item.completed` / `command_execution` items (command, aggregated_output,
    exit_code, status) — the generic stream parser only lifted agent_message
    text out of item.completed, so verify_entrypoint_evidence() always saw an
    empty tool_results list even though the entrypoint genuinely ran
    (2026-07-02 real-machine finding, same class of gap as the Cursor Agent
    D14 / Trae D19 fixes)."""
    adapter = CodexAdapter()
    lines = [
        json.dumps({"type": "thread.started", "thread_id": "t1"}),
        json.dumps({"type": "turn.started"}),
        json.dumps({
            "type": "item.completed",
            "item": {
                "id": "item_1",
                "type": "command_execution",
                "command": "python scripts/run.py",
                "aggregated_output": '{"status": "success", "ok": true}\n',
                "exit_code": 0,
                "status": "completed",
            },
        }),
        json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 1}}),
    ]
    parsed = adapter.parse_stream(lines)
    assert len(parsed.tool_results) == 1
    assert verify_entrypoint_evidence(parsed.tool_results, "scripts/run.py") is True


def test_codex_parse_stream_failed_command_execution_is_not_evidence():
    adapter = CodexAdapter()
    lines = [
        json.dumps({
            "type": "item.completed",
            "item": {
                "id": "item_1",
                "type": "command_execution",
                "command": "python scripts/run.py",
                "aggregated_output": "Traceback...\n",
                "exit_code": 1,
                "status": "failed",
            },
        }),
        json.dumps({"type": "turn.completed"}),
    ]
    parsed = adapter.parse_stream(lines)
    assert verify_entrypoint_evidence(parsed.tool_results, "scripts/run.py") is False
