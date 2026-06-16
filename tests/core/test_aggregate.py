"""
Task 7 — Aggregate + Decision tests.

Strictly follows 1.2 v1.2.1 R1–R8 rules (grill-me C-2):
  R4: completeness < 70 AND score_total < 70 → fail
  R5: |DS - WB| >= 10 OR one-pass-one-fail → warn + human (null score),
      except when both models consensus-fail (both bundle fail or both scores < 70)
      → aggregate mean and let R8 fail without human queue
  R6: score >= 85 AND completeness >= 90 AND confirmed + capability_full + level ok → pass
  R7: 70 <= score <= 84 OR 70 <= completeness <= 89 → warn
  R8: score < 70 → fail
"""

import pytest

from skillhub_eval.core.aggregate import AggregateStage
from skillhub_eval.core.decision import DecisionStage
from skillhub_eval.core.schemas import BundleState, EvaluationMode


# ─── helpers ─────────────────────────────────────────────────────────────────

def make_votes(
    ds_score: float,
    wb_score: float,
    ds_status: str = "pass",
    wb_status: str = "pass",
    case_id: str = "c1",
) -> list[dict]:
    return [
        {
            "model": "deepseek",
            "case_id": case_id,
            "score_total": ds_score,
            "suggested_review_status": ds_status,
            "dimension_scores": {},
            "confidence": "high",
            "evidence_refs": [],
            "feedback": "",
        },
        {
            "model": "gemini",
            "case_id": case_id,
            "score_total": wb_score,
            "suggested_review_status": wb_status,
            "dimension_scores": {},
            "confidence": "high",
            "evidence_refs": [],
            "feedback": "",
        },
    ]


def confirmed_full_ctx(
    score: float | None,
    completeness: float,
    r5: bool = False,
    r1_r4_fail: bool = False,
    reason_codes: list | None = None,
    level_ok: bool = True,
) -> dict:
    return {
        "bundle_state": BundleState.confirmed,
        "evaluation_mode": EvaluationMode.capability_full,
        "r5_triggered": r5,
        "r1_r4_fail": r1_r4_fail,
        "score_total": score,
        "completeness_score": completeness,
        "reason_codes": reason_codes or [],
        "level_requirement_met": level_ok,
    }


# ─── AggregateStage ───────────────────────────────────────────────────────────

class TestAggregate:
    def setup_method(self):
        self.agg = AggregateStage()

    # R5: score gap >= 10 → null + disagreement
    def test_r5_score_gap_triggers(self):
        votes = make_votes(ds_score=85, wb_score=74)  # gap = 11
        result = self.agg.run(votes=votes, assertion_passed=True, completeness_score=85)
        assert result["r5_triggered"] is True
        assert result["score_total"] is None
        assert result["score_total_source"] == "null_due_to_disagreement"
        assert "MODEL_DISAGREEMENT_R5" in result["reason_codes"]

    # R5: exactly 10 gap → triggers (boundary)
    def test_r5_exactly_10_gap_triggers(self):
        votes = make_votes(ds_score=80, wb_score=70)  # gap = 10
        result = self.agg.run(votes=votes, assertion_passed=True, completeness_score=85)
        assert result["r5_triggered"] is True

    # R5: gap = 9 → does NOT trigger
    def test_r5_gap_9_no_trigger(self):
        votes = make_votes(ds_score=80, wb_score=71)  # gap = 9
        result = self.agg.run(votes=votes, assertion_passed=True, completeness_score=85)
        assert result["r5_triggered"] is False
        assert result["score_total"] == pytest.approx(75.5)

    # R5: one-pass-one-fail status → triggers
    def test_r5_one_pass_one_fail_status(self):
        votes = make_votes(ds_score=88, wb_score=85, ds_status="pass", wb_status="fail")
        result = self.agg.run(votes=votes, assertion_passed=True, completeness_score=85)
        assert result["r5_triggered"] is True
        assert result["score_total"] is None

    # No R5: both pass, gap < 10 → aggregated_mean
    def test_no_r5_aggregated_mean(self):
        votes = make_votes(ds_score=80, wb_score=82)
        result = self.agg.run(votes=votes, assertion_passed=True, completeness_score=85)
        assert result["r5_triggered"] is False
        assert result["score_total"] == pytest.approx(81.0)
        assert result["score_total_source"] == "aggregated_mean"

    def test_r5_not_triggered_when_only_redline_disagrees(self):
        votes = [
            *make_votes(85, 86, case_id="h01"),
            {"model": "deepseek", "case_id": "r01", "case_type": "refusal_case",
             "score_total": 0, "suggested_review_status": "fail",
             "dimension_scores": {}, "confidence": "high", "evidence_refs": [], "feedback": ""},
            {"model": "gemini", "case_id": "r01", "case_type": "refusal_case",
             "score_total": 95, "suggested_review_status": "pass",
             "dimension_scores": {}, "confidence": "high", "evidence_refs": [], "feedback": ""},
        ]
        for v in votes[:2]:
            v["case_type"] = "happy_path"
        result = self.agg.run(votes=votes, assertion_passed=True, completeness_score=90)
        assert result["r5_triggered"] is False
        assert "REDLINE_MODEL_DISAGREEMENT" in result["reason_codes"]
        assert result["score_total"] == pytest.approx(85.5)
        assert result["score_total_source"] == "average_pool_mean"

    def test_r5_still_triggers_when_average_pool_disagrees(self):
        votes = [
            *make_votes(85, 70, case_id="h01"),
        ]
        for v in votes:
            v["case_type"] = "happy_path"
        result = self.agg.run(votes=votes, assertion_passed=True, completeness_score=90)
        assert result["r5_triggered"] is True
        assert result["score_total"] is None

    def test_r5_skipped_when_both_consensus_fail_despite_large_gap(self):
        """Low fixture pattern: DS~15 + GM~47 → aggregate fail, not R5 warn."""
        votes = make_votes(ds_score=14.7, wb_score=46.9, ds_status="fail", wb_status="fail")
        result = self.agg.run(votes=votes, assertion_passed=True, completeness_score=100)
        assert result["r5_triggered"] is False
        assert "MODEL_DISAGREEMENT_R5" not in result["reason_codes"]
        assert result["score_total"] == pytest.approx(30.8)

    def test_r5_skipped_when_both_scores_below_70_and_both_fail_status(self):
        votes = make_votes(ds_score=65, wb_score=55, ds_status="fail", wb_status="fail")
        result = self.agg.run(votes=votes, assertion_passed=True, completeness_score=100)
        assert result["r5_triggered"] is False
        assert result["score_total"] == pytest.approx(60.0)

    def test_consensus_fail_flows_to_r8_decision_without_human(self):
        votes = make_votes(ds_score=15, wb_score=45, ds_status="fail", wb_status="fail")
        agg = self.agg.run(votes=votes, assertion_passed=True, completeness_score=100)
        dec = DecisionStage()
        ctx = confirmed_full_ctx(
            score=agg["score_total"],
            completeness=agg["completeness_score"],
            r5=agg["r5_triggered"],
        )
        status = dec.decide(ctx)
        assert status == "fail"
        assert dec.requires_human_review(ctx, status) is False

    # Redline fail propagates
    def test_redline_fail_propagates(self):
        votes = make_votes(90, 88)
        result = self.agg.run(votes=votes, assertion_passed=True,
                              completeness_score=95, redline_fail=True)
        assert result["r1_r4_fail"] is True
        assert "REDLINE_CASE_FAIL" in result["reason_codes"]


# ─── DecisionStage ────────────────────────────────────────────────────────────

class TestDecision:
    def setup_method(self):
        self.dec = DecisionStage()

    # R6: pass → score >= 85, completeness >= 90, confirmed, capability_full
    def test_r6_pass(self):
        ctx = confirmed_full_ctx(score=87, completeness=91)
        assert self.dec.decide(ctx) == "pass"

    # R6 boundary: exactly 85 / 90
    def test_r6_boundary_pass(self):
        ctx = confirmed_full_ctx(score=85, completeness=90)
        assert self.dec.decide(ctx) == "pass"

    # R6 fails if score = 84 (→ R7 warn)
    def test_r7_score_84(self):
        ctx = confirmed_full_ctx(score=84, completeness=91)
        assert self.dec.decide(ctx) == "warn"

    # R7: completeness = 89 (below 90 threshold)
    def test_r7_completeness_89(self):
        ctx = confirmed_full_ctx(score=86, completeness=89)
        assert self.dec.decide(ctx) == "warn"

    # R8: score < 70 → fail
    def test_r8_score_below_70(self):
        ctx = confirmed_full_ctx(score=68, completeness=85)
        assert self.dec.decide(ctx) == "fail"

    # R8 boundary: exactly 70 → NOT R8 (should be R7)
    def test_r8_boundary_70_is_warn(self):
        ctx = confirmed_full_ctx(score=70, completeness=85)
        assert self.dec.decide(ctx) == "warn"

    # R4: dual-low → fail (both < 70)
    def test_r4_dual_low_fail(self):
        ctx = confirmed_full_ctx(score=65, completeness=65)
        assert self.dec.decide(ctx) == "fail"

    # R4: only score low, completeness ok → not R4 (R8 fires)
    def test_r4_not_triggered_single_low(self):
        ctx = confirmed_full_ctx(score=65, completeness=80)
        # R8 fires: score < 70
        assert self.dec.decide(ctx) == "fail"

    # R1–R4 hard fail: redline case
    def test_r1_r4_fail_overrides_all(self):
        ctx = confirmed_full_ctx(score=95, completeness=95, r1_r4_fail=True)
        assert self.dec.decide(ctx) == "fail"

    # R5: disagreement → warn (even if scores individually would pass)
    def test_r5_forces_warn(self):
        ctx = confirmed_full_ctx(score=None, completeness=91, r5=True,
                                 reason_codes=["MODEL_DISAGREEMENT_R5"])
        assert self.dec.decide(ctx) == "warn"

    # PASS gate: not confirmed → cannot pass even with perfect scores
    def test_pass_gate_draft_enriched_blocks_pass(self):
        ctx = {
            "bundle_state": BundleState.draft_enriched,
            "evaluation_mode": EvaluationMode.capability_full,
            "r5_triggered": False,
            "r1_r4_fail": False,
            "score_total": 95,
            "completeness_score": 95,
            "reason_codes": [],
            "level_requirement_met": True,
        }
        assert self.dec.decide(ctx) == "warn"

    # PASS gate: degraded mode → cannot pass
    def test_pass_gate_degraded_mode_blocks_pass(self):
        ctx = {
            "bundle_state": BundleState.confirmed,
            "evaluation_mode": EvaluationMode.degraded,
            "r5_triggered": False,
            "r1_r4_fail": False,
            "score_total": 95,
            "completeness_score": 95,
            "reason_codes": [],
            "level_requirement_met": True,
        }
        assert self.dec.decide(ctx) == "warn"

    # human review required when R5
    def test_requires_human_when_r5(self):
        ctx = confirmed_full_ctx(score=None, completeness=91, r5=True)
        status = self.dec.decide(ctx)
        assert self.dec.requires_human_review(ctx, status) is True

    # human review required when warn (non-R5 also goes to review queue)
    def test_requires_human_when_warn(self):
        ctx = confirmed_full_ctx(score=75, completeness=85)
        status = self.dec.decide(ctx)  # R7 warn
        assert status == "warn"
        assert self.dec.requires_human_review(ctx, status) is True

    # human review NOT required when pass
    def test_no_human_review_when_pass(self):
        ctx = confirmed_full_ctx(score=90, completeness=92)
        status = self.dec.decide(ctx)
        assert status == "pass"
        assert self.dec.requires_human_review(ctx, status) is False
