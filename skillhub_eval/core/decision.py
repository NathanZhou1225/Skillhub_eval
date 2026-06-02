"""
DecisionStage — applies PASS gate + R1–R8 priority ladder (1.2 v1.2.1, C-2).

Priority (highest to lowest):
  R1–R4  hard fail  → always "fail" regardless of scores
  R5     disagreement → always "warn" + human review required
  PASS gate check (bundle_state=confirmed, evaluation_mode=capability_full)
  R6     score >= 85 AND completeness >= 90 → "pass"
  R7     score 70–84 OR completeness 70–89 → "warn"
  R8     score < 70 → "fail"
"""

from __future__ import annotations

from .schemas.enums import BundleState, EvaluationMode

# 1.2 §6.2 thresholds (do not change — owned by 评估指标与准入标准.md)
_R6_SCORE_MIN = 85
_R6_COMPLETENESS_MIN = 90
_R8_SCORE_MAX = 70        # exclusive: score < 70 → fail
_DUAL_LOW_THRESHOLD = 70  # R4: BOTH below this → fail


class DecisionStage:
    """
    Produces a final review_status string: "pass" | "warn" | "fail".

    ctx keys expected:
        bundle_state           BundleState
        evaluation_mode        EvaluationMode
        r5_triggered           bool
        r1_r4_fail             bool
        score_total            float | None
        completeness_score     float
        reason_codes           list[str]
        level_requirement_met  bool  (optional, defaults True)
    """

    def decide(self, ctx: dict) -> str:
        bundle_state = ctx["bundle_state"]
        evaluation_mode = ctx["evaluation_mode"]
        r5_triggered = ctx.get("r5_triggered", False)
        r1_r4_fail = ctx.get("r1_r4_fail", False)
        score = ctx.get("score_total")
        completeness = ctx.get("completeness_score", 0.0)
        level_ok = ctx.get("level_requirement_met", True)

        # ── R1–R4: hard fail (highest priority) ──────────────────────────────
        if r1_r4_fail:
            return "fail"

        # ── R4: dual-low (both quality AND completeness < 70) ─────────────────
        if (
            score is not None
            and score < _DUAL_LOW_THRESHOLD
            and completeness < _DUAL_LOW_THRESHOLD
        ):
            return "fail"

        # ── R8: quality score below minimum ───────────────────────────────────
        if score is not None and score < _R8_SCORE_MAX:
            return "fail"

        # ── R5: model disagreement → always warn + human ──────────────────────
        if r5_triggered:
            return "warn"

        # ── PASS gate: must have confirmed + capability_full ──────────────────
        can_pass = (
            bundle_state == BundleState.confirmed
            and evaluation_mode == EvaluationMode.capability_full
            and level_ok
        )

        if not can_pass:
            return "warn"

        # ── R6: high-quality pass ─────────────────────────────────────────────
        if (
            score is not None
            and score >= _R6_SCORE_MIN
            and completeness >= _R6_COMPLETENESS_MIN
        ):
            return "pass"

        # ── R7: mid-range warn ────────────────────────────────────────────────
        return "warn"

    def requires_human_review(self, ctx: dict, review_status: str) -> bool:
        """
        Returns True when the run must enter awaiting_human_review:
        - R5 disagreement
        - Any warn result (queue for potential override)
        """
        return ctx.get("r5_triggered", False) or review_status == "warn"
