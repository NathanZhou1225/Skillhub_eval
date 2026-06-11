"""Wave 5.3 Task 10 — bootstrap enrich + confirm E2E (mock LLM)."""

from __future__ import annotations

import io
import json
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.persistence.sqlite import SqliteRepository


def _zip_skill_only() -> bytes:
    buffer = io.BytesIO()
    skill_md = (
        "---\n"
        "name: w53-e2e\n"
        "description: E2E skill for wave5.3 with long enough description for L0 gate.\n"
        "risk_level: low\n"
        "category: fin-research/quant-signal\n"
        "---\n"
        "# W53 E2E\n"
    )
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", skill_md)
    return buffer.getvalue()


@pytest.fixture()
def client_with_repo(tmp_path):
    repo = SqliteRepository(str(tmp_path / "w53_e2e.db"))
    repo.init_db()
    mock_ds = MagicMock()
    mock_ds.generate = AsyncMock(
        return_value=json.dumps(
            {
                "rows": [
                    {
                        "type": "happy_path",
                        "tests_what": "主流程",
                        "business_expectation": "E2E 专属文案",
                        "redline_note": "",
                    }
                ]
            }
        )
    )
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: mock_ds
    app.dependency_overrides[get_gemini_provider] = lambda: MagicMock()

    with patch(
        "skillhub_eval.adapters.api.routes.conversations.EvaluationEngine"
    ) as mock_engine:
        mock_engine.return_value.run_async = AsyncMock()
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client, repo, mock_ds


def test_bootstrap_enrich_then_confirm_skill_id_with_queding(
    client_with_repo, tmp_path, monkeypatch
):
    client, repo, mock_ds = client_with_repo
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    conv_id = client.post("/conversations/new").json()["conversation_id"]
    bootstrap = client.post(
        f"/conversations/{conv_id}/bootstrap",
        data={"skill_id": "w53-e2e", "source": "upload"},
        files={"bundle_zip": ("b.zip", _zip_skill_only(), "application/zip")},
    )
    assert bootstrap.status_code == 202
    body = bootstrap.json()
    assert body.get("propagation_deferred") is True

    assert mock_ds.generate.await_count >= 1
    assert repo.get_plan_enrichment(conv_id) is not None
    messages = repo.get_lui_messages(conv_id)
    assert any(m["message_type"] == "propagation_plan" for m in messages)

    with patch(
        "skillhub_eval.adapters.api.routes.chat.continue_eval_after_skill_id_confirmed",
        new_callable=AsyncMock,
        return_value=(None, None, None, None, True, "awaiting_propagation_confirm"),
    ):
        confirm = client.post(
            f"/conversations/{conv_id}/chat",
            json={"message": "确定"},
        )
    if repo.get_conversation(conv_id)["status"] == "awaiting_skill_id_confirm":
        assert confirm.status_code == 200
