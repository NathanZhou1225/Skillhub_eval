"""Wave 5.3 Task 3 — bootstrap always enriches propagation plan."""

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


def _make_zip_bytes(*, skill_md: str) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", skill_md)
    return buffer.getvalue(), "bundle.zip"


@pytest.fixture()
def client_with_repo(tmp_path):
    repo = SqliteRepository(str(tmp_path / "w53_enrich.db"))
    repo.init_db()

    mock_ds = MagicMock()
    mock_ds.generate = AsyncMock(
        return_value=json.dumps(
            {
                "rows": [
                    {
                        "type": "happy_path",
                        "tests_what": "主流程",
                        "business_expectation": "Skill 专属预期 A",
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
    ) as mock_engine_cls:
        mock_engine_cls.return_value.run_async = AsyncMock()
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client, repo, mock_ds


def test_bootstrap_deferred_plan_is_enriched_and_cached(
    client_with_repo, tmp_path, monkeypatch
):
    client, repo, mock_ds = client_with_repo
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    skill_md = (
        "---\n"
        "name: enrich-skill\n"
        "description: 这是一个用于测试 bootstrap enrich 的 Skill，描述足够长以满足 L0 门槛。\n"
        "risk_level: low\n"
        "category: fin-research/quant-signal\n"
        "---\n"
        "# Enrich Skill\n"
    )
    payload, filename = _make_zip_bytes(skill_md=skill_md)

    conv_id = client.post("/conversations/new").json()["conversation_id"]
    resp = client.post(
        f"/conversations/{conv_id}/bootstrap",
        data={"skill_id": "enrich-skill", "source": "upload"},
        files={"bundle_zip": (filename, payload, "application/zip")},
    )
    assert resp.status_code == 202
    assert resp.json()["propagation_deferred"] is True
    mock_ds.generate.assert_awaited()

    messages = repo.get_lui_messages(conv_id)
    plan_msg = next(m for m in messages if m["message_type"] == "propagation_plan")
    plan = plan_msg["payload_json"]
    if isinstance(plan, str):
        plan = json.loads(plan)
    assert plan.get("enrichment_status") in ("ok", "degraded", "skipped")
    cached = repo.get_plan_enrichment(conv_id)
    assert cached is not None
    assert cached.get("skill_id")
