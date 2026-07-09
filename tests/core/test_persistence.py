import pytest

from skillhub_eval.core.schemas import (
    BundleState,
    EvaluationMode,
    EvaluationReport,
    RunStatus,
)
from skillhub_eval.persistence.sqlite import SqliteRepository


@pytest.fixture
def repo(tmp_path):
    db = str(tmp_path / "test.db")
    repository = SqliteRepository(db)
    repository.init_db()
    return repository


def test_create_and_get_run(repo):
    run_id = repo.create_run(
        skill_id="s1",
        skill_bundle_path="/tmp/s1",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    assert run_id is not None
    row = repo.get_run(run_id)
    assert row["skill_id"] == "s1"
    assert row["status"] == "pending"


def test_update_status(repo):
    run_id = repo.create_run("s2", "/tmp/s2", "minimal", "degraded")
    repo.update_status(run_id, "level0_checking")
    assert repo.get_run(run_id)["status"] == "level0_checking"


def test_save_and_get_report(repo):
    run_id = repo.create_run("s3", "/tmp/s3", "confirmed", "capability_full")
    report = EvaluationReport(
        run_id=run_id,
        skill_id="s3",
        skill_bundle_path="/tmp/s3",
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
        status=RunStatus.completed,
        review_status="pass",
        rubric_version="v1.2",
        prompt_version="review-agent-v0.2",
    )
    repo.save_report(run_id, report)
    fetched = repo.get_report(run_id)
    assert fetched["review_status"] == "pass"


def test_list_history(repo):
    for i in range(3):
        repo.create_run(f"sk{i}", f"/tmp/sk{i}", "minimal", "degraded")
    rows = repo.list_history(limit=10)
    assert len(rows) == 3


def test_human_review_required_filter(repo):
    run_id = repo.create_run("s4", "/tmp/s4", "confirmed", "capability_full")
    repo.update_status(run_id, "awaiting_human_review")
    repo.set_human_review_required(run_id, True, ["MODEL_DISAGREEMENT_R5"])
    rows = repo.list_history(human_review_required=True)
    assert any(r["run_id"] == run_id for r in rows)


def test_save_and_get_votes(repo):
    run_id = repo.create_run("s5", "/tmp/s5", "confirmed", "capability_full")
    votes = [
        {"model": "deepseek", "case_id": "c1", "score_total": 85},
        {"model": "gemini", "case_id": "c1", "score_total": 72},
    ]
    repo.save_votes(run_id, votes)
    fetched = repo.get_votes_for_run(run_id)
    assert len(fetched) == 2
    assert fetched[0]["model"] == "deepseek"


def test_save_confirmation(repo):
    repo.save_confirmation(
        skill_id="skill.test",
        field_path="negative_prompts",
        confirmed_value="no PII",
        operator="alice",
    )
    with repo._conn() as conn:
        row = conn.execute(
            "SELECT field_path, confirmed_value, confirmed_by FROM bundle_confirmations"
        ).fetchone()
    assert row["field_path"] == "negative_prompts"
    assert row["confirmed_value"] == "no PII"
    assert row["confirmed_by"] == "alice"


def test_append_stage_and_log_event(repo):
    run_id = repo.create_run("s6", "/tmp/s6", "minimal", "degraded")
    repo.append_stage(run_id, "level0_checking", {"cases": 3})
    repo.log_event(run_id, "eval_score_variance_detected", {"gap": 12})
    with repo._conn() as conn:
        stage_count = conn.execute(
            "SELECT COUNT(*) AS c FROM stage_transitions WHERE run_id=?",
            (run_id,),
        ).fetchone()["c"]
        event_count = conn.execute(
            "SELECT COUNT(*) AS c FROM analytics_events WHERE run_id=?",
            (run_id,),
        ).fetchone()["c"]
    assert stage_count == 1
    assert event_count == 1


def test_save_gaps_and_get_gaps(repo):
    run_id = repo.create_run("s7", "/tmp/s7", "draft_enriched", "degraded")
    gaps = {
        "skill_id": "skill.gaps",
        "run_id": run_id,
        "gaps": [{"field_path": "description", "severity": "warn", "message": "too short"}],
    }
    repo.save_gaps(run_id, gaps)
    fetched = repo.get_gaps("skill.gaps")
    assert fetched["gaps"][0]["field_path"] == "description"


def test_get_stage_progress(repo):
    run_id = repo.create_run("s8", "/tmp/s8", "minimal", "capability_full")
    repo.append_stage(run_id, "level0_checking")
    repo.append_stage(run_id, "risk_locking")
    repo.append_stage(run_id, "awaiting_confirm")
    assert repo.get_stage_progress(run_id) == [
        "level0_checking", "risk_locking", "awaiting_confirm",
    ]


def test_get_stage_progress_includes_local_agent_case_events(repo):
    run_id = repo.create_run("s8-local", "/tmp/s8", "confirmed", "capability_full")
    repo.append_stage(run_id, "case_executing")
    repo.log_event(run_id, "local_agent_case_started", {"case_id": "c01", "case_type": "happy_path"})
    repo.log_event(run_id, "local_agent_case_succeeded", {
        "case_id": "c01",
        "status": "ok",
        "duration_ms": 1234,
    })
    repo.log_event(run_id, "local_agent_case_failed", {
        "case_id": "c02",
        "status": "incomplete",
        "degrade_reason": "run_incomplete",
        "stderr_excerpt": "boom",
    })

    progress = repo.get_stage_progress(run_id)

    assert progress[0] == "case_executing"
    events = [item for item in progress if isinstance(item, dict)]
    assert [item["event"] for item in events] == [
        "local_agent_case_started",
        "local_agent_case_succeeded",
        "local_agent_case_failed",
    ]
    assert events[0]["case_id"] == "c01"
    assert events[0]["case_type"] == "happy_path"
    assert events[0]["created_at"]
    assert events[1]["duration_ms"] == 1234
    assert events[2]["stderr_excerpt"] == "boom"


def test_get_stage_timings_and_history_summary(repo):
    run_id = repo.create_run("s9", "/tmp/s9", "confirmed", "capability_full")
    repo.log_event(run_id, "stage_timing", {"stage": "level0_checking", "ms": 100})
    repo.log_event(run_id, "stage_timing", {"stage": "model_judging", "ms": 5000})
    repo.log_event(run_id, "stage_timing", {"stage": "case_judge", "case_id": "c01", "ms": 900})

    timings = repo.get_stage_timings(run_id)
    assert len(timings) == 3
    assert timings[1]["stage"] == "model_judging"

    summaries = repo.get_stage_timing_summaries([run_id])
    assert summaries[run_id]["total_phase_ms"] == 5100
    assert summaries[run_id]["model_judging_ms"] == 5000

    history = repo.list_history(limit=5)
    row = next(r for r in history if r["run_id"] == run_id)
    assert row["timing_summary"]["total_phase_ms"] == 5100
