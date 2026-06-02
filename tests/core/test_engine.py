"""
Task 8 — EvaluationEngine integration tests.

Covers:
  - Full pipeline confirmed → report with review_status
  - C-3: draft_enriched stops at awaiting_confirm (does NOT call model_judge)
  - C-3: degraded mode continues but review_status capped at warn
  - Level 0 fail → engine terminates immediately, no LLM calls
  - R5 disagreement → score_total=null, human_review.required=True
"""

import asyncio
import pytest

from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.core.schemas import BundleState, EvaluationMode, RunStatus
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.providers.base import BaseLLMProvider


# ─── fake providers ───────────────────────────────────────────────────────────

class HighScoreProvider(BaseLLMProvider):
    """Both DS and WB agree: high scores → should produce pass."""

    async def judge(self, prompt: str) -> dict:
        return {
            "sub_scores": {
                "step_completeness": {
                    "score": 90,
                    "pass": True,
                    "reason": "complete",
                    "evidence_refs": [],
                },
                "no_hallucination": {
                    "score": 92,
                    "pass": True,
                    "reason": "accurate",
                    "evidence_refs": [],
                },
            },
            "confidence": "high",
            "dimension_notes": "",
        }


class DisagreeProvider(BaseLLMProvider):
    """
    DS gives pass-level (88), WB gives fail-level (60) → gap=28 → R5.
    Also DS status=pass, WB status=fail → status mismatch.
    """

    def __init__(self, score: float, status: str):
        self.score = score
        self.status = status

    async def judge(self, prompt: str) -> dict:
        return {
            "sub_scores": {
                "step_completeness": {
                    "score": int(self.score),
                    "pass": self.score >= 70,
                    "reason": "disagree",
                    "evidence_refs": [],
                }
            },
            "confidence": "low",
            "dimension_notes": "",
        }


class CallCountProvider(BaseLLMProvider):
    """Tracks how many times judge() was called (to verify early-termination)."""

    def __init__(self):
        self.calls = 0

    async def judge(self, prompt: str) -> dict:
        self.calls += 1
        return {
            "sub_scores": {
                "step_completeness": {
                    "score": 85,
                    "pass": True,
                    "reason": "ok",
                    "evidence_refs": [],
                }
            },
            "confidence": "high",
            "dimension_notes": "",
        }


# ─── bundle fixtures ──────────────────────────────────────────────────────────

def make_confirmed_low_bundle(tmp_path, n_cases: int = 3) -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "SKILL.md").write_text(
        "---\nname: test-skill\nid: skill.test\nrisk_level: low\n"
        "description: 员工出勤智能核查\n---\n# Test\n",
        encoding="utf-8",
    )
    ec = tmp_path / "eval_cases"
    ec.mkdir()
    for i in range(n_cases):
        (ec / f"case_{i:02d}.yaml").write_text(
            f"id: case_{i:02d}\ntype: happy_path\nuser_intent: test intent {i}\n",
            encoding="utf-8",
        )
    (tmp_path / "sample_io").mkdir()
    return str(tmp_path)


def make_draft_enriched_bundle(tmp_path) -> str:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "SKILL.md").write_text(
        "---\nname: draft-skill\nid: skill.draft\nrisk_level: low\n---\n# Draft\n",
        encoding="utf-8",
    )
    ec = tmp_path / "eval_cases"
    ec.mkdir()
    for i in range(3):
        (ec / f"case_{i:02d}.yaml").write_text(
            f"id: case_{i:02d}\ntype: happy_path\nuser_intent: intent {i}\n",
            encoding="utf-8",
        )
    return str(tmp_path)


# ─── helpers ──────────────────────────────────────────────────────────────────

def make_engine(tmp_path, ds_provider=None, wb_provider=None):
    db = str(tmp_path / "engine_test.db")
    repo = SqliteRepository(db)
    repo.init_db()
    ds = ds_provider or HighScoreProvider()
    wb = wb_provider or HighScoreProvider()
    engine = EvaluationEngine(repo=repo, ds_provider=ds, wb_provider=wb)
    return engine, repo


# ─── tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_confirmed_full_run_produces_report(tmp_path):
    """Full pipeline: confirmed + capability_full → completed with review_status."""
    bundle = make_confirmed_low_bundle(tmp_path / "bundle")
    engine, repo = make_engine(tmp_path)

    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path=bundle,
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle,
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
    )

    run = repo.get_run(run_id)
    assert run["status"] in ("completed", "awaiting_human_review")

    report = repo.get_report(run_id)
    assert report is not None
    assert report["skill_id"] == "skill.test"
    assert report["review_status"] in ("pass", "warn", "fail")
    assert report["bundle_state"] == "confirmed"
    assert report["evaluation_mode"] == "capability_full"


@pytest.mark.asyncio
async def test_c3_draft_enriched_stops_at_awaiting_confirm(tmp_path):
    """
    C-3: bundle_state=draft_enriched with capability_full mode should stop
    at awaiting_confirm and NOT call model providers.
    """
    bundle = make_draft_enriched_bundle(tmp_path / "bundle")
    ds_counter = CallCountProvider()
    wb_counter = CallCountProvider()
    engine, repo = make_engine(tmp_path, ds_provider=ds_counter, wb_provider=wb_counter)

    run_id = repo.create_run(
        skill_id="skill.draft",
        skill_bundle_path=bundle,
        bundle_state="draft_enriched",
        evaluation_mode="capability_full",
    )
    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle,
        bundle_state=BundleState.draft_enriched,
        evaluation_mode=EvaluationMode.capability_full,
    )

    run = repo.get_run(run_id)
    assert run["status"] == "awaiting_confirm"
    # LLM providers must NOT have been called
    assert ds_counter.calls == 0
    assert wb_counter.calls == 0


@pytest.mark.asyncio
async def test_degraded_mode_continues_and_caps_at_warn(tmp_path):
    """
    C-3: degraded mode (bundle_state=draft_enriched, evaluation_mode=degraded)
    continues through model judging but review_status is capped at warn.
    """
    bundle = make_draft_enriched_bundle(tmp_path / "bundle")
    engine, repo = make_engine(tmp_path)

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

    report = repo.get_report(run_id)
    assert report is not None
    # Degraded mode can never produce "pass"
    assert report["review_status"] in ("warn", "fail")
    assert report["evaluation_mode"] == "degraded"


@pytest.mark.asyncio
async def test_level0_fail_terminates_immediately(tmp_path):
    """Level 0 failure must stop the pipeline before any LLM calls."""
    bundle_path = str(tmp_path / "empty_bundle")
    (tmp_path / "empty_bundle").mkdir()
    # No SKILL.md → Level 0 fail

    ds_counter = CallCountProvider()
    wb_counter = CallCountProvider()
    engine, repo = make_engine(tmp_path, ds_provider=ds_counter, wb_provider=wb_counter)

    run_id = repo.create_run(
        skill_id="skill.empty",
        skill_bundle_path=bundle_path,
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle_path,
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
    )

    run = repo.get_run(run_id)
    assert run["status"] == "failed"
    assert run["review_status"] == "fail"
    assert ds_counter.calls == 0
    assert wb_counter.calls == 0

    report = repo.get_report(run_id)
    assert "LEVEL0_SCHEMA_FAIL" in report["reason_codes"]


@pytest.mark.asyncio
async def test_r5_disagreement_produces_null_score_and_human_review(tmp_path):
    """R5: DS=88 (pass), WB=60 (fail) → gap=28 → score_total=null, human review."""
    bundle = make_confirmed_low_bundle(tmp_path / "bundle")
    ds_prov = DisagreeProvider(score=88, status="pass")
    wb_prov = DisagreeProvider(score=60, status="fail")
    engine, repo = make_engine(tmp_path, ds_provider=ds_prov, wb_provider=wb_prov)

    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path=bundle,
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle,
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
    )

    report = repo.get_report(run_id)
    assert report is not None
    assert report["score_total"] is None
    assert report["score_total_source"] == "null_due_to_disagreement"
    assert "MODEL_DISAGREEMENT_R5" in report["reason_codes"]
    assert report["human_review"]["required"] is True

    run = repo.get_run(run_id)
    assert run["human_review_required"] == 1


@pytest.mark.asyncio
async def test_workflow_timeout_marks_run_failed(tmp_path):
    """180s timeout fires → run status=failed, reason_code=EVAL_WORKFLOW_TIMEOUT."""

    class SlowProvider(BaseLLMProvider):
        async def judge(self, prompt: str) -> dict:
            await asyncio.sleep(9999)
            return {}

    bundle = make_confirmed_low_bundle(tmp_path / "bundle")
    engine, repo = make_engine(tmp_path, ds_provider=SlowProvider(), wb_provider=SlowProvider())
    engine._workflow_timeout = 0.1  # override to 100ms for test

    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path=bundle,
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle,
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
    )

    run = repo.get_run(run_id)
    assert run["status"] == "failed"
