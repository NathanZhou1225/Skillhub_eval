import pytest

from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.core.schemas import BundleState, EvaluationMode
from skillhub_eval.persistence.sqlite import SqliteRepository
from tests.core.test_engine import CallCountProvider, make_draft_enriched_bundle


@pytest.mark.asyncio
async def test_degraded_readiness_is_lightweight_and_persists_gaps(tmp_path):
    bundle = make_draft_enriched_bundle(tmp_path / "bundle")
    repo = SqliteRepository(str(tmp_path / "readiness.db"))
    repo.init_db()
    ds_counter = CallCountProvider()
    wb_counter = CallCountProvider()
    engine = EvaluationEngine(repo=repo, ds_provider=ds_counter, wb_provider=wb_counter)

    run_id = repo.create_run(
        skill_id="skill.draft",
        skill_bundle_path=bundle,
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
    )
    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle,
        bundle_state=BundleState.draft_enriched,
        evaluation_mode=EvaluationMode.degraded,
    )

    run = repo.get_run(run_id)
    assert run["status"] == "completed"
    assert run["review_status"] == "warn"
    assert run["score_total"] is None

    stage_progress = repo.get_stage_progress(run_id)
    assert "model_judging" not in stage_progress
    assert "case_executing" not in stage_progress
    assert "code_asserting" not in stage_progress

    # Readiness path must not call AI risk review/model judging providers.
    assert ds_counter.calls == 0
    assert wb_counter.calls == 0

    report = repo.get_report(run_id)
    assert report is not None
    assert report["score_total"] is None
    assert report["review_status"] == "warn"
    assert report.get("gaps")

    gaps = repo.get_gaps("skill.draft")
    assert gaps is not None
    assert gaps.get("required_actions")
