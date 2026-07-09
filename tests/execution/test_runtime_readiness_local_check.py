"""Local-check readiness must not tell users to generate cases before clicking."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from skillhub_eval.execution.runtime_readiness import (
    LOCAL_CHECK_MESSAGES_ZH,
    _local_check_state,
)


def _low_risk_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "filesystem-like"
    root.mkdir()
    (root / "SKILL.md").write_text(
        "---\nname: filesystem-mcp-server\nrisk_level: low\n---\n# Demo\n",
        encoding="utf-8",
    )
    return root


def test_low_risk_without_preflight_case_is_missing_not_blocked(tmp_path):
    root = _low_risk_bundle(tmp_path)
    repo = MagicMock()
    repo.get_runtime_preflight.return_value = None
    fake_context = {
        "runtime": MagicMock(runtime_id="trae"),
        "bundle": {
            "risk_level_declared": "low",
            "eval_cases": [],
        },
        "skill_fingerprint": "fp-skill",
        "fingerprint": "fp-rt",
        "model_id": "default",
    }

    with patch(
        "skillhub_eval.execution.runtime_readiness.PreflightRunner._context",
        return_value=fake_context,
    ):
        state = _local_check_state(
            skill_bundle_path=str(root),
            runtime_id="trae",
            model_id="default",
            repo=repo,
        )

    assert state["local_check_status"] == "missing"
    assert state["can_run_local_check"] is True
    assert "生成检查用例" not in state["local_check_message_zh"]
    assert "尚未检查" in state["local_check_message_zh"]


def test_copy_does_not_call_unchecked_a_failure():
    assert "失败" not in LOCAL_CHECK_MESSAGES_ZH["missing"]
    assert "生成检查用例" not in LOCAL_CHECK_MESSAGES_ZH["missing"]
    assert LOCAL_CHECK_MESSAGES_ZH["failed"].startswith("检查未通过")
    assert "失败" not in LOCAL_CHECK_MESSAGES_ZH["blocked"]
