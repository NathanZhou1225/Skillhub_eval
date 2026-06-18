from unittest.mock import patch

from skillhub_eval.execution.adapters.codex import CodexAdapter


def test_codex_build_args_hardened_disables_network():
    adapter = CodexAdapter()
    args = adapter.build_args(cwd="/tmp/work", hardened=True)
    assert args[0] == "codex"
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
