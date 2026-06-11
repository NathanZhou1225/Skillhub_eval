"""Wave 5.3 Task 7 — draft_preview flow via propagation fork."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.persistence.sqlite import SqliteRepository
from tests.adapters.test_chat_wave5_2_propagation_gate import (
    _seed_propagation_confirm,
)


@pytest.fixture()
def client_with_repo(tmp_path, monkeypatch):
    repo = SqliteRepository(str(tmp_path / "w53_draft.db"))
    repo.init_db()
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    mock_ds = MagicMock()
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: mock_ds
    app.dependency_overrides[get_gemini_provider] = lambda: MagicMock()

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, repo, mock_ds


def test_scene_choice_write_file_publishes_draft_preview(client_with_repo, tmp_path):
    client, repo, mock_ds = client_with_repo
    conv_id = _seed_propagation_confirm(repo, tmp_path)
    repo.update_conversation_status(conv_id, "awaiting_propagation_scene_choice")

    mock_patch = {
        "eval_cases": [{"id": "draft_001", "type": "happy_path"}],
        "sample_io": [],
    }
    with patch(
        "skillhub_eval.adapters.api.routes.chat.LuiAgent.generate_draft_for_staging",
        new_callable=AsyncMock,
        return_value=mock_patch,
    ) as mock_generate:
        resp = client.post(
            f"/conversations/{conv_id}/chat",
            json={"message": "__ACTION_DRAFT_WRITE_FILE__"},
        )

    assert resp.status_code == 200
    assert resp.json().get("activity_phase") == "writing_draft"
    conv = repo.get_conversation(conv_id)
    assert conv["status"] == "awaiting_draft_confirm"
    mock_generate.assert_awaited_once()


def test_draft_fork_from_propagation_confirm(client_with_repo, tmp_path):
    client, repo, _mock_ds = client_with_repo
    conv_id = _seed_propagation_confirm(repo, tmp_path)

    resp = client.post(
        f"/conversations/{conv_id}/chat",
        json={"message": "__ACTION_DRAFT_MODE__"},
    )
    assert resp.status_code == 200
    conv = repo.get_conversation(conv_id)
    assert conv["status"] == "awaiting_propagation_dialogue"
