"""Wave 5.1 Task 3 — awaiting_draft_confirm chat gate."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.lui_agent import LuiAgent
from skillhub_eval.persistence.sqlite import SqliteRepository


@pytest.fixture()
def client_with_repo(tmp_path, monkeypatch):
    repo = SqliteRepository(str(tmp_path / "draft_gate.db"))
    repo.init_db()
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo

    mock_ds = AsyncMock()
    mock_gemini = AsyncMock()
    app.dependency_overrides[get_ds_provider] = lambda: mock_ds
    app.dependency_overrides[get_gemini_provider] = lambda: mock_gemini

    with TestClient(app) as client:
        yield client, repo, mock_ds


def _seed_conversation(repo: SqliteRepository, tmp_path) -> str:
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")
    staging = tmp_path / "staging" / conv_id
    staging.mkdir(parents=True)
    (staging / "SKILL.md").write_text(
        "---\nid: skill.test\nname: test\nrisk_level: low\ndescription: d\n---\n# body\n",
        encoding="utf-8",
    )
    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path=str(staging),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    with repo._conn() as conn:
        conn.execute(
            "UPDATE conversations SET active_run_id=? WHERE conversation_id=?",
            (run_id, conv_id),
        )
    repo.set_pending_patch(conv_id, {"skill_md_updates": {"description": "patched"}})
    return conv_id


def test_unconfirmed_mutation_blocked(client_with_repo, tmp_path, monkeypatch):
    from skillhub_eval.core.lui_agent import LuiResponse

    client, repo, _mock_ds = client_with_repo
    conv_id = _seed_conversation(repo, tmp_path)

    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.chat.LuiAgent.respond",
        AsyncMock(
            return_value=LuiResponse(
                intent="mutation",
                reply="直接改",
                patch={"skill_md_updates": {"description": "hack"}},
            )
        ),
    )

    resp = client.post(
        f"/conversations/{conv_id}/chat",
        json={"message": "帮我直接改一下"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "DRAFT_NOT_CONFIRMED"


def test_confirm_applies_pending_patch(client_with_repo, tmp_path, monkeypatch):
    client, repo, mock_ds = client_with_repo
    conv_id = _seed_conversation(repo, tmp_path)
    staging = tmp_path / "staging" / conv_id

    trigger = AsyncMock(return_value="run-next")
    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.chat.StagingWriter.trigger_next_run",
        trigger,
    )

    resp = client.post(
        f"/conversations/{conv_id}/chat",
        json={"message": "确认"},
    )
    assert resp.status_code == 200
    assert resp.json()["intent"] == "mutation"
    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["status"] == "active"
    assert repo.get_pending_patch(conv_id) is None
    content = (staging / "SKILL.md").read_text(encoding="utf-8")
    assert "patched" in content
    trigger.assert_awaited_once()


def test_is_draft_confirmation_prefixes():
    assert LuiAgent.is_draft_confirmation("确认")
    assert LuiAgent.is_draft_confirmation("可以，按这个来")
    assert not LuiAgent.is_draft_confirmation("把描述改短一点")
