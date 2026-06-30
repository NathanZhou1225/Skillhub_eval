from pathlib import Path
from unittest.mock import patch

from skillhub_eval.execution.agent_registry import get_agent_def
from skillhub_eval.execution import detection


def setup_function():
    detection.clear_detection_cache()


def test_resolve_via_install_dir_glob(tmp_path, monkeypatch):
    bin_dir = tmp_path / "trae-cli" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "trae-cli.exe").write_text("x")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with patch.object(detection, "find_cli_binary", return_value=None):
        path = detection.resolve_agent_binary(get_agent_def("trae"))
    assert path and path.endswith("trae-cli.exe")


def test_detected_with_config_dir_is_ok(monkeypatch):
    with patch.object(detection, "resolve_agent_binary", return_value="/bin/codex"), \
         patch.object(detection, "_config_dir_present", return_value=True):
        r = detection.detect_agent(get_agent_def("codex"))
    assert r.detected and r.auth_state == "ok"


def test_binary_without_config_dir_is_missing(monkeypatch):
    with patch.object(detection, "resolve_agent_binary", return_value="/bin/codex"), \
         patch.object(detection, "_config_dir_present", return_value=False):
        r = detection.detect_agent(get_agent_def("codex"))
    assert r.detected and r.auth_state == "missing"


def test_cursor_is_unknown_when_detected():
    with patch.object(detection, "resolve_agent_binary", return_value="/bin/cursor-agent"), \
         patch.object(detection, "_config_dir_present", return_value=True):
        r = detection.detect_agent(get_agent_def("cursor-agent"))
    assert r.detected and r.auth_state == "unknown"


def test_no_binary_not_detected():
    with patch.object(detection, "resolve_agent_binary", return_value=None):
        r = detection.detect_agent(get_agent_def("codex"))
    assert r.detected is False and r.auth_state == "missing"


def test_cache_avoids_second_probe():
    calls = {"n": 0}

    def fake_resolve(_def):
        calls["n"] += 1
        return "/bin/codex"

    with patch.object(detection, "resolve_agent_binary", side_effect=fake_resolve), \
         patch.object(detection, "_config_dir_present", return_value=True):
        detection.detect_agent(get_agent_def("codex"))
        detection.detect_agent(get_agent_def("codex"))
    assert calls["n"] == 1
