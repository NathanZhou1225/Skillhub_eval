from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.persistence.sqlite import SqliteRepository


class _FakeProvider:
    async def judge(self, prompt: str) -> dict:
        return {"intent": "explain_only", "reply": "ok", "patch": None}


@pytest.fixture()
def client_with_repo(tmp_path):
    db_path = str(tmp_path / "review.db")
    repo = SqliteRepository(db_path)
    repo.init_db()
    provider = _FakeProvider()

    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: provider
    app.dependency_overrides[get_gemini_provider] = lambda: provider
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, repo


def _create_reviewable_run(repo: SqliteRepository, conversation_id: str | None = None) -> str:
    run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path="/tmp/bundle",
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conversation_id,
    )
    repo.set_human_review_required(run_id, True, ["MODEL_DISAGREEMENT_R5"])
    return run_id


def test_review_reject_unfreezes_conversation_and_resets_counters(client_with_repo):
    client, repo = client_with_repo
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    repo.update_conversation_status(conv_id, "frozen")
    repo.set_conversation_auto_confirmed(conv_id, True)
    repo.increment_auto_run_count(conv_id)
    repo.increment_auto_run_count(conv_id)
    run_id = _create_reviewable_run(repo, conversation_id=conv_id)

    resp = client.post(
        f"/eval/review/{run_id}",
        json={"action": "reject", "operator": "expert", "comment": "缺少关键风控约束"},
    )

    assert resp.status_code == 200
    assert resp.json()["review_status"] == "fail"
    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["status"] == "active"
    assert conv["auto_run_count"] == 0
    assert conv["auto_confirmed"] == 0
    msgs = repo.get_lui_messages(conv_id)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "system"
    assert "专家已驳回" in msgs[0]["content"]
    assert "缺少关键风控约束" in msgs[0]["content"]


def test_review_approve_only_resets_auto_run_count(client_with_repo):
    client, repo = client_with_repo
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    repo.update_conversation_status(conv_id, "frozen")
    repo.set_conversation_auto_confirmed(conv_id, True)
    repo.increment_auto_run_count(conv_id)
    run_id = _create_reviewable_run(repo, conversation_id=conv_id)

    resp = client.post(
        f"/eval/review/{run_id}",
        json={"action": "approve", "operator": "expert", "comment": "通过"},
    )

    assert resp.status_code == 200
    assert resp.json()["review_status"] == "pass"
    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["auto_run_count"] == 0
    assert conv["status"] == "frozen"
    assert conv["auto_confirmed"] == 1
    msgs = repo.get_lui_messages(conv_id)
    assert len(msgs) == 1
    assert msgs[0]["role"] == "system"
    assert "专家已批准" in msgs[0]["content"]


def test_review_without_conversation_id_keeps_existing_behavior(client_with_repo):
    client, repo = client_with_repo
    run_id = _create_reviewable_run(repo, conversation_id=None)

    resp = client.post(
        f"/eval/review/{run_id}",
        json={"action": "approve", "operator": "expert", "comment": "legacy"},
    )

    assert resp.status_code == 200
    assert resp.json()["review_status"] == "pass"
    run = repo.get_run(run_id)
    assert run is not None
    assert run["status"] == "completed"
    assert run["review_status"] == "pass"
