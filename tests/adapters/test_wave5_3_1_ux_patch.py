"""Wave 5.3.1 — UX patch: silent actions, readiness choice gate."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.chat_notifications import (
    has_optional_improvement_gaps,
    on_run_terminal_chat_notifications,
)
from skillhub_eval.persistence.sqlite import SqliteRepository
from tests.core.test_engine import make_confirmed_low_bundle


@pytest.fixture()
def client_with_repo(tmp_path):
    repo = SqliteRepository(str(tmp_path / "w531.db"))
    repo.init_db()
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: AsyncMock()
    app.dependency_overrides[get_gemini_provider] = lambda: AsyncMock()
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, repo


def test_internal_action_message_not_persisted(client_with_repo, tmp_path, monkeypatch):  # noqa: PT019
    client, repo = client_with_repo
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")
    repo.update_conversation_status(conv_id, "awaiting_skill_id_confirm")
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.chat.continue_eval_after_skill_id_confirmed",
        AsyncMock(return_value=(None, None, None, None, True, "awaiting_propagation_confirm")),
    )
    resp = client.post(
            f"/conversations/{conv_id}/chat",
            json={"message": "__ACTION_CONFIRM_SKILL__"},
        )
    assert resp.status_code == 200
    user_msgs = [m for m in repo.get_lui_messages(conv_id) if m["role"] == "user"]
    assert not any("__ACTION_" in m["content"] for m in user_msgs)


@pytest.mark.asyncio
async def test_optional_gaps_defer_auto_formal(tmp_path, monkeypatch):
    repo = SqliteRepository(str(tmp_path / "defer_formal.db"))
    repo.init_db()
    bundle = make_confirmed_low_bundle(tmp_path / "bundle")
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
            (json.dumps({"gaps": [], "skill_summary": {"highlights": "ok"}}, ensure_ascii=False), run_id),
        )
        conn.execute(
            "UPDATE conversations SET active_run_id=? WHERE conversation_id=?",
            (run_id, conv_id),
        )

    assert has_optional_improvement_gaps(bundle) is True

    trigger = AsyncMock(return_value="run-formal")

    class _FakeWriter:
        def __init__(self, repo):
            pass

        trigger_next_run = trigger

    monkeypatch.setattr("skillhub_eval.core.staging_writer.StagingWriter", _FakeWriter)

    ds = AsyncMock()
    gemini = AsyncMock()
    await on_run_terminal_chat_notifications(run_id, repo, ds, gemini)

    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["status"] == "active"
    trigger.assert_awaited_once()

    readiness = next(
        m for m in repo.get_lui_messages(conv_id) if m["message_type"] == "readiness_result"
    )
    payload = readiness["payload_json"]
    assert payload.get("optional_gaps")
