"""Wave 5 Task 4 — chat multipart, skill_id confirm, review system messages."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.case_sanitizer import SanitizerResult
from skillhub_eval.core.bundle_security import BundleSecurityScanResult
from skillhub_eval.persistence.sqlite import SqliteRepository

_VALID_BUNDLE = {
    "skill_md_text": (
        "---\n"
        "name: zip-skill\n"
        "description: 这是一个足够长的 Skill 描述，用于在 chat wave5 测试中跳过 L0 purpose 门槛。\n"
        "risk_level: low\n"
        "category: fin-research/quant-signal\n"
        "---\n"
        "# Demo\n\n"
        "This bundle has eval cases and valid metadata for wave5 chat tests.\n"
    ),
    "skill_meta": {
        "name": "zip-skill",
        "category": "fin-research/quant-signal",
        "description": "这是一个足够长的 Skill 描述，用于在 chat wave5 测试中跳过 L0 purpose 门槛。",
    },
    "risk_level_declared": "low",
    "eval_cases": [{"id": "c1", "type": "happy_path"}],
    "n_cases": 1,
    "skill_id": "zip-skill",
}


def _zip_bytes(filename: str = "ignored.zip") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", "---\nname: zip-skill\n---\n# Demo\n")
        zf.writestr("eval_cases/c1.yaml", "id: c1\ntype: happy_path\n")
    return buffer.getvalue()


@pytest.fixture()
def client_with_repo(tmp_path):
    db_path = str(tmp_path / "wave5_chat.db")
    repo = SqliteRepository(db_path)
    repo.init_db()

    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: MagicMock()
    app.dependency_overrides[get_gemini_provider] = lambda: MagicMock()

    with patch(
        "skillhub_eval.adapters.api.routes.conversations.EvaluationEngine"
    ) as mock_engine_cls:
        mock_engine_cls.return_value.run_async = AsyncMock()
        with patch(
            "skillhub_eval.adapters.api.routes.conversations.ingest_bundle",
            return_value=_VALID_BUNDLE,
        ):
            with patch(
                "skillhub_eval.adapters.api.routes.conversations.scan_bundle_security",
                return_value=BundleSecurityScanResult(intake_status="passed"),
            ):
                with patch(
                    "skillhub_eval.adapters.api.routes.conversations.CaseSanitizer"
                ) as mock_san:
                    mock_san.return_value.run.return_value = SanitizerResult(
                        broken_moved=0,
                        invalid_type_count=0,
                        gap_by_type={"happy_path": 0},
                        needs_propagation=False,
                        existing_counts={"happy_path": 1},
                    )
                    with TestClient(app, raise_server_exceptions=True) as c:
                        yield c, repo


def test_chat_multipart_zip_auto_id_requires_confirm(client_with_repo, tmp_path):
    client, repo = client_with_repo
    with patch("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging")):
        conv_id = client.post("/conversations/new").json()["conversation_id"]
        resp = client.post(
            f"/conversations/{conv_id}/chat",
            files={"bundle_zip": ("my-skill.zip", _zip_bytes(), "application/zip")},
            data={"message": ""},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bootstrap_status"] == "awaiting_skill_id_confirm"
    conv = repo.get_conversation(conv_id)
    assert conv["status"] == "awaiting_skill_id_confirm"
    assert conv["skill_id"] == "zip-skill"


def test_chat_confirm_after_auto_id_starts_eval(client_with_repo, tmp_path):
    client, repo = client_with_repo
    with patch("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging")):
        conv_id = client.post("/conversations/new").json()["conversation_id"]
        client.post(
            f"/conversations/{conv_id}/chat",
            files={"bundle_zip": ("bundle.zip", _zip_bytes(), "application/zip")},
            data={"message": ""},
        )
        resp = client.post(
            f"/conversations/{conv_id}/chat",
            json={"message": "确认"},
        )
    assert resp.status_code == 200
    assert resp.json()["bootstrap_status"] == "accepted"
    assert resp.json()["new_run_id"]
    conv = repo.get_conversation(conv_id)
    assert conv["status"] == "active"
    assert conv["active_run_id"]


def test_chat_zip_with_explicit_skill_id_skips_confirm(client_with_repo, tmp_path):
    client, repo = client_with_repo
    with patch("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging")):
        conv_id = client.post("/conversations/new").json()["conversation_id"]
        resp = client.post(
            f"/conversations/{conv_id}/chat",
            files={"bundle_zip": ("bundle.zip", _zip_bytes(), "application/zip")},
            data={"message": "skill_id: explicit-skill"},
        )
    assert resp.status_code == 200
    assert resp.json()["bootstrap_status"] == "accepted"
    conv = repo.get_conversation(conv_id)
    assert conv["skill_id"] == "explicit-skill"


def test_review_approve_appends_system_message(client_with_repo):
    client, repo = client_with_repo
    conv_id = repo.create_conversation(skill_id="s1", source="upload")
    run_id = repo.create_run(
        skill_id="s1",
        skill_bundle_path="/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    repo.set_human_review_required(run_id, True, ["MODEL_DISAGREEMENT_R5"])
    repo.update_status(run_id, "awaiting_human_review")

    resp = client.post(
        f"/eval/review/{run_id}",
        json={"action": "approve", "operator": "self", "comment": "ok"},
    )
    assert resp.status_code == 200
    messages = repo.get_lui_messages(conv_id)
    system_msgs = [m for m in messages if m["role"] == "system"]
    assert any("专家已批准" in m["content"] for m in system_msgs)
