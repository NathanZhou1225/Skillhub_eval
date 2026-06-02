"""
Task 9 — FastAPI route tests.

C-4 compliance:
  ALL tests use app.dependency_overrides to inject an isolated tmp SQLite repo.
  No test touches the real DB or the real LLM providers.
  Each test function gets its own clean repository via the `client` fixture.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.persistence.sqlite import SqliteRepository


# ─── fake provider ────────────────────────────────────────────────────────────

class FakeProvider:
    async def judge(self, prompt: str) -> dict:
        return {
            "sub_scores": {
                "step_completeness": {
                    "score": 88,
                    "pass": True,
                    "reason": "ok",
                    "evidence_refs": [],
                }
            },
            "confidence": "high",
            "dimension_notes": "",
        }


# ─── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def client(tmp_path):
    """
    C-4: per-test isolated client.
    dependency_overrides[get_repo] injects a fresh SQLite in a tmp dir.
    No global state is contaminated between tests.
    """
    db_path = str(tmp_path / "test.db")
    repo = SqliteRepository(db_path)
    repo.init_db()

    fake_provider = FakeProvider()

    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: fake_provider
    app.dependency_overrides[get_gemini_provider] = lambda: fake_provider

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture()
def client_with_repo(tmp_path):
    """Same as `client` but also exposes the repo for direct inspection."""
    db_path = str(tmp_path / "test.db")
    repo = SqliteRepository(db_path)
    repo.init_db()
    fake_provider = FakeProvider()

    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: fake_provider
    app.dependency_overrides[get_gemini_provider] = lambda: fake_provider

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, repo


# ─── /health ──────────────────────────────────────────────────────────────────

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ─── POST /eval/run ───────────────────────────────────────────────────────────

def test_post_eval_run_returns_202_and_run_id(client):
    payload = {
        "skill_id": "skill.abc",
        "skill_bundle_path": "/tmp/nonexistent",
        "bundle_state": "confirmed",
        "evaluation_mode": "capability_full",
    }
    resp = client.post("/eval/run", json=payload)
    assert resp.status_code == 202
    body = resp.json()
    assert "run_id" in body
    assert body["status"] == "pending"
    assert body["run_id"]


def test_post_eval_run_invalid_bundle_state_returns_422(client):
    payload = {
        "skill_id": "skill.abc",
        "skill_bundle_path": "/tmp/x",
        "bundle_state": "not_a_real_state",
        "evaluation_mode": "capability_full",
    }
    resp = client.post("/eval/run", json=payload)
    assert resp.status_code == 422


def test_post_eval_run_missing_skill_id_returns_422(client):
    payload = {
        "skill_bundle_path": "/tmp/x",
        "bundle_state": "confirmed",
        "evaluation_mode": "capability_full",
    }
    resp = client.post("/eval/run", json=payload)
    assert resp.status_code == 422


# ─── GET /eval/report/{run_id} ────────────────────────────────────────────────

def test_get_report_not_found(client):
    resp = client.get("/eval/report/nonexistent-id")
    assert resp.status_code == 404


def test_get_report_returns_status_after_run(client_with_repo):
    c, repo = client_with_repo
    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    resp = c.get(f"/eval/report/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == run_id
    assert "status" in body


# ─── GET /eval/history ────────────────────────────────────────────────────────

def test_get_history_empty(client):
    resp = client.get("/eval/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["runs"] == []


def test_get_history_returns_runs(client_with_repo):
    c, repo = client_with_repo
    for i in range(3):
        repo.create_run(
            skill_id=f"skill.{i}",
            skill_bundle_path="/tmp/x",
            bundle_state="confirmed",
            evaluation_mode="capability_full",
        )
    resp = c.get("/eval/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3


def test_get_history_human_review_filter(client_with_repo):
    c, repo = client_with_repo
    run_id = repo.create_run(
        skill_id="skill.flag",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    repo.set_human_review_required(run_id, True, ["MODEL_DISAGREEMENT_R5"])
    # another run without flag
    repo.create_run(
        skill_id="skill.ok",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    resp = c.get("/eval/history?human_review_only=true")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["runs"][0]["skill_id"] == "skill.flag"


# ─── POST /bundle/{skill_id}/confirm ─────────────────────────────────────────

def test_bundle_confirm_persists_fields(client_with_repo):
    c, repo = client_with_repo
    payload = {
        "confirmed_fields": {
            "negative_prompts": "do not leak PII",
            "error_handling": "return structured error",
        },
        "confirmed_cases": [],
        "operator": "alice",
    }
    resp = c.post("/bundle/skill.test/confirm", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["skill_id"] == "skill.test"
    assert body["operator"] == "alice"
    assert body["confirmed_count"] == 2
    assert "next_step" in body


def test_bundle_confirm_empty_fields_returns_422(client):
    payload = {
        "confirmed_fields": {},
        "operator": "alice",
    }
    resp = client.post("/bundle/skill.test/confirm", json=payload)
    assert resp.status_code == 422


# ─── POST /eval/review/{run_id} ───────────────────────────────────────────────

def test_review_approve_updates_status(client_with_repo):
    c, repo = client_with_repo
    run_id = repo.create_run(
        skill_id="skill.warn",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    repo.set_human_review_required(run_id, True, ["MODEL_DISAGREEMENT_R5"])

    resp = c.post(f"/eval/review/{run_id}", json={
        "action": "approve",
        "operator": "expert_bob",
        "comment": "LGTM after review",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "approve"
    assert body["review_status"] == "pass"

    run = repo.get_run(run_id)
    assert run["review_status"] == "pass"


def test_review_reject_updates_status(client_with_repo):
    c, repo = client_with_repo
    run_id = repo.create_run(
        skill_id="skill.warn",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    repo.set_human_review_required(run_id, True, ["MODEL_DISAGREEMENT_R5"])

    resp = c.post(f"/eval/review/{run_id}", json={
        "action": "reject",
        "operator": "expert_bob",
        "comment": "Security risk detected",
    })
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "fail"


def test_review_run_not_found_returns_404(client):
    resp = client.post("/eval/review/bad-id", json={
        "action": "approve",
        "operator": "alice",
    })
    assert resp.status_code == 404


def test_review_run_not_flagged_returns_409(client_with_repo):
    c, repo = client_with_repo
    run_id = repo.create_run(
        skill_id="skill.ok",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    resp = c.post(f"/eval/review/{run_id}", json={
        "action": "approve",
        "operator": "alice",
    })
    assert resp.status_code == 409


def test_review_invalid_action_returns_422(client_with_repo):
    c, repo = client_with_repo
    run_id = repo.create_run(
        skill_id="skill.x",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    repo.set_human_review_required(run_id, True, ["MODEL_DISAGREEMENT_R5"])
    resp = c.post(f"/eval/review/{run_id}", json={
        "action": "maybe",
        "operator": "alice",
    })
    assert resp.status_code == 422
