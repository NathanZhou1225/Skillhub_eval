from datetime import UTC, datetime

import pytest

from skillhub_eval.core.chat_notifications import (
    append_readiness_result_message,
    on_run_terminal_chat_notifications,
)
from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.core.schemas import (
    BundleState,
    EvaluationMode,
    EvaluationReport,
    RunStatus,
)
from skillhub_eval.persistence.sqlite import SqliteRepository
from tests.core.test_engine import make_draft_enriched_bundle, make_engine


def _seed_degraded_report(repo: SqliteRepository, run_id: str, bundle_path: str) -> None:
    report = EvaluationReport(
        run_id=run_id,
        skill_id="skill.draft",
        skill_bundle_path=bundle_path,
        bundle_state=BundleState.draft_enriched,
        evaluation_mode=EvaluationMode.degraded,
        status=RunStatus.completed,
        review_status="warn",
        score_total=None,
        score_total_source="not_applicable",
        completeness_score=80.0,
        gaps=[{"field_path": "sample_io", "severity": "block"}],
        required_actions=["补齐 sample_io"],
        stage_progress=["level0_checking", "risk_locking", "normalizing"],
        security_status="passed",
        risk_level_locked="low",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    repo.save_report(run_id, report)
    repo.update_status(run_id, "completed", review_status="warn", score_total=None)


def test_append_readiness_result_message_writes_readiness_type(tmp_path):
    bundle = make_draft_enriched_bundle(tmp_path / "bundle")
    repo = SqliteRepository(str(tmp_path / "notif.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill.draft", source="upload")
    run_id = repo.create_run(
        skill_id="skill.draft",
        skill_bundle_path=bundle,
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    _seed_degraded_report(repo, run_id, bundle)

    append_readiness_result_message(conv_id, run_id, repo)

    messages = repo.get_lui_messages(conv_id)
    readiness = [m for m in messages if m.get("message_type") == "readiness_result"]
    assert len(readiness) == 1
    payload = readiness[0]["payload_json"]
    assert payload["run_id"] == run_id
    assert payload["can_enter_formal"] is False
    assert "body_sections" in payload


@pytest.mark.asyncio
async def test_on_run_terminal_degraded_uses_readiness_not_rich_report(tmp_path):
    bundle = make_draft_enriched_bundle(tmp_path / "bundle")
    engine, repo = make_engine(tmp_path)
    conv_id = repo.create_conversation(skill_id="skill.draft", source="upload")
    run_id = repo.create_run(
        skill_id="skill.draft",
        skill_bundle_path=bundle,
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle,
        bundle_state=BundleState.draft_enriched,
        evaluation_mode=EvaluationMode.degraded,
    )

    # Re-trigger notification hook to verify idempotent message routing behavior.
    await on_run_terminal_chat_notifications(run_id, repo, engine.ds, engine.wb)

    messages = repo.get_lui_messages(conv_id)
    readiness = [m for m in messages if m.get("message_type") == "readiness_result"]
    rich = [m for m in messages if m.get("message_type") == "rich_report"]
    assert readiness
    assert not rich
