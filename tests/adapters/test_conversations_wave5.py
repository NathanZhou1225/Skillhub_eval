"""Wave 5 Task 3 — conversation list, new session, bootstrap, history conversation API."""

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
    "skill_md_text": "---\nname: from-skill-md\n---\n# Demo Skill\n",
    "skill_meta": {
        "name": "from-skill-md",
        "category": "fin-research/quant-signal",
        "description": "这是一个足够长的 Skill 描述，用于在 complete cases 测试中跳过 L0 purpose 澄清门槛。",
    },
    "risk_level_declared": "low",
    "eval_cases": [{"id": "c1", "type": "happy_path"}],
    "n_cases": 1,
    "skill_id": "from-skill-md",
}


def _make_zip_bytes(
    *,
    skill_md: str = "---\nname: from-skill-md\n---\n# Demo Skill\n",
    filename: str = "my-bundle.zip",
) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", skill_md)
        zf.writestr("eval_cases/case_001.yaml", "id: case_001\ntype: happy_path\n")
    return buffer.getvalue(), filename


def _make_sanitizer_result() -> SanitizerResult:
    return SanitizerResult(
        broken_moved=0,
        invalid_type_count=0,
        gap_by_type={"happy_path": 0},
        needs_propagation=False,
        existing_counts={"happy_path": 1},
    )


@pytest.fixture()
def client_with_repo(tmp_path):
    db_path = str(tmp_path / "wave5_api.db")
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
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c, repo


def test_new_conversation_returns_welcome(client_with_repo):
    client, repo = client_with_repo
    resp = client.post("/conversations/new")
    assert resp.status_code == 201
    conv_id = resp.json()["conversation_id"]
    assert conv_id

    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["skill_id"] == ""

    messages = repo.get_lui_messages(conv_id)
    assert len(messages) == 1
    assert messages[0]["message_type"] == "welcome"
    assert messages[0]["payload_json"] == {"expected_inputs": ["skill_id", "bundle"]}


def test_list_conversations_includes_sessions(client_with_repo):
    client, repo = client_with_repo
    conv_a = repo.create_conversation(skill_id="skill-a", source="upload")
    conv_b = repo.create_conversation(skill_id="skill-b", source="upload")
    repo.append_lui_message(conv_a, "agent", "hello a")
    repo.append_lui_message(conv_b, "system", "pending soon")

    resp = client.get("/conversations?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["conversations"]) == 2
    by_id = {c["conversation_id"]: c for c in body["conversations"]}
    assert by_id[conv_a]["last_message_preview"] == "hello a"
    assert by_id[conv_a]["lui_message_count"] == 1


def test_list_conversations_pending_review_filter(client_with_repo):
    client, repo = client_with_repo
    conv_pending = repo.create_conversation(skill_id="skill-p", source="upload")
    conv_ok = repo.create_conversation(skill_id="skill-ok", source="upload")

    run_id = repo.create_run(
        skill_id="skill-p",
        skill_bundle_path="/tmp/p",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_pending,
    )
    with repo._conn() as conn:
        conn.execute(
            "UPDATE evaluation_runs SET status=?, human_review_required=1 WHERE run_id=?",
            ("awaiting_human_review", run_id),
        )

    resp = client.get("/conversations?pending_review=true")
    assert resp.status_code == 200
    ids = {c["conversation_id"] for c in resp.json()["conversations"]}
    assert conv_pending in ids
    assert conv_ok not in ids


def test_bootstrap_auto_identify_requires_confirm(client_with_repo, tmp_path, monkeypatch):
    client, repo = client_with_repo
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    new_resp = client.post("/conversations/new")
    conv_id = new_resp.json()["conversation_id"]
    payload, filename = _make_zip_bytes()

    resp = client.post(
        f"/conversations/{conv_id}/bootstrap",
        files={"bundle_zip": (filename, payload, "application/zip")},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "awaiting_skill_id_confirm"
    assert body["run_id"] is None
    assert body["skill_id"] == "from-skill-md"
    assert body["skill_id_source"] == "skill_md"
    assert body.get("staging_path")
    assert conv_id in str(body["staging_path"]).replace("\\", "/")

    conv = repo.get_conversation(conv_id)
    assert conv["status"] == "awaiting_skill_id_confirm"
    messages = repo.get_lui_messages(conv_id)
    assert any("识别到你的 Skill 名称" in m["content"] for m in messages)


def test_bootstrap_explicit_skill_id_skips_confirm(
    client_with_repo, tmp_path, monkeypatch
):
    client, repo = client_with_repo
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))
    passed = BundleSecurityScanResult(intake_status="passed")

    new_resp = client.post("/conversations/new")
    conv_id = new_resp.json()["conversation_id"]
    payload, filename = _make_zip_bytes()

    with (
        patch(
            "skillhub_eval.adapters.api.routes.conversations.ingest_bundle",
            return_value=_VALID_BUNDLE,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.scan_bundle_security",
            return_value=passed,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CaseSanitizer",
            return_value=MagicMock(run=MagicMock(return_value=_make_sanitizer_result())),
        ),
    ):
        resp = client.post(
            f"/conversations/{conv_id}/bootstrap",
            data={"skill_id": "explicit-skill", "source": "upload"},
            files={"bundle_zip": (filename, payload, "application/zip")},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["run_id"]
    assert body["skill_id"] == "explicit-skill"
    assert body["skill_id_source"] == "explicit_request"
    assert body.get("staging_path")
    assert conv_id in str(body["staging_path"]).replace("\\", "/")

    messages = repo.get_lui_messages(conv_id)
    assert any("已开始评估" in m["content"] for m in messages)


def test_bootstrap_user_message_skill_id_skips_confirm(
    client_with_repo, tmp_path, monkeypatch
):
    client, repo = client_with_repo
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))
    passed = BundleSecurityScanResult(intake_status="passed")

    new_resp = client.post("/conversations/new")
    conv_id = new_resp.json()["conversation_id"]
    payload, filename = _make_zip_bytes()

    with (
        patch(
            "skillhub_eval.adapters.api.routes.conversations.ingest_bundle",
            return_value=_VALID_BUNDLE,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.scan_bundle_security",
            return_value=passed,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CaseSanitizer",
            return_value=MagicMock(run=MagicMock(return_value=_make_sanitizer_result())),
        ),
    ):
        resp = client.post(
            f"/conversations/{conv_id}/bootstrap",
            data={"user_message": "skill_id: user-declared", "source": "upload"},
            files={"bundle_zip": (filename, payload, "application/zip")},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["skill_id"] == "user-declared"
    assert body["skill_id_source"] == "user_message"


def test_bootstrap_security_blocked_writes_system_message(
    client_with_repo, tmp_path, monkeypatch
):
    client, repo = client_with_repo
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))
    blocked = BundleSecurityScanResult(intake_status="blocked", intake_findings=[{"source": "skill_bundle"}])

    new_resp = client.post("/conversations/new")
    conv_id = new_resp.json()["conversation_id"]
    payload, filename = _make_zip_bytes()

    with (
        patch(
            "skillhub_eval.adapters.api.routes.conversations.ingest_bundle",
            return_value=_VALID_BUNDLE,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.scan_bundle_security",
            return_value=blocked,
        ),
    ):
        resp = client.post(
            f"/conversations/{conv_id}/bootstrap",
            data={"skill_id": "explicit-skill", "source": "upload"},
            files={"bundle_zip": (filename, payload, "application/zip")},
        )

    assert resp.status_code == 422
    messages = repo.get_lui_messages(conv_id)
    assert any(m.get("message_type") == "security_blocked" for m in messages)
    assert any("安全门禁未通过" in m["content"] for m in messages)


def test_bootstrap_local_ref_forbidden_without_demo(client_with_repo):
    client, repo = client_with_repo
    new_resp = client.post("/conversations/new")
    conv_id = new_resp.json()["conversation_id"]

    resp = client.post(
        f"/conversations/{conv_id}/bootstrap",
        json={
            "skill_id": "demo-skill",
            "source": "local_ref",
            "skill_bundle_path": "/tmp/demo",
        },
    )
    assert resp.status_code == 403


def test_eval_history_includes_conversation_fields(client_with_repo):
    client, repo = client_with_repo
    conv_id = repo.create_conversation(skill_id="skill-h", source="upload")
    repo.append_lui_message(conv_id, "system", "history preview")
    run_id = repo.create_run(
        skill_id="skill-h",
        skill_bundle_path="/tmp/h",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )

    resp = client.get("/eval/history")
    assert resp.status_code == 200
    run = next(r for r in resp.json()["runs"] if r["run_id"] == run_id)
    assert run["conversation_id"] == conv_id
    assert run["lui_message_count"] == 1
    assert run["last_message_preview"] == "history preview"


def test_eval_history_conversation_endpoint(client_with_repo):
    client, repo = client_with_repo
    conv_id = repo.create_conversation(skill_id="skill-c", source="upload")
    repo.append_lui_message(conv_id, "user", "hello")
    repo.append_lui_message(conv_id, "agent", "hi there")
    run_id = repo.create_run(
        skill_id="skill-c",
        skill_bundle_path="/tmp/c",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )

    resp = client.get(f"/eval/history/{run_id}/conversation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation_id"] == conv_id
    assert body["message_count"] == 2
    assert len(body["messages"]) == 2


def test_eval_history_conversation_404_without_conversation(client_with_repo):
    client, repo = client_with_repo
    run_id = repo.create_run(
        skill_id="skill-legacy",
        skill_bundle_path="/tmp/legacy",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    resp = client.get(f"/eval/history/{run_id}/conversation")
    assert resp.status_code == 404
