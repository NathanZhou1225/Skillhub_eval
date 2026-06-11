"""Wave 5.3 Task 5 — action chips + confirm synonyms in chat."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.persistence.sqlite import SqliteRepository
from tests.adapters.test_chat_wave5_2_propagation_gate import _seed_propagation_confirm


def _seed_skill_id_confirm(repo: SqliteRepository, tmp_path) -> str:
    conv_id = repo.create_conversation(skill_id="from-skill-md", source="upload")
    staging = tmp_path / "staging" / conv_id
    staging.mkdir(parents=True)
    (staging / "SKILL.md").write_text(
        "---\nname: from-skill-md\n---\n# Demo\n",
        encoding="utf-8",
    )
    repo.update_conversation_status(conv_id, "awaiting_skill_id_confirm")
    return conv_id


@pytest.fixture()
def client_with_repo(tmp_path, monkeypatch):
    repo = SqliteRepository(str(tmp_path / "w53_actions.db"))
    repo.init_db()
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: MagicMock()
    app.dependency_overrides[get_gemini_provider] = lambda: MagicMock()

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, repo


def test_queding_accepted_at_skill_id_gate(client_with_repo, tmp_path):
    client, repo = client_with_repo
    conv_id = _seed_skill_id_confirm(repo, tmp_path)

    with patch(
        "skillhub_eval.adapters.api.routes.chat.continue_eval_after_skill_id_confirmed",
        new_callable=AsyncMock,
        return_value=(None, None, None, None, True, "awaiting_propagation_confirm"),
    ):
        resp = client.post(
            f"/conversations/{conv_id}/chat",
            json={"message": "确定"},
        )

    assert resp.status_code == 200
    assert resp.json()["intent"] == "explain_only"


def test_action_confirm_skill_constant(client_with_repo, tmp_path):
    client, repo = client_with_repo
    conv_id = _seed_skill_id_confirm(repo, tmp_path)

    with patch(
        "skillhub_eval.adapters.api.routes.chat.continue_eval_after_skill_id_confirmed",
        new_callable=AsyncMock,
        return_value=(None, None, None, None, True, "awaiting_propagation_confirm"),
    ):
        resp = client.post(
            f"/conversations/{conv_id}/chat",
            json={"message": "__ACTION_CONFIRM_SKILL__"},
        )

    assert resp.status_code == 200


def test_chat_response_includes_activity_phase_on_propagate(client_with_repo, tmp_path):
    client, repo = client_with_repo
    conv_id = _seed_propagation_confirm(repo, tmp_path)

    with patch(
        "skillhub_eval.adapters.api.routes.chat._execute_propagate",
        new_callable=AsyncMock,
    ) as mock_exec:
        from skillhub_eval.adapters.api.routes.chat import ChatResponse

        mock_exec.return_value = ChatResponse(
            reply="出题中",
            intent="explain_only",
            activity_phase="propagating",
        )
        resp = client.post(
            f"/conversations/{conv_id}/chat",
            json={"message": "__ACTION_PROPAGATE__"},
        )

    assert resp.status_code == 200
    assert resp.json().get("activity_phase") == "propagating"
