"""Task 2 — Rich Report server-side write (chat_notifications)."""

import pytest

from skillhub_eval.core.chat_notifications import (
    append_rich_report_message,
    build_rich_report_payload,
)
from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.core.schemas import BundleState, EvaluationMode
from skillhub_eval.persistence.sqlite import SqliteRepository

from tests.core.test_engine import (
    make_confirmed_low_bundle,
    make_draft_enriched_bundle,
    make_engine,
)


def _make_repo_with_conv(tmp_path, bundle_path: str, skill_id: str = "skill.test"):
    repo = SqliteRepository(str(tmp_path / "chat_notif.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id=skill_id, source="upload")
    run_id = repo.create_run(
        skill_id=skill_id,
        skill_bundle_path=bundle_path,
        bundle_state="draft_enriched",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    return repo, conv_id, run_id


def test_build_rich_report_payload_matches_get_report_shape(tmp_path):
    bundle = make_draft_enriched_bundle(tmp_path / "bundle")
    repo, conv_id, run_id = _make_repo_with_conv(tmp_path, bundle, skill_id="skill.draft")
    repo.update_status(run_id, "awaiting_confirm")

    payload = build_rich_report_payload(run_id, repo)

    assert payload["run_id"] == run_id
    assert payload["conversation_id"] == conv_id
    assert payload["status"] == "awaiting_confirm"
    assert "review_status" in payload
    assert "reason_codes" in payload
    assert "human_review_required" in payload
    assert "report" in payload
    assert "actions" in payload
    assert isinstance(payload["actions"], list)


def test_initial_phase_hides_score_line(tmp_path):
    bundle = make_draft_enriched_bundle(tmp_path / "bundle")
    repo, _conv_id, run_id = _make_repo_with_conv(tmp_path, bundle, skill_id="skill.draft")
    with repo._conn() as conn:
        conn.execute(
            "UPDATE evaluation_runs SET evaluation_mode='degraded' WHERE run_id=?",
            (run_id,),
        )
    repo.update_status(run_id, "completed", score_total=72.5)

    payload = build_rich_report_payload(run_id, repo)
    assert payload["report_phase"] == "initial"
    assert payload["score_line_html"] is None
    assert not any(a["id"] == "confirm_all" for a in payload["actions"])


def _make_formal_run_repo(tmp_path, *, status: str, review_status: str, human_review: bool = False):
    bundle = make_confirmed_low_bundle(tmp_path / "bundle")
    repo = SqliteRepository(str(tmp_path / "formal.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")
    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path=bundle,
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, status, review_status=review_status, score_total=81.0)
    if human_review:
        repo.set_human_review_required(run_id, True, ["R5_MODEL_DISAGREEMENT"])
    return repo, conv_id, run_id


def test_formal_pass_verdict_and_next_action(tmp_path):
    repo, _conv_id, run_id = _make_formal_run_repo(
        tmp_path, status="completed", review_status="pass"
    )
    payload = build_rich_report_payload(run_id, repo)

    assert payload["verdict_zh"] == "通过"
    assert payload["verdict_badge_class"] == "pass"
    assert "上架" in payload["next_action_zh"]
    assert any(a["id"] == "openRunDetail" for a in payload["actions"])


def test_formal_warn_without_human_review_verdict(tmp_path):
    repo, _conv_id, run_id = _make_formal_run_repo(
        tmp_path, status="completed", review_status="warn", human_review=False
    )
    payload = build_rich_report_payload(run_id, repo)

    assert payload["verdict_zh"] == "通过（有改进建议）"
    assert payload["verdict_badge_class"] == "pass_warn"
    assert payload["next_action_zh"] == "建议按报告优化后再次提交"


def test_formal_awaiting_human_review_verdict(tmp_path):
    repo, _conv_id, run_id = _make_formal_run_repo(
        tmp_path,
        status="awaiting_human_review",
        review_status="warn",
        human_review=True,
    )
    payload = build_rich_report_payload(run_id, repo)

    assert payload["report_phase"] == "formal_pending_review"
    assert payload["verdict_zh"] == "需人工复核"
    assert payload["verdict_badge_class"] == "warn"
    assert "专家裁定" in payload["next_action_zh"]


def test_formal_fail_verdict(tmp_path):
    repo, _conv_id, run_id = _make_formal_run_repo(
        tmp_path, status="completed", review_status="fail"
    )
    payload = build_rich_report_payload(run_id, repo)

    assert payload["verdict_zh"] == "未通过"
    assert payload["verdict_badge_class"] == "fail"
    assert "完整报告" in payload["next_action_zh"]


def test_initial_phase_omits_verdict_fields(tmp_path):
    bundle = make_draft_enriched_bundle(tmp_path / "bundle")
    repo, _conv_id, run_id = _make_repo_with_conv(tmp_path, bundle, skill_id="skill.draft")
    with repo._conn() as conn:
        conn.execute(
            "UPDATE evaluation_runs SET evaluation_mode='degraded' WHERE run_id=?",
            (run_id,),
        )
    repo.update_status(run_id, "completed", review_status="warn")

    payload = build_rich_report_payload(run_id, repo)

    assert payload["report_phase"] == "initial"
    assert "verdict_zh" not in payload
    assert "verdict_badge_class" not in payload
    assert "next_action_zh" not in payload
    assert not any(a["id"] == "openRunDetail" for a in payload["actions"])


def test_formal_phase_shows_score_line(tmp_path):
    bundle = make_confirmed_low_bundle(tmp_path / "bundle")
    repo = SqliteRepository(str(tmp_path / "formal.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")
    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path=bundle,
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, "completed", score_total=81.0)

    payload = build_rich_report_payload(run_id, repo)
    assert payload["report_phase"] == "formal"
    assert payload["score_line_html"] is not None
    assert "81.0" in payload["score_line_html"]
    assert not any(a["id"] == "confirm_all" for a in payload["actions"])


def test_expert_actions_have_visible_in_and_enabled_on_human_review(tmp_path):
    bundle = make_confirmed_low_bundle(tmp_path / "bundle")
    repo = SqliteRepository(str(tmp_path / "expert.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")
    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path=bundle,
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    repo.update_status(
        run_id,
        "awaiting_human_review",
        review_status="warn",
    )
    repo.set_human_review_required(run_id, True, ["R5_MODEL_DISAGREEMENT"])

    payload = build_rich_report_payload(run_id, repo)
    expert = [a for a in payload["actions"] if a["id"].startswith("expert_")]
    assert len(expert) == 2
    for action in expert:
        assert action["visible_in"] == "expert"
        assert action["enabled"] is True


def test_append_rich_report_message_is_idempotent(tmp_path):
    bundle = make_draft_enriched_bundle(tmp_path / "bundle")
    repo, conv_id, run_id = _make_repo_with_conv(tmp_path, bundle, skill_id="skill.draft")
    repo.update_status(run_id, "awaiting_confirm")

    append_rich_report_message(conv_id, run_id, repo)
    append_rich_report_message(conv_id, run_id, repo)

    messages = repo.get_lui_messages(conv_id)
    rich = [m for m in messages if m.get("message_type") == "rich_report"]
    assert len(rich) == 1
    assert rich[0]["payload_json"]["run_id"] == run_id


def test_append_rich_report_message_writes_agent_bubble(tmp_path):
    bundle = make_draft_enriched_bundle(tmp_path / "bundle")
    repo, conv_id, run_id = _make_repo_with_conv(tmp_path, bundle, skill_id="skill.draft")
    repo.update_status(run_id, "awaiting_confirm")

    append_rich_report_message(conv_id, run_id, repo)

    messages = repo.get_lui_messages(conv_id)
    assert len(messages) == 1
    msg = messages[0]
    assert msg["role"] == "agent"
    assert msg["message_type"] == "rich_report"
    assert msg["run_id"] == run_id
    assert msg["content"]
    assert msg["payload_json"]["status"] == "awaiting_confirm"


@pytest.mark.asyncio
async def test_engine_parks_awaiting_confirm_writes_rich_report(tmp_path):
    bundle = make_draft_enriched_bundle(tmp_path / "bundle")
    engine, repo = make_engine(tmp_path)
    conv_id = repo.create_conversation(skill_id="skill.draft", source="upload")
    run_id = repo.create_run(
        skill_id="skill.draft",
        skill_bundle_path=bundle,
        bundle_state="draft_enriched",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )

    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle,
        bundle_state=BundleState.draft_enriched,
        evaluation_mode=EvaluationMode.capability_full,
    )

    assert repo.get_run(run_id)["status"] == "awaiting_confirm"
    messages = repo.get_lui_messages(conv_id)
    rich = [m for m in messages if m.get("message_type") == "rich_report"]
    assert len(rich) == 1
    assert rich[0]["payload_json"]["run_id"] == run_id


@pytest.mark.asyncio
async def test_engine_finalize_writes_rich_report_for_conversation(tmp_path):
    bundle = make_confirmed_low_bundle(tmp_path / "bundle")
    engine, repo = make_engine(tmp_path)
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")
    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path=bundle,
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )

    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle,
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
    )

    run = repo.get_run(run_id)
    assert run["status"] in ("completed", "awaiting_human_review")
    messages = repo.get_lui_messages(conv_id)
    rich = [m for m in messages if m.get("message_type") == "rich_report"]
    assert len(rich) == 1
    assert rich[0]["payload_json"]["status"] == run["status"]
