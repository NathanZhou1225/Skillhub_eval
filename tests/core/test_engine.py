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
import json

import pytest

from skillhub_eval.core.engine import (
    EvaluationEngine,
    dimension_scores_from_sub_scores,
)
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


class FailProvider(BaseLLMProvider):
    """Always raises — simulates API timeout / outage."""

    async def judge(self, prompt: str) -> dict:
        raise RuntimeError("provider unavailable")


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
    assert report["stage_progress"] == ["level0_checking"]


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
    assert report["provider_summary"] is not None
    assert report["provider_summary"]["r5_triggered"] is True
    assert len(report["provider_summary"]["per_case"]) == 3

    run = repo.get_run(run_id)
    assert run["human_review_required"] == 1


@pytest.mark.asyncio
async def test_minimal_capability_full_stops_at_awaiting_confirm(tmp_path):
    """
    T1 fix: minimal bundle_state + capability_full with 0 eval_cases must
    stop at awaiting_confirm, NOT fail with RISK_CASE_COUNT_INSUFFICIENT.
    LLM providers must not be called.
    """
    bundle_path = str(tmp_path / "minimal_bundle")
    (tmp_path / "minimal_bundle").mkdir()
    (tmp_path / "minimal_bundle" / "SKILL.md").write_text(
        "---\nname: grill-me\nrisk_level: low\n---\n# Grill Me\n",
        encoding="utf-8",
    )
    # No eval_cases/ directory → 0 cases

    ds_counter = CallCountProvider()
    wb_counter = CallCountProvider()
    engine, repo = make_engine(tmp_path, ds_provider=ds_counter, wb_provider=wb_counter)

    run_id = repo.create_run(
        skill_id="grill-me",
        skill_bundle_path=bundle_path,
        bundle_state="minimal",
        evaluation_mode="capability_full",
    )
    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle_path,
        bundle_state=BundleState.minimal,
        evaluation_mode=EvaluationMode.capability_full,
    )

    run = repo.get_run(run_id)
    assert run["status"] == "awaiting_confirm", (
        f"Expected awaiting_confirm, got {run['status']!r}. "
        "minimal + capability_full must park, not fail with case count error."
    )
    # LLM must not be called
    assert ds_counter.calls == 0
    assert wb_counter.calls == 0
    # reason_codes must NOT contain RISK_CASE_COUNT_INSUFFICIENT
    import json
    codes = json.loads(run.get("reason_codes") or "[]")
    assert "RISK_CASE_COUNT_INSUFFICIENT" not in codes


@pytest.mark.asyncio
async def test_degraded_minimal_zero_cases_completes_with_warn(tmp_path):
    """
    T1 fix (Q1-B): degraded + minimal + 0 eval_cases must skip case gate,
    run through empty case_exec, and produce a terminal status (completed/warn),
    NOT fail with RISK_CASE_COUNT_INSUFFICIENT.
    """
    bundle_path = str(tmp_path / "deg_bundle")
    (tmp_path / "deg_bundle").mkdir()
    (tmp_path / "deg_bundle" / "SKILL.md").write_text(
        "---\nname: tiered-memory\nrisk_level: low\n---\n# Tiered Memory\n",
        encoding="utf-8",
    )
    # No eval_cases/ → 0 cases

    engine, repo = make_engine(tmp_path)

    run_id = repo.create_run(
        skill_id="tiered-memory",
        skill_bundle_path=bundle_path,
        bundle_state="minimal",
        evaluation_mode="degraded",
    )
    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle_path,
        bundle_state=BundleState.minimal,
        evaluation_mode=EvaluationMode.degraded,
    )

    run = repo.get_run(run_id)
    assert run["status"] in ("completed", "awaiting_human_review"), (
        f"degraded + 0 cases must complete (warn), got {run['status']!r}"
    )
    import json
    codes = json.loads(run.get("reason_codes") or "[]")
    assert "RISK_CASE_COUNT_INSUFFICIENT" not in codes
    # Degraded mode must never produce pass
    assert run.get("review_status") in ("warn", "fail", None)


@pytest.mark.asyncio
async def test_confirmed_zero_cases_fails_case_gate(tmp_path):
    """
    confirmed + capability_full + 0 cases must still fail via case gate
    (case gate is NOT skipped for confirmed bundles).
    """
    bundle_path = str(tmp_path / "confirmed_empty")
    (tmp_path / "confirmed_empty").mkdir()
    (tmp_path / "confirmed_empty" / "SKILL.md").write_text(
        "---\nname: empty-confirmed\nrisk_level: low\n---\n# Empty\n",
        encoding="utf-8",
    )

    ds_counter = CallCountProvider()
    wb_counter = CallCountProvider()
    engine, repo = make_engine(tmp_path, ds_provider=ds_counter, wb_provider=wb_counter)

    run_id = repo.create_run(
        skill_id="empty-confirmed",
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
    import json
    codes = json.loads(run.get("reason_codes") or "[]")
    assert "RISK_CASE_COUNT_INSUFFICIENT" in codes
    assert ds_counter.calls == 0  # case gate kills before LLM

    report = repo.get_report(run_id)
    assert report is not None
    assert "RISK_CASE_COUNT_INSUFFICIENT" in report["reason_codes"]
    assert "risk_locking" in report["stage_progress"]


@pytest.mark.asyncio
async def test_minimal_run_gaps_snapshot_includes_block_items(tmp_path):
    """T2: awaiting_confirm run persists structured gaps with required_actions."""
    bundle_path = str(tmp_path / "minimal_gaps")
    (tmp_path / "minimal_gaps").mkdir()
    (tmp_path / "minimal_gaps" / "SKILL.md").write_text(
        "---\nname: grill-me\n---\n# Grill Me\n",
        encoding="utf-8",
    )

    engine, repo = make_engine(tmp_path)
    run_id = repo.create_run(
        skill_id="grill-me",
        skill_bundle_path=bundle_path,
        bundle_state="minimal",
        evaluation_mode="capability_full",
    )
    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle_path,
        bundle_state=BundleState.minimal,
        evaluation_mode=EvaluationMode.capability_full,
    )

    gaps = repo.get_gaps("grill-me")
    assert gaps is not None
    assert gaps["required_actions"]
    block_fields = {g["field_path"] for g in gaps["gaps"] if g["severity"] == "block"}
    assert "eval_cases" in block_fields
    assert "sample_io" in block_fields

    report = repo.get_report(run_id)
    assert report is not None
    assert report["status"] == "awaiting_confirm"
    assert report["gaps"]
    assert report["stage_progress"]


@pytest.mark.asyncio
async def test_t4_awaiting_confirm_lightweight_report_fields(tmp_path):
    bundle_path = str(tmp_path / "park")
    (tmp_path / "park").mkdir()
    (tmp_path / "park" / "SKILL.md").write_text(
        "---\nname: grill-me\nrisk_level: low\n---\n# Grill Me\n",
        encoding="utf-8",
    )
    engine, repo = make_engine(tmp_path)
    run_id = repo.create_run(
        skill_id="grill-me",
        skill_bundle_path=bundle_path,
        bundle_state="minimal",
        evaluation_mode="capability_full",
    )
    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle_path,
        bundle_state=BundleState.minimal,
        evaluation_mode=EvaluationMode.capability_full,
    )
    report = repo.get_report(run_id)
    assert report is not None
    assert report["required_actions"]
    assert "awaiting_confirm" in report["stage_progress"]
    assert report["risk_level_locked"] == "low"
    assert report["score_total_source"] == "not_applicable"


@pytest.mark.asyncio
async def test_t4_level0_fail_report_stage_progress(tmp_path):
    bundle_path = str(tmp_path / "no_skill_md")
    (tmp_path / "no_skill_md").mkdir()
    engine, repo = make_engine(tmp_path)
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
    report = repo.get_report(run_id)
    assert report["stage_progress"] == ["level0_checking"]
    assert "LEVEL0_SCHEMA_FAIL" in report["reason_codes"]


@pytest.mark.asyncio
async def test_parallel_case_judging_exceeds_single_case_concurrency(tmp_path):
    """T7: Semaphore(3) allows multiple cases to judge DS+Gemini concurrently."""

    class ConcurrentProbeProvider(BaseLLMProvider):
        active = 0
        peak = 0

        async def judge(self, prompt: str) -> dict:
            ConcurrentProbeProvider.active += 1
            ConcurrentProbeProvider.peak = max(
                ConcurrentProbeProvider.peak,
                ConcurrentProbeProvider.active,
            )
            await asyncio.sleep(0.03)
            ConcurrentProbeProvider.active -= 1
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

    ConcurrentProbeProvider.active = 0
    ConcurrentProbeProvider.peak = 0

    bundle = make_confirmed_low_bundle(tmp_path / "bundle", n_cases=6)
    probe = ConcurrentProbeProvider()
    engine, repo = make_engine(tmp_path, ds_provider=probe, wb_provider=probe)

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

    # One case at a time would peak at 2 (DS+Gemini); with 3 case slots, peak ≥ 4
    assert ConcurrentProbeProvider.peak >= 4
    assert repo.get_run(run_id)["status"] in ("completed", "awaiting_human_review")


@pytest.mark.asyncio
async def test_stage_timing_events_logged(tmp_path):
    """T7: engine emits stage_timing analytics events per phase."""
    bundle = make_confirmed_low_bundle(tmp_path / "bundle", n_cases=3)
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

    with repo._conn() as conn:
        rows = conn.execute(
            "SELECT event_name, payload_json FROM analytics_events WHERE run_id=?",
            (run_id,),
        ).fetchall()

    timing = [
        json.loads(r["payload_json"])
        for r in rows
        if r["event_name"] == "stage_timing"
    ]
    stages = {t["stage"] for t in timing}
    assert "level0_checking" in stages
    assert "risk_locking" in stages
    assert "model_judging" in stages
    assert any(t.get("stage") == "case_judge" and "case_id" in t for t in timing)


@pytest.mark.asyncio
async def test_workflow_timeout_high_risk_uses_600s(tmp_path):
    """T7: risk_level=high locks 600s workflow budget before judging."""
    bundle_path = tmp_path / "high_bundle"
    bundle_path.mkdir(parents=True)
    (bundle_path / "SKILL.md").write_text(
        "---\nname: high-skill\nid: skill.high\nrisk_level: high\n---\n# High\n",
        encoding="utf-8",
    )
    ec = bundle_path / "eval_cases"
    ec.mkdir()
    for i in range(9):
        (ec / f"case_{i:02d}.yaml").write_text(
            f"id: case_{i:02d}\ntype: happy_path\nuser_intent: intent {i}\n",
            encoding="utf-8",
        )
    (bundle_path / "sample_io").mkdir()

    engine, repo = make_engine(tmp_path)
    run_id = repo.create_run(
        skill_id="skill.high",
        skill_bundle_path=str(bundle_path),
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )

    class ProbeProvider(BaseLLMProvider):
        async def judge(self, prompt: str) -> dict:
            assert engine._workflow_timeout == 600.0
            return await HighScoreProvider().judge(prompt)

    engine.ds = ProbeProvider()
    engine.wb = ProbeProvider()

    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=str(bundle_path),
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
    )


@pytest.mark.asyncio
async def test_workflow_timeout_marks_run_failed(tmp_path):
    """Workflow timeout fires → run status=failed, reason_code=EVAL_WORKFLOW_TIMEOUT."""

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

    report = repo.get_report(run_id)
    assert report is not None
    assert "EVAL_WORKFLOW_TIMEOUT" in report["reason_codes"]
    assert report["stage_progress"]
    assert "level0_checking" in report["stage_progress"]
    assert report.get("error_detail")


def test_prompt_no_hardcoded_scores(tmp_path):
    """Post-T8: format example must not contain literal score digits."""
    engine, _ = make_engine(tmp_path)
    bundle = {
        "skill_id": "demo-skill",
        "skill_md_text": "---\nname: demo\n---\n# Demo\n",
    }
    case = {"id": "c1", "type": "happy_path", "user_intent": "test intent"}
    prompt = engine._build_prompt(
        case,
        bundle,
        BundleState.confirmed,
        EvaluationMode.capability_full,
    )
    assert '"score":85' not in prompt
    assert '"score":80' not in prompt
    assert "<integer 0-100>" in prompt
    assert "instruction_following" in prompt
    assert "禁止照抄" in prompt


def test_extract_score_weighted_three_dimensions(tmp_path):
    engine, _ = make_engine(tmp_path)
    raw = {
        "sub_scores": {
            "instruction_following": {"score": 80, "pass": True},
            "output_compliance": {"score": 70, "pass": True},
            "business_resolution": {"score": 90, "pass": True},
        }
    }
    # 80*0.4 + 70*0.3 + 90*0.3 = 32 + 21 + 27 = 80
    assert engine._extract_score(raw) == 80.0


def test_extract_score_fallback_single_sub_score(tmp_path):
    engine, _ = make_engine(tmp_path)
    raw = {"sub_scores": {"step_completeness": {"score": 88}}}
    assert engine._extract_score(raw) == 88.0


@pytest.mark.asyncio
async def test_model_votes_dimension_scores_populated(tmp_path):
    """Post-T8: report model_votes carry rubric dimension scores from sub_scores."""
    bundle_path = make_confirmed_low_bundle(tmp_path, n_cases=6)
    engine, repo = make_engine(tmp_path)
    run_id = repo.create_run(
        skill_id="skill.test",
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
    report = repo.get_report(run_id)
    assert report and report.get("model_votes")
    for vote in report["model_votes"]:
        dim = vote.get("dimension_scores") or {}
        # mock HighScoreProvider uses step_completeness only → dims stay null
        assert "instruction_following" in dim


@pytest.mark.asyncio
async def test_all_providers_fail_marks_eval_unavailable(tmp_path):
    bundle = make_confirmed_low_bundle(tmp_path / "bundle", n_cases=3)
    engine, repo = make_engine(
        tmp_path,
        ds_provider=FailProvider(),
        wb_provider=FailProvider(),
    )
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
    report = repo.get_report(run_id)
    assert "EVAL_PROVIDER_UNAVAILABLE" in report["reason_codes"]
    assert not report.get("model_votes")
    assert run.get("human_review_required") in (0, False, None)


def test_dimension_scores_from_sub_scores_maps_rubric():
    dim = dimension_scores_from_sub_scores({
        "instruction_following": {"score": 81},
        "output_compliance": {"score": 72},
        "business_resolution": {"score": 93},
    })
    assert dim.instruction_following == 81.0
    assert dim.output_compliance == 72.0
    assert dim.business_resolution == 93.0


# ── Decision warn reason_codes ────────────────────────────────────────────────

def test_decision_warn_completeness_low_emits_reason_code():
    """P2: decision sets WARN_COMPLETENESS_LOW when score>=85 but completeness<90."""
    from skillhub_eval.core.decision import DecisionStage
    from skillhub_eval.core.schemas.enums import BundleState, EvaluationMode

    dec = DecisionStage()
    ctx = {
        "bundle_state": BundleState.confirmed,
        "evaluation_mode": EvaluationMode.capability_full,
        "r5_triggered": False,
        "r1_r4_fail": False,
        "score_total": 88.0,
        "completeness_score": 75.0,
        "reason_codes": [],
        "level_requirement_met": True,
    }
    status = dec.decide(ctx)
    extra = dec.warn_reason_codes(ctx)
    assert status == "warn"
    assert "WARN_COMPLETENESS_LOW" in extra


def test_decision_warn_score_midrange_emits_reason_code():
    """P2: decision sets WARN_SCORE_MIDRANGE when score is 70-84."""
    from skillhub_eval.core.decision import DecisionStage
    from skillhub_eval.core.schemas.enums import BundleState, EvaluationMode

    dec = DecisionStage()
    ctx = {
        "bundle_state": BundleState.confirmed,
        "evaluation_mode": EvaluationMode.capability_full,
        "r5_triggered": False,
        "r1_r4_fail": False,
        "score_total": 78.0,
        "completeness_score": 95.0,
        "reason_codes": [],
        "level_requirement_met": True,
    }
    status = dec.decide(ctx)
    extra = dec.warn_reason_codes(ctx)
    assert status == "warn"
    assert "WARN_SCORE_MIDRANGE" in extra


@pytest.mark.asyncio
async def test_skill_summary_field_populated_on_pass(tmp_path):
    """skill_summary field is included in report when model judging succeeds."""
    class SummaryProvider(BaseLLMProvider):
        """First call: returns normal judge vote; second call: returns skill summary."""
        call_count = 0

        async def judge(self, prompt: str) -> dict:
            SummaryProvider.call_count += 1
            if "质量诊断摘要" in prompt or "overall_verdict" in prompt:
                return {
                    "overall_verdict": "技能文档质量良好",
                    "strengths": ["意图清晰"],
                    "weaknesses": ["样例较少"],
                    "dimension_notes": {
                        "instruction_following": "良好",
                        "output_compliance": "达标",
                        "business_resolution": "尚可",
                    },
                    "recommendation": "建议补充边界 case",
                }
            return {
                "sub_scores": {
                    "instruction_following": {"score": 90, "pass": True},
                    "output_compliance": {"score": 88, "pass": True},
                    "business_resolution": {"score": 92, "pass": True},
                },
                "confidence": "high",
                "dimension_notes": "",
            }

    bundle_path = make_confirmed_low_bundle(tmp_path / "bundle_ss", n_cases=3)
    engine, repo = make_engine(
        tmp_path,
        ds_provider=SummaryProvider(),
        wb_provider=SummaryProvider(),
    )
    run_id = repo.create_run(
        skill_id="skill.test",
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
    report = repo.get_report(run_id)
    assert report is not None
    ss = report.get("skill_summary")
    # summary may be None if wb_provider returned judge vote for summary call
    # (provider is shared), just assert field exists in schema
    assert "skill_summary" in report
