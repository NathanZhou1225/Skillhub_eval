import json
from pathlib import Path
from unittest.mock import patch

from skillhub_eval.core.execution_source import RoutingExecutionSource, resolve_execution_source_name
from skillhub_eval.core.schemas.report import ExecResult


def test_resolve_execution_source_per_skill_over_env(monkeypatch):
    monkeypatch.setattr(
        "skillhub_eval.core.execution_source.settings.exec_source",
        "sample_io",
    )
    monkeypatch.setattr(
        "skillhub_eval.core.execution_source.get_exec_source",
        lambda: "local",
    )
    assert resolve_execution_source_name({"execution_source": "local"}) == "local"
    assert resolve_execution_source_name({}) == "local"


def test_routing_falls_back_to_sample_io_on_local_failure(tmp_path):
    bundle_dir = tmp_path / "skill"
    bundle_dir.mkdir()
    (bundle_dir / "sample_io").mkdir()
    (bundle_dir / "sample_io" / "h01.json").write_text(
        json.dumps({"fallback": True}), encoding="utf-8",
    )
    bundle = {
        "execution_source": "local",
        "bundle_path": str(bundle_dir),
        "has_scripts": False,
    }

    incomplete = ExecResult(actual_output=None, source="local_agent", status="incomplete")

    with patch("skillhub_eval.core.execution_source.LocalAgentSource") as mock_cls:
        mock_cls.return_value.get_actual_output.return_value = incomplete
        src = RoutingExecutionSource(bundle)
        result = src.get_actual_output(
            str(bundle_dir), "h01", case={"id": "h01"}, bundle=bundle,
        )
    assert result.source == "sample_io"
    assert result.actual_output == {"fallback": True}
    assert result.confidence == "low"


def test_routing_local_success_no_fallback(tmp_path):
    bundle_dir = tmp_path / "skill"
    bundle_dir.mkdir()
    bundle = {"execution_source": "local", "bundle_path": str(bundle_dir)}

    ok = ExecResult(
        actual_output={"real": True},
        source="local_agent",
        status="ok",
        level="level_2",
    )
    with patch("skillhub_eval.core.execution_source.LocalAgentSource") as mock_cls:
        mock_cls.return_value.get_actual_output.return_value = ok
        src = RoutingExecutionSource(bundle)
        result = src.get_actual_output(str(bundle_dir), "h01", bundle=bundle)
    assert result.source == "local_agent"
    assert result.actual_output == {"real": True}
