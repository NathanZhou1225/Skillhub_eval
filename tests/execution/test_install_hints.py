from skillhub_eval.execution.install_hints import get_install_hint


def test_known_agent_has_install_command_and_docs():
    hint = get_install_hint("codex")
    assert hint and hint["install_command"] and hint["docs_url"].startswith("http")


def test_unknown_agent_returns_none():
    assert get_install_hint("does-not-exist") is None
