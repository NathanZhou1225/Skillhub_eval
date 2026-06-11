from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.lui_agent import LuiResponse
from skillhub_eval.persistence.sqlite import SqliteRepository


class _FakeProvider:
    async def judge(self, prompt: str) -> dict:
        return {"intent": "explain_only", "reply": "ok", "patch": None}


def _write_bundle(root: Path, *, case_types: list[str] | None = None) -> Path:
    types = case_types or ["happy_path", "happy_path", "happy_path"]
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        "---\n"
        "id: demo.skill\n"
        "name: demo.skill\n"
        "risk_level: low\n"
        "description: 这是一个足够长的 Skill 描述，用于在 complete cases 测试中跳过 L0 purpose 澄清门槛。\n"
        "category: fin-research/quant-signal\n"
        "negative_prompts: np\n"
        "error_handling: eh\n"
        "permission_scope: ps\n"
        "security_notes: sn\n"
        "---\n"
        "# Demo\n" + ("x\n" * 50),
        encoding="utf-8",
    )
    eval_cases = root / "eval_cases"
    sample_io = root / "sample_io"
    eval_cases.mkdir(parents=True, exist_ok=True)
    sample_io.mkdir(parents=True, exist_ok=True)
    for i, case_type in enumerate(types):
        case_id = f"case_{i:02d}"
        payload = {
            "id": case_id,
            "type": case_type,
            "user_intent": "intent",
            "input_template": "input",
            "expected_behavior": "behavior",
        }
        (eval_cases / f"{case_id}.yaml").write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        (sample_io / f"{case_id}.json").write_text(
            '{"input":"x","output":"y"}',
            encoding="utf-8",
        )
    return root


def _make_zip_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "SKILL.md",
            "---\n"
            "id: zip.skill\n"
            "name: zip.skill\n"
            "risk_level: low\n"
            "description: 这是一个足够长的 Skill 描述，用于在 complete cases 测试中跳过 L0 purpose 澄清门槛。\n"
            "category: fin-research/quant-signal\n"
            "negative_prompts: np\n"
            "error_handling: eh\n"
            "permission_scope: ps\n"
            "security_notes: sn\n"
            "---\n"
            "# Zip\n" + ("x\n" * 50),
        )
        for i in range(3):
            zf.writestr(
                f"eval_cases/case_{i:02d}.yaml",
                "id: case_{i:02d}\n"
                "type: happy_path\n"
                "user_intent: intent\n"
                "input_template: input\n"
                "expected_behavior: behavior\n",
            )
            zf.writestr(f"sample_io/case_{i:02d}.json", '{"input":"x","output":"y"}')
    return buffer.getvalue()


def _count_runs(repo: SqliteRepository) -> int:
    with repo._conn() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM evaluation_runs").fetchone()[0])


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
    repo = SqliteRepository(str(tmp_path / "wave4_e2e.db"))
    repo.init_db()
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    async def _fast_run_async(
        self,
        run_id: str,
        skill_bundle_path: str,
        bundle_state,
        evaluation_mode,
    ) -> None:
        self.repo.update_status(run_id, "completed", review_status="warn", reason_codes=[])
        _seed_report(self.repo, run_id)

    import skillhub_eval.adapters.api.routes.conversations as conversations_route
    import skillhub_eval.core.engine as engine_module

    monkeypatch.setattr(conversations_route.EvaluationEngine, "run_async", _fast_run_async)
    monkeypatch.setattr(engine_module.EvaluationEngine, "run_async", _fast_run_async)

    app = create_app()
    provider = _FakeProvider()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: provider
    app.dependency_overrides[get_gemini_provider] = lambda: provider
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, repo, tmp_path


def test_session_lock_409_when_active_run_pending(client_with_repo):
    client, repo, tmp_path = client_with_repo
    staging = _write_bundle(tmp_path / "bundle_lock")
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )

    resp = client.post(f"/conversations/{conv_id}/chat", json={"message": "hello"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "SESSION_LOCKED"


def test_quota_fuse_freezes_conversation_and_marks_awaiting_review(client_with_repo, monkeypatch):
    client, repo, tmp_path = client_with_repo
    staging = _write_bundle(tmp_path / "bundle_quota")
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    repo.set_conversation_auto_confirmed(conv_id, True)
    run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, "completed")
    with repo._conn() as conn:
        conn.execute(
            "UPDATE conversations SET active_run_id=? WHERE conversation_id=?",
            (run_id, conv_id),
        )
    for _ in range(5):
        repo.increment_auto_run_count(conv_id)

    resp = client.post(
        f"/conversations/{conv_id}/chat",
        json={"message": "__SYSTEM_ACTION_CONFIRM_ALL__"},
    )
    assert resp.status_code == 200
    assert resp.json()["new_run_id"] is None

    conv = repo.get_conversation(conv_id)
    assert conv is not None and conv["status"] == "frozen"
    run = repo.get_run(run_id)
    assert run is not None
    assert run["status"] == "awaiting_human_review"
    assert run["human_review_required"] == 1
    msgs = repo.get_lui_messages(conv_id)
    assert any("最大自动修改次数" in m["content"] for m in msgs)


def test_expert_reject_unfreezes_and_resets_conversation(client_with_repo):
    client, repo, tmp_path = client_with_repo
    staging = _write_bundle(tmp_path / "bundle_reject")
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    repo.update_conversation_status(conv_id, "frozen")
    repo.set_conversation_auto_confirmed(conv_id, True)
    repo.increment_auto_run_count(conv_id)
    run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    repo.set_human_review_required(run_id, True, ["MODEL_DISAGREEMENT_R5"])
    repo.update_status(run_id, "awaiting_human_review")

    resp = client.post(
        f"/eval/review/{run_id}",
        json={"action": "reject", "operator": "expert", "comment": "need fixes"},
    )
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "fail"
    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["status"] == "active"
    assert conv["auto_run_count"] == 0
    assert conv["auto_confirmed"] == 0
    msgs = repo.get_lui_messages(conv_id)
    assert any("专家已驳回" in m["content"] for m in msgs)


def test_confirm_cases_is_annotation_only_no_new_run(client_with_repo):
    client, repo, tmp_path = client_with_repo
    staging = _write_bundle(tmp_path / "bundle_confirm_cases")
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, "completed")
    before_runs = _count_runs(repo)

    resp = client.post(
        f"/conversations/{conv_id}/confirm-cases",
        json={"case_ids": ["case_00", "case_01"]},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == ["case_00", "case_01"]
    after_runs = _count_runs(repo)
    assert after_runs == before_runs
    conv = repo.get_conversation(conv_id)
    assert conv is not None and conv["active_run_id"] == run_id
    data = yaml.safe_load((staging / "eval_cases" / "case_00.yaml").read_text(encoding="utf-8"))
    assert data["confirmed"] is True


def test_route_c_confirm_all_creates_capability_full_run(client_with_repo, monkeypatch):
    client, repo, tmp_path = client_with_repo
    staging = _write_bundle(tmp_path / "bundle_route_c")
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    run_1 = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    repo.update_status(run_1, "completed")
    _seed_report(repo, run_1)

    async def _mock_llm_respond(self, user_message, history, report, conv=None, repo=None, staging_path=None):
        return LuiResponse(
            intent="mutation",
            reply="updated",
            patch={"skill_md_updates": {"description": "updated by mutation"}},
        )

    monkeypatch.setattr("skillhub_eval.core.lui_agent.LuiAgent._llm_respond", _mock_llm_respond)

    mutation_resp = client.post(f"/conversations/{conv_id}/chat", json={"message": "update metadata"})
    assert mutation_resp.status_code == 200
    run_2 = mutation_resp.json()["new_run_id"]
    assert run_2 is not None
    run2_row = repo.get_run(run_2)
    assert run2_row is not None
    assert run2_row["evaluation_mode"] == "degraded"

    confirm_resp = client.post(
        f"/conversations/{conv_id}/chat",
        json={"message": "__SYSTEM_ACTION_CONFIRM_ALL__"},
    )
    assert confirm_resp.status_code == 200
    run_3 = confirm_resp.json()["new_run_id"]
    assert run_3 is not None
    run3_row = repo.get_run(run_3)
    assert run3_row is not None
    assert run3_row["evaluation_mode"] == "capability_full"
    assert run3_row["bundle_state"] == "confirmed"


def test_zip_upload_e2e_then_chat_works(client_with_repo):
    client, repo, _ = client_with_repo
    payload = _make_zip_bytes()

    start_resp = client.post(
        "/conversations/start",
        data={"skill_id": "zip.skill", "source": "upload"},
        files={"bundle_zip": ("bundle.zip", payload, "application/zip")},
    )
    assert start_resp.status_code == 202
    body = start_resp.json()
    conv_id = body["conversation_id"]
    run_id = body["run_id"]
    assert run_id is not None

    run = repo.get_run(run_id)
    assert run is not None and run["status"] == "completed"
    chat_resp = client.post(f"/conversations/{conv_id}/chat", json={"message": "hello after upload"})
    assert chat_resp.status_code == 200
    assert chat_resp.json()["intent"] == "explain_only"


def test_opening_marker_is_idempotent_only_one_agent_message(client_with_repo):
    client, repo, tmp_path = client_with_repo
    staging = _write_bundle(tmp_path / "bundle_opening")
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, "completed")
    _seed_report(repo, run_id)

    first = client.post(
        f"/conversations/{conv_id}/chat",
        json={"message": "__TRIGGER_AGENT_OPENING__"},
    )
    second = client.post(
        f"/conversations/{conv_id}/chat",
        json={"message": "__TRIGGER_AGENT_OPENING__"},
    )
    assert first.status_code == 200
    assert second.status_code == 200

    msgs = repo.get_lui_messages(conv_id)
    agent_msgs = [m for m in msgs if m["role"] == "agent"]
    assert len(agent_msgs) == 1
