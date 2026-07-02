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


def test_routing_does_not_mask_local_failure_as_sample_io(tmp_path):
    """Genuine local-agent failures (e.g. run_incomplete) SHALL NOT be silently
    replaced with a fake sample_io 'ok' result — the failure must stay visible."""
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

    incomplete = ExecResult(
        actual_output=None,
        source="local_agent",
        status="incomplete",
        degrade_reason="run_incomplete",
        stderr_excerpt="agent crashed",
    )

    with patch("skillhub_eval.core.execution_source.LocalAgentSource") as mock_cls:
        mock_cls.return_value.get_actual_output.return_value = incomplete
        src = RoutingExecutionSource(bundle)
        result = src.get_actual_output(
            str(bundle_dir), "h01", case={"id": "h01"}, bundle=bundle,
        )
    assert result.source == "local_agent"
    assert result.status == "incomplete"
    assert result.degrade_reason == "run_incomplete"
    assert result.stderr_excerpt == "agent crashed"
    assert result.actual_output is None


def test_routing_still_degrades_redline_without_hardened_profile(tmp_path):
    """The one spec'd exception: redline cases on agents without a hardened
    profile are a deliberate, known degrade — not a failure — so they still
    get scored via sample_io."""
    bundle_dir = tmp_path / "skill"
    bundle_dir.mkdir()
    (bundle_dir / "sample_io").mkdir()
    (bundle_dir / "sample_io" / "r01.json").write_text(
        json.dumps({"doc_centric": True}), encoding="utf-8",
    )
    bundle = {
        "execution_source": "local",
        "bundle_path": str(bundle_dir),
        "has_scripts": False,
    }

    redline_degrade = ExecResult(
        actual_output=None,
        source="local_agent",
        status="incomplete",
        degrade_reason="redline_no_hardened_profile",
    )

    with patch("skillhub_eval.core.execution_source.LocalAgentSource") as mock_cls:
        mock_cls.return_value.get_actual_output.return_value = redline_degrade
        src = RoutingExecutionSource(bundle)
        result = src.get_actual_output(
            str(bundle_dir), "r01", case={"id": "r01"}, bundle=bundle,
        )
    assert result.source == "sample_io"
    assert result.status == "ok"
    assert result.actual_output == {"doc_centric": True}
    assert result.degrade_reason == "redline_no_hardened_profile"


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
