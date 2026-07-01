from unittest.mock import patch

from skillhub_eval.execution.agent_registry import get_agent_def
from skillhub_eval.execution import models


def test_fallback_when_no_probe():
    disc = models.discover_models(get_agent_def("codex"))  # codex has no model_probe
    assert "default" in [m["id"] for m in disc.models]
    assert disc.models_source == "fallback"


def test_trae_live_probe_used():
    out = "GLM-5.2\nDeepSeek-V4-Pro\n"
    with patch.object(models, "_run_probe", return_value=out):
        disc = models.discover_models(get_agent_def("trae"))
    ids = [m["id"] for m in disc.models]
    assert "GLM-5.2" in ids and "DeepSeek-V4-Pro" in ids
    assert disc.models_source == "live"


def test_trae_probe_failure_falls_back():
    with patch.object(models, "_run_probe", return_value=None):
        disc = models.discover_models(get_agent_def("trae"))
    assert disc.models_source == "fallback"


def test_stored_custom_model_preserved():
    disc = models.discover_models(get_agent_def("codex"), stored_model="my/gpt-x")
    custom = next(m for m in disc.models if m["id"] == "my/gpt-x")
    assert custom["source"] in ("custom", "stale")


def test_cursor_list_models_format_parsed():
    out = """Available models

auto - Auto (current)
gpt-5.2 - GPT-5.2
composer-2.5-fast - Composer 2.5 Fast (default)

Tip: use --model <id>
"""
    with patch.object(models, "_run_probe", return_value=out):
        disc = models.discover_models(get_agent_def("cursor-agent"))
    by_id = {m["id"]: m for m in disc.models}
    assert disc.models_source == "live"
    assert by_id["gpt-5.2"]["label"] == "GPT-5.2"
    assert by_id["composer-2.5-fast"]["label"].startswith("Composer")
    assert "Tip:" not in by_id


def test_cursor_models_probe_falls_back_to_list_models():
    calls = []

    def fake_probe(agent, probe=None):
        calls.append(probe)
        if probe == ("models",):
            return None
        if probe == ("--list-models",):
            return "gpt-5.2 - GPT-5.2\n"
        raise AssertionError(f"unexpected probe: {probe}")

    with patch.object(models, "_run_probe", side_effect=fake_probe):
        disc = models.discover_models(get_agent_def("cursor-agent"))

    assert calls == [("models",), ("--list-models",)]
    assert disc.models_source == "live"
    assert any(m["id"] == "gpt-5.2" for m in disc.models)


def test_cursor_model_parser_filters_non_model_status_text():
    out = """No models available. Please sign in to Cursor.
Tip: run cursor-agent login
"""
    with patch.object(models, "_run_probe", return_value=out):
        disc = models.discover_models(get_agent_def("cursor-agent"))

    assert disc.models_source == "fallback"
    assert [m["id"] for m in disc.models] == ["default", "gpt-5"]
