"""T2 — Gaps engine unit tests."""

from pathlib import Path

import pytest

from skillhub_eval.core.gaps import SECURITY_FIELDS, scan_gaps
from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.core.schemas import BundleState


def _write_skill(tmp_path: Path, *, risk: str | None = "low", description: str = "A test skill"):
    lines = ["---", "name: test-skill"]
    if description:
        lines.append(f"description: {description}")
    if risk is not None:
        lines.append(f"risk_level: {risk}")
    lines.extend(["---", "# Test"])
    (tmp_path / "SKILL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _add_cases(tmp_path: Path, n: int) -> None:
    ec = tmp_path / "eval_cases"
    ec.mkdir(exist_ok=True)
    for i in range(n):
        (ec / f"c{i:02d}.yaml").write_text(
            f"id: c{i:02d}\ntype: happy_path\nuser_intent: intent {i}\n",
            encoding="utf-8",
        )


def test_gaps_detects_missing_eval_cases(tmp_path):
    _write_skill(tmp_path)
    bundle = ingest_bundle(str(tmp_path))
    result = scan_gaps(bundle, BundleState.minimal)

    paths = {g["field_path"] for g in result["gaps"]}
    assert "eval_cases" in paths
    block = next(g for g in result["gaps"] if g["field_path"] == "eval_cases")
    assert block["severity"] == "block"
    assert any("eval_cases" in a for a in result["required_actions"])


def test_gaps_detects_insufficient_case_count(tmp_path):
    _write_skill(tmp_path)
    _add_cases(tmp_path, 1)
    bundle = ingest_bundle(str(tmp_path))
    result = scan_gaps(bundle, BundleState.minimal)

    paths = {g["field_path"] for g in result["gaps"]}
    assert "eval_cases.count" in paths
    gap = next(g for g in result["gaps"] if g["field_path"] == "eval_cases.count")
    assert gap["severity"] == "block"
    assert "2" in gap["message"]  # need 2 more for low (min 3)


def test_gaps_detects_case_count_exceeds_limit(tmp_path):
    _write_skill(tmp_path, risk="low")
    _add_cases(tmp_path, 7)
    bundle = ingest_bundle(str(tmp_path))
    result = scan_gaps(bundle, BundleState.minimal)

    paths = {g["field_path"] for g in result["gaps"]}
    assert "eval_cases.count" in paths
    assert any("上限" in g["message"] or "移除" in g["message"]
               for g in result["gaps"] if g["field_path"] == "eval_cases.count")


def test_gaps_detects_missing_sample_io_for_l1_path(tmp_path):
    _write_skill(tmp_path)
    _add_cases(tmp_path, 3)
    bundle = ingest_bundle(str(tmp_path))
    assert bundle["has_scripts"] is False
    assert bundle["has_sample_io"] is False

    result = scan_gaps(bundle, BundleState.minimal)
    paths = {g["field_path"] for g in result["gaps"]}
    assert "sample_io" in paths
    assert any(g["severity"] == "block" for g in result["gaps"] if g["field_path"] == "sample_io")


def test_gaps_skips_sample_io_when_scripts_present(tmp_path):
    _write_skill(tmp_path)
    _add_cases(tmp_path, 3)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run.py").write_text("print('ok')\n", encoding="utf-8")
    bundle = ingest_bundle(str(tmp_path))

    result = scan_gaps(bundle, BundleState.minimal)
    paths = {g["field_path"] for g in result["gaps"]}
    assert "sample_io" not in paths


def test_gaps_warns_missing_description(tmp_path):
    _write_skill(tmp_path, description="")
    bundle = ingest_bundle(str(tmp_path))
    result = scan_gaps(bundle, BundleState.minimal)

    gap = next(g for g in result["gaps"] if g["field_path"] == "description")
    assert gap["severity"] == "warn"


def test_gaps_info_when_risk_level_not_declared(tmp_path):
    _write_skill(tmp_path, risk=None)
    bundle = ingest_bundle(str(tmp_path))
    result = scan_gaps(bundle, BundleState.minimal)

    gap = next(g for g in result["gaps"] if g["field_path"] == "risk_level")
    assert gap["severity"] == "info"


def test_gaps_warns_unconfirmed_security_fields(tmp_path):
    _write_skill(tmp_path)
    bundle = ingest_bundle(str(tmp_path))
    result = scan_gaps(bundle, BundleState.minimal, confirmed_field_paths=frozenset())

    sec_gaps = [g for g in result["gaps"] if g["field_path"] in SECURITY_FIELDS]
    assert len(sec_gaps) == len(SECURITY_FIELDS)
    assert all(g["severity"] == "warn" for g in sec_gaps)


def test_gaps_skips_confirmed_security_fields(tmp_path):
    _write_skill(tmp_path)
    bundle = ingest_bundle(str(tmp_path))
    confirmed = frozenset({"negative_prompts", "error_handling"})
    result = scan_gaps(bundle, BundleState.minimal, confirmed_field_paths=confirmed)

    paths = {g["field_path"] for g in result["gaps"]}
    assert "negative_prompts" not in paths
    assert "error_handling" not in paths
    assert "permission_scope" in paths


def test_gaps_minimal_bundle_has_required_actions(tmp_path):
    """grill-me-like minimal bundle produces block + warn required_actions."""
    _write_skill(tmp_path, description="")
    bundle = ingest_bundle(str(tmp_path))
    result = scan_gaps(bundle, BundleState.minimal)

    assert result["gaps"]
    assert result["required_actions"]
    assert len(result["required_actions"]) >= 2
    # T2: no template YAML/JSON bodies in snapshot
    snapshot_text = str(result)
    assert "user_intent:" not in snapshot_text
    assert '"response"' not in snapshot_text


def test_gaps_complete_l1_bundle_minimal_gaps(tmp_path):
    _write_skill(tmp_path)
    _add_cases(tmp_path, 3)
    (tmp_path / "sample_io").mkdir()
    (tmp_path / "sample_io" / "c00.json").write_text('{"response":"ok"}\n', encoding="utf-8")
    bundle = ingest_bundle(str(tmp_path))
    confirmed = frozenset(SECURITY_FIELDS)
    result = scan_gaps(bundle, BundleState.minimal, confirmed_field_paths=confirmed)

    block_gaps = [g for g in result["gaps"] if g["severity"] == "block"]
    assert block_gaps == []
