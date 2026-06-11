"""Wave 5.1 Task 6 — report split E2E."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from skillhub_eval.core.chat_notifications import (
    append_rich_report_message,
    build_rich_report_payload,
    on_run_terminal_chat_notifications,
)
from skillhub_eval.core.lui_agent import LuiAgent
from skillhub_eval.persistence.sqlite import SqliteRepository
from tests.core.test_engine import make_confirmed_low_bundle, make_draft_enriched_bundle


class _TemplateProvider:
    async def judge(self, prompt: str) -> dict:
        return {
            "reply": "初评发现缺口，建议补全 description。确认后我再写入。",
            "patch": {"skill_md_updates": {"description": "filled"}, "eval_cases": []},
        }


@pytest.mark.asyncio
async def test_auto_formal_after_gap_zero_initial(tmp_path, monkeypatch):
    repo = SqliteRepository(str(tmp_path / "auto_formal.db"))
    repo.init_db()
    bundle = make_confirmed_low_bundle(tmp_path / "bundle")
    skill_md_path = tmp_path / "bundle" / "SKILL.md"
    skill_md_path.write_text(
        "---\nname: test-skill\nid: skill.test\nrisk_level: low\n"
        "description: 员工出勤智能核查\n"
        "category: general-utility/report-generator\n"
        "negative_prompts: 禁止越权\n"
        "error_handling: 明确错误提示\n"
        "permission_scope: 只读考勤\n"
        "security_notes: 不含 PII\n"
        "---\n# Test\n",
        encoding="utf-8",
    )
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")
    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path=bundle,
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, "completed", review_status="warn")
    with repo._conn() as conn:
        conn.execute(
            "UPDATE evaluation_runs SET report_json=? WHERE run_id=?",
            (
                json.dumps(
                    {"skill_summary": {"highlights": "ok"}, "gaps": []},
                    ensure_ascii=False,
                ),
                run_id,
            ),
        )
        conn.execute(
            "UPDATE conversations SET active_run_id=? WHERE conversation_id=?",
            (run_id, conv_id),
        )

    trigger = AsyncMock(return_value="run-formal")

    class _FakeWriter:
        def __init__(self, repo):
            pass

        trigger_next_run = trigger

    monkeypatch.setattr(
        "skillhub_eval.core.staging_writer.StagingWriter",
        _FakeWriter,
    )

    ds = AsyncMock()
    gemini = AsyncMock()
    await on_run_terminal_chat_notifications(run_id, repo, ds, gemini)

    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["auto_confirmed"] == 1
    trigger.assert_awaited_once()
    messages = repo.get_lui_messages(conv_id)
    readiness = [m for m in messages if m.get("message_type") == "readiness_result"]
    assert len(readiness) == 1
    assert readiness[0]["payload_json"].get("can_enter_formal") is not None
    rich = [m for m in messages if m.get("message_type") == "rich_report"]
    assert len(rich) == 0


@pytest.mark.asyncio
async def test_gap_path_sets_pending_patch(tmp_path):
    repo = SqliteRepository(str(tmp_path / "gaps.db"))
    repo.init_db()
    bundle = make_draft_enriched_bundle(tmp_path / "bundle")
    conv_id = repo.create_conversation(skill_id="skill.draft", source="upload")
    run_id = repo.create_run(
        skill_id="skill.draft",
        skill_bundle_path=bundle,
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, "completed")
    gaps = [{"severity": "required", "field_path": "description", "message": "missing"}]
    with repo._conn() as conn:
        conn.execute(
            "UPDATE evaluation_runs SET report_json=? WHERE run_id=?",
            (
                json.dumps({"gaps": gaps, "skill_summary": {}}, ensure_ascii=False),
                run_id,
            ),
        )

    agent = LuiAgent(ds_provider=_TemplateProvider())
    await agent.handle_post_initial_review(conv_id, run_id, repo)

    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["status"] == "awaiting_draft_confirm"
    assert repo.get_pending_patch(conv_id) is not None
    msgs = [m for m in repo.get_lui_messages(conv_id) if m["role"] == "agent"]
    assert any("缺口" in m["content"] or "草案" in m["content"] for m in msgs)


def test_formal_payload_has_score_line(tmp_path):
    bundle = make_confirmed_low_bundle(tmp_path / "bundle")
    repo = SqliteRepository(str(tmp_path / "score.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")
    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path=bundle,
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, "completed", score_total=88.5)

    payload = build_rich_report_payload(run_id, repo)
    assert payload["report_phase"] == "formal"
    assert payload["score_line_html"] is not None
    assert "88.5" in payload["score_line_html"]
