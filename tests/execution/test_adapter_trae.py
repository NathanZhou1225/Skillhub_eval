from unittest.mock import patch

import yaml

from skillhub_eval.execution import diagnostics, models as models_module
from skillhub_eval.execution.adapters.trae import TraeAdapter


def test_build_args_stream_json():
    with patch("skillhub_eval.execution.adapters.trae._resolved_bin", return_value="trae-cli"):
        args = TraeAdapter(model=None).build_args(cwd="/tmp")
    assert args[0] == "trae-cli"
    assert "-p" in args or "--print" in args
    assert "--output-format" in args and "stream-json" in args
    assert "--yolo" in args
    assert "acp" not in args  # G1: no longer ACP


def test_build_args_includes_model():
    with patch("skillhub_eval.execution.adapters.trae._resolved_bin", return_value="trae-cli"):
        args = TraeAdapter(model="GLM-5.2").build_args(cwd="/tmp")
    assert "--model" not in args
    assert "-c" in args
    assert "model.name=GLM-5.2" in args


def test_trae_prompt_via_stdin_false():
    assert TraeAdapter().prompt_via_stdin is False


def test_parse_stream_trae_result_event():
    a = TraeAdapter()
    lines = [
        '{"type":"stream_event","delta":{"role":"assistant","content":"OK"}}',
        '{"type":"result","subtype":"success","result":"OK","duration_ms":12004,'
        '"usage":{"input_tokens":10,"output_tokens":1}}',
    ]
    parsed = a.parse_stream(lines)
    assert parsed.is_complete is True
    assert "OK" in parsed.final_text


def test_parse_stream_reuses_generic_parser():
    a = TraeAdapter()
    parsed = a.parse_stream(['{"type":"result","result":"ok"}'])
    assert parsed.is_complete is True


def test_diagnose_missing_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    result = TraeAdapter().diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_CONFIG_DIR_MISSING"


def test_diagnose_dir_not_writable(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / ".trae").mkdir()
    with patch.object(diagnostics, "check_writable", return_value=False):
        result = TraeAdapter().diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_CONFIG_DIR_NOT_WRITABLE"


def test_diagnose_missing_models_section(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump({"model": {"name": "GLM-5.2"}}), encoding="utf-8"
    )
    result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_MODEL_NOT_CONFIGURED"


def test_diagnose_reads_fallback_config_filename(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "traecli.yaml").write_text(
        yaml.safe_dump({"model": {"name": "GLM-5.2"}}), encoding="utf-8"
    )
    result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_MODEL_NOT_CONFIGURED"


def test_diagnose_probe_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump(
            {"model": {"name": "GLM-5.2"}, "models": [{"name": "GLM-5.2", "provider": "zhipu"}]}
        ),
        encoding="utf-8",
    )
    with patch.object(models_module, "_run_probe", return_value=None):
        result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_MODEL_PROBE_UNAVAILABLE"


def test_diagnose_model_not_in_probe_list(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump(
            {"model": {"name": "GLM-5.2"}, "models": [{"name": "other-model", "provider": "zhipu"}]}
        ),
        encoding="utf-8",
    )
    with patch.object(models_module, "_run_probe", return_value="other-model\n"):
        result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_MODEL_NOT_IN_LIST"


def test_diagnose_ok_when_model_resolves(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump(
            {"model": {"name": "GLM-5.2"}, "models": [{"name": "GLM-5.2", "provider": "zhipu"}]}
        ),
        encoding="utf-8",
    )
    with patch.object(models_module, "_run_probe", return_value="GLM-5.2\n"):
        result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is True
    assert result.reason_code is None
