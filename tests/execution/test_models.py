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
