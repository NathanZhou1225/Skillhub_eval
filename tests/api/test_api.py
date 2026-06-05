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

def test_get_bundle_gaps_not_found(client):
    resp = client.get("/bundle/skill.missing/gaps")
    assert resp.status_code == 404


def test_get_bundle_gaps_returns_snapshot_and_templates(client_with_repo):
    c, repo = client_with_repo
    run_id = repo.create_run(
        skill_id="grill-me",
        skill_bundle_path="/tmp/grill-me",
        bundle_state="minimal",
        evaluation_mode="capability_full",
    )
    repo.save_gaps(run_id, {
        "skill_id": "grill-me",
        "run_id": run_id,
        "gaps": [
            {"field_path": "eval_cases", "severity": "block", "message": "missing"},
        ],
        "required_actions": ["创建 eval_cases/ 目录"],
    })

    resp = c.get("/bundle/grill-me/gaps")
    assert resp.status_code == 200
    body = resp.json()
    assert body["skill_id"] == "grill-me"
    assert body["gaps"][0]["field_path"] == "eval_cases"
    assert body["required_actions"]
    assert "eval_case" in body["templates"]
    assert "sample_io" in body["templates"]
    assert "user_intent:" in body["templates"]["eval_case"]


def test_get_bundle_gaps_includes_confirmations(client_with_repo):
    c, repo = client_with_repo
    run_id = repo.create_run(
        skill_id="skill.gaps",
        skill_bundle_path="/tmp/x",
        bundle_state="minimal",
        evaluation_mode="capability_full",
    )
    repo.save_gaps(run_id, {
        "skill_id": "skill.gaps",
        "run_id": run_id,
        "gaps": [],
        "required_actions": [],
    })
    repo.save_confirmation("skill.gaps", "negative_prompts", "no PII", "alice")

    resp = c.get("/bundle/skill.gaps/gaps")
    assert resp.status_code == 200
    assert resp.json()["confirmed_fields"]["negative_prompts"] == "no PII"


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

def test_get_report_includes_provider_summary(client_with_repo):
    from skillhub_eval.core.schemas import (
        EvaluationReport,
        HumanReview,
        ProviderSummary,
    )

    c, repo = client_with_repo
    run_id = repo.create_run(
        skill_id="skill.r5",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    repo.save_report(
        run_id,
        EvaluationReport(
            run_id=run_id,
            skill_id="skill.r5",
            skill_bundle_path="/tmp/x",
            bundle_state="confirmed",
            evaluation_mode="capability_full",
            status="awaiting_human_review",
            review_status="warn",
            score_total=None,
            score_total_source="null_due_to_disagreement",
            reason_codes=["MODEL_DISAGREEMENT_R5"],
            provider_summary=ProviderSummary(
                deepseek_score=88.0,
                gemini_score=60.0,
                score_gap=28.0,
                r5_triggered=True,
                per_case=[],
            ),
            human_review=HumanReview(required=True, trigger_codes=["MODEL_DISAGREEMENT_R5"]),
        ),
    )

    resp = c.get(f"/eval/report/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider_summary"] is not None
    assert body["provider_summary"]["r5_triggered"] is True
    assert body["report"]["provider_summary"]["deepseek_score"] == 88.0


def test_get_report_includes_stage_timing(client_with_repo):
    c, repo = client_with_repo
    run_id = repo.create_run(
        skill_id="skill.timing",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    repo.log_event(run_id, "stage_timing", {"stage": "level0_checking", "ms": 80})
    repo.log_event(run_id, "stage_timing", {"stage": "model_judging", "ms": 12000})
    repo.append_stage(run_id, "level0_checking")
    repo.append_stage(run_id, "model_judging")

    resp = c.get(f"/eval/report/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["stage_timings"]) == 2
    assert body["timing_summary"]["model_judging_ms"] == 12000
    assert "level0_checking" in body["stage_progress"]


def test_review_approve_updates_status_and_report(client_with_repo):
    from skillhub_eval.core.schemas import (
        EvaluationReport,
        HumanReview,
        ProviderSummary,
    )

    c, repo = client_with_repo
    run_id = repo.create_run(
        skill_id="skill.warn",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    repo.set_human_review_required(run_id, True, ["MODEL_DISAGREEMENT_R5"])
    repo.save_report(
        run_id,
        EvaluationReport(
            run_id=run_id,
            skill_id="skill.warn",
            skill_bundle_path="/tmp/x",
            bundle_state="confirmed",
            evaluation_mode="capability_full",
            status="awaiting_human_review",
            review_status="warn",
            provider_summary=ProviderSummary(
                deepseek_score=88.0, gemini_score=60.0, r5_triggered=True,
            ),
            human_review=HumanReview(required=True),
        ),
    )

    resp = c.post(f"/eval/review/{run_id}", json={
        "action": "approve",
        "operator": "expert_bob",
        "comment": "LGTM after review",
    })
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "pass"

    report = repo.get_report(run_id)
    assert report["human_review"]["reviewer_action"] == "approve"
    assert report["human_review"]["operator"] == "expert_bob"
    assert report["provider_summary"]["deepseek_score"] == 88.0


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
