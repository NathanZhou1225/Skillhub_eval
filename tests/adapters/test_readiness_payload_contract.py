"""Wave 5.3 Task 1 — readiness_result flat payload ↔ UI contract."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from skillhub_eval.core.chat_notifications import append_readiness_result_message
from skillhub_eval.core.schemas import (
    BundleState,
    EvaluationMode,
    EvaluationReport,
    RunStatus,
)
from skillhub_eval.persistence.sqlite import SqliteRepository

_UI_PATH = (
    Path(__file__).resolve().parents[2]
    / "skillhub_eval"
    / "adapters"
    / "ui"
    / "static"
    / "index.html"
)

_REQUIRED_UI_FIELDS = (
    "completeness_score",
    "security_status",
    "risk_level_locked",
    "case_gate",
    "gap_count",
    "评估条件门槛",
    "可选改进",
    "红线说明",
    "ACTION_START_FORMAL",
)


def test_readiness_payload_exposes_flat_fields_for_ui(tmp_path, monkeypatch):
    repo = SqliteRepository(str(tmp_path / "readiness.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")
    staging = tmp_path / "staging" / conv_id
    staging.mkdir(parents=True)
    bundle_path = str(staging)
    (staging / "SKILL.md").write_text(
        "---\nid: skill.test\nname: test\nrisk_level: low\ndescription: d\n---\n# body\n",
        encoding="utf-8",
    )
    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path=bundle_path,
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    report = EvaluationReport(
        run_id=run_id,
        skill_id="skill.test",
        skill_bundle_path=bundle_path,
        bundle_state=BundleState.draft_enriched,
        evaluation_mode=EvaluationMode.degraded,
        status=RunStatus.completed,
        review_status="warn",
        completeness_score=72.5,
        security_status="pass",
        risk_level_locked="low",
        gaps=[{"message": "缺 eval_cases"}],
        required_actions=["补齐 happy_path"],
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    repo.save_report(run_id, report)
    monkeypatch.setattr(
        "skillhub_eval.core.chat_notifications.compute_gap_zero",
        lambda _path: False,
    )
    monkeypatch.setattr(
        "skillhub_eval.core.chat_notifications.compute_case_gate",
        lambda _path: {"passed": False, "type_coverage": {"happy_path": 0}},
    )

    append_readiness_result_message(conv_id, run_id, repo)
    messages = repo.get_lui_messages(conv_id)
    readiness = next(m for m in messages if m["message_type"] == "readiness_result")
    payload = readiness["payload_json"]
    if isinstance(payload, str):
        import json

        payload = json.loads(payload)

    assert payload["completeness_score"] == 72.5
    assert payload["security_status"] == "pass"
    assert payload["risk_level_locked"] == "low"
    assert "passed" in payload["case_gate"]
    assert payload["case_gate"]["passed"] is False
    assert "optional_gaps" in payload
    assert "blocking_gaps" in payload
    assert "security_status_zh" in payload


def test_index_html_reads_flat_readiness_and_plan_fields():
    html = _UI_PATH.read_text(encoding="utf-8")
    for token in _REQUIRED_UI_FIELDS:
        assert token in html, f"missing UI contract token: {token}"
    assert "input.value = ''" in html
    assert "sendConversationMessage" in html
