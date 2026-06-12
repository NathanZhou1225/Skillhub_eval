"""Wave 5.4 — GET /eval/report/{run_id}/trace + has_judge_trace."""

import json

from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.persistence.sqlite import SqliteRepository


def _client_with_repo(tmp_path):
    db = str(tmp_path / "trace_api.db")
    repo = SqliteRepository(db)
    repo.init_db()
    app = create_app()
    from skillhub_eval.adapters.api import deps

    app.dependency_overrides[deps.get_repo] = lambda: repo
    return TestClient(app), repo


def test_trace_endpoint_404(tmp_path):
    client, _ = _client_with_repo(tmp_path)
    r = client.get("/eval/report/missing/trace")
    assert r.status_code == 404


def test_report_has_judge_trace_flag(tmp_path):
    client, repo = _client_with_repo(tmp_path)
    run_id = repo.create_run(
        skill_id="skill.t",
        skill_bundle_path="/b",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    r = client.get(f"/eval/report/{run_id}")
    assert r.status_code == 200
    assert r.json()["has_judge_trace"] is False

    repo.save_judge_trace(run_id, "c1", "prompt", None)
    r2 = client.get(f"/eval/report/{run_id}")
    assert r2.json()["has_judge_trace"] is True


def test_trace_endpoint_returns_cases(tmp_path):
    client, repo = _client_with_repo(tmp_path)
    run_id = repo.create_run(
        skill_id="skill.t",
        skill_bundle_path="/b",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    repo.save_judge_trace(run_id, "c1", "prompt body", None)
    vote = {
        "model": "deepseek",
        "case_id": "c1",
        "case_type": "happy_path",
        "score_total": 80.0,
        "dimension_scores": {
            "instruction_following": {"score": 80, "analysis": "分析"},
        },
        "prompt_version": "review-agent-v0.5",
    }
    repo.save_votes(run_id, [vote])

    r = client.get(f"/eval/report/{run_id}/trace")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == run_id
    assert len(body["cases"]) == 1
    assert body["cases"][0]["prompt_text"] == "prompt body"
    assert body["cases"][0]["votes"]["deepseek"]["sub_scores"]["instruction_following"]["analysis"] == "分析"
