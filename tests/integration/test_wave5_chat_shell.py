"""Wave 5 Task 6 — Chat-First shell E2E integration tests."""

from __future__ import annotations

import io
import json
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.case_sanitizer import SanitizerResult
from skillhub_eval.core.chat_notifications import (
    append_readiness_result_message,
    append_rich_report_message,
)
from skillhub_eval.core.bundle_security import BundleSecurityScanResult
from skillhub_eval.persistence.sqlite import SqliteRepository

_VALID_BUNDLE = {
    "skill_md_text": (
        "---\n"
        "id: zip-skill\n"
        "name: zip-skill\n"
        "risk_level: low\n"
        "description: 这是一个足够长的 Skill 描述，用于在 complete cases 测试中跳过 L0 purpose 澄清门槛。\n"
        "category: fin-research/quant-signal\n"
        "negative_prompts: np\n"
        "error_handling: eh\n"
        "permission_scope: ps\n"
        "security_notes: sn\n"
        "---\n"
        "# Zip\n" + ("x\n" * 50)
    ),
    "skill_meta": {
        "name": "zip-skill",
        "category": "fin-research/quant-signal",
        "description": "这是一个足够长的 Skill 描述，用于在 complete cases 测试中跳过 L0 purpose 澄清门槛。",
    },
    "risk_level_declared": "low",
    "eval_cases": [{"id": "c1", "type": "happy_path"}],
    "n_cases": 1,
    "skill_id": "zip-skill",
}


def _zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", _VALID_BUNDLE["skill_md_text"])
        zf.writestr(
            "eval_cases/c1.yaml",
            yaml.safe_dump(
                {
                    "id": "c1",
                    "type": "happy_path",
                    "user_intent": "intent",
                    "input_template": "input",
                    "expected_behavior": "behavior",
                },
                allow_unicode=True,
                sort_keys=False,
            ),
        )
        zf.writestr("sample_io/c1.json", '{"input":"x","output":"y"}')
    return buffer.getvalue()


def _seed_report(repo: SqliteRepository, run_id: str) -> None:
    report = {
        "skill_summary": {"highlights": "亮点", "weaknesses": "不足"},
        "gaps": [],
        "security_status": "passed",
    }
    with repo._conn() as conn:
        conn.execute(
            "UPDATE evaluation_runs SET report_json=? WHERE run_id=?",
            (json.dumps(report, ensure_ascii=False), run_id),
        )


@pytest.fixture()
def client_with_repo(tmp_path, monkeypatch):
    repo = SqliteRepository(str(tmp_path / "wave5_e2e.db"))
    repo.init_db()
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    async def _fast_run_async(self, run_id, skill_bundle_path, bundle_state, evaluation_mode):
        run = self.repo.get_run(run_id) or {}
        conv_id = run.get("conversation_id")
        self.repo.update_status(run_id, "completed", review_status="warn")
        _seed_report(self.repo, run_id)
        if conv_id:
            eval_mode = str(run.get("evaluation_mode", ""))
            if eval_mode == "degraded":
                append_readiness_result_message(str(conv_id), run_id, self.repo)
            else:
                append_rich_report_message(str(conv_id), run_id, self.repo)

    import skillhub_eval.adapters.api.routes.conversations as conversations_route
    import skillhub_eval.core.engine as engine_module

    monkeypatch.setattr(conversations_route.EvaluationEngine, "run_async", _fast_run_async)
    monkeypatch.setattr(engine_module.EvaluationEngine, "run_async", _fast_run_async)

    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: MagicMock()
    app.dependency_overrides[get_gemini_provider] = lambda: MagicMock()

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
                with patch(
                    "skillhub_eval.adapters.api.routes.chat.ingest_bundle",
                    return_value=_VALID_BUNDLE,
                ):
                    with TestClient(app, raise_server_exceptions=True) as client:
                        yield client, repo, tmp_path


def test_new_session_welcome_message(client_with_repo):
    client, repo, _ = client_with_repo
    resp = client.post("/conversations/new")
    assert resp.status_code == 201
    conv_id = resp.json()["conversation_id"]
    messages = repo.get_lui_messages(conv_id)
    assert any(m["message_type"] == "welcome" for m in messages)


def test_zip_bootstrap_confirm_then_rich_report(client_with_repo):
    client, repo, _ = client_with_repo
    conv_id = client.post("/conversations/new").json()["conversation_id"]

    upload = client.post(
        f"/conversations/{conv_id}/chat",
        files={"bundle_zip": ("bundle.zip", _zip_bytes(), "application/zip")},
        data={"message": ""},
    )
    assert upload.status_code == 200
    assert upload.json()["bootstrap_status"] == "awaiting_skill_id_confirm"

    confirm = client.post(f"/conversations/{conv_id}/chat", json={"message": "确认"})
    assert confirm.status_code == 200
    assert confirm.json()["bootstrap_status"] == "accepted"
    run_id = confirm.json()["new_run_id"]
    assert run_id

    messages = repo.get_lui_messages(conv_id)
    assert any(m.get("message_type") == "assessment_gate_result" for m in messages)
    assert any(
        m.get("message_type") == "rich_report" and str(m.get("run_id")) == run_id
        for m in messages
    )


def test_human_review_approve_appends_system_message(client_with_repo):
    client, repo, tmp_path = client_with_repo
    conv_id = client.post("/conversations/new").json()["conversation_id"]
    staging = tmp_path / "staging" / conv_id
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "SKILL.md").write_text(_VALID_BUNDLE["skill_md_text"], encoding="utf-8")

    run_id = repo.create_run(
        skill_id="zip-skill",
        skill_bundle_path=str(staging),
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    repo.set_human_review_required(run_id, True, ["MODEL_DISAGREEMENT_R5"])
    repo.update_status(run_id, "awaiting_human_review")
    repo.update_conversation_status(conv_id, "frozen")

    resp = client.post(
        f"/eval/review/{run_id}",
        json={"action": "approve", "operator": "self", "comment": "ok"},
    )
    assert resp.status_code == 200
    messages = repo.get_lui_messages(conv_id)
    assert any("专家已批准" in m["content"] for m in messages)
    conv = repo.get_conversation(conv_id)
    assert conv["auto_run_count"] == 0


def test_history_includes_conversation_fields_and_endpoint(client_with_repo):
    client, repo, _ = client_with_repo
    conv_id = client.post("/conversations/new").json()["conversation_id"]
    repo.append_lui_message(conv_id, "user", "hello history")
    run_id = repo.create_run(
        skill_id="zip-skill",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, "completed")

    hist = client.get("/eval/history?limit=10")
    assert hist.status_code == 200
    row = next(r for r in hist.json()["runs"] if r["run_id"] == run_id)
    assert row["conversation_id"] == conv_id
    assert row["lui_message_count"] >= 1
    assert row["last_message_preview"]

    conv_resp = client.get(f"/eval/history/{run_id}/conversation")
    assert conv_resp.status_code == 200
    body = conv_resp.json()
    assert body["conversation_id"] == conv_id
    assert body["message_count"] >= 1
    assert any(m["content"] == "hello history" for m in body["messages"])


def test_demo_local_ref_bootstrap_when_enabled(client_with_repo, tmp_path, monkeypatch):
    client, repo, _ = client_with_repo
    bundle_dir = tmp_path / "local_bundle"
    bundle_dir.mkdir()
    (bundle_dir / "SKILL.md").write_text(_VALID_BUNDLE["skill_md_text"], encoding="utf-8")
    (bundle_dir / "eval_cases").mkdir()
    (bundle_dir / "eval_cases" / "c1.yaml").write_text("id: c1\ntype: happy_path\n", encoding="utf-8")

    monkeypatch.setattr("skillhub_eval.settings.settings.demo_allow_local_ref", True)

    conv_id = client.post("/conversations/new").json()["conversation_id"]
    resp = client.post(
        f"/conversations/{conv_id}/bootstrap",
        json={
            "source": "local_ref",
            "skill_bundle_path": str(bundle_dir),
            "user_message": "skill_id: zip-skill",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["run_id"]
    conv = repo.get_conversation(conv_id)
    assert conv["skill_id"] == "zip-skill"
