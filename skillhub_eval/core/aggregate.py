"""
AggregateStage — implements 1.2 v1.2.1 §6.4 rules (C-2, grill-me 2026-06-02).

Key rules:
  R5: |DS.score_total - WB.score_total| >= 10
      OR DS.suggested_review_status != WB.suggested_review_status
         (one-pass-one-fail at bundle level)
      → score_total = null, source = null_due_to_disagreement

All other scores: aggregated_mean = round(mean(DS, WB), 1)
Redline fail: caller sets redline_fail=True → r1_r4_fail=True
"""

from __future__ import annotations


# R5 disagreement threshold (1.2 §6.4.3, NOT 15)
_R5_GAP_THRESHOLD = 10


class AggregateStage:
    """
    Aggregates dual-model votes per 1.2 §6.4 rules.

    Inputs
    ------
    votes           list[dict]  — model_vote dicts (model, score_total, suggested_review_status, ...)
    assertion_passed bool       — True if all code assertions passed
    completeness_score float    — completeness checklist score
    redline_fail    bool        — True if any redline case (refusal/adversarial) failed

    Returns
    -------
    dict with: r5_triggered, r1_r4_fail, score_total, score_total_source,
               completeness_score, reason_codes, ds_score, wb_score
    """

    def run(
        self,
        votes: list[dict],
        assertion_passed: bool,
        completeness_score: float,
        redline_fail: bool = False,
    ) -> dict:
        reason_codes: list[str] = []

        # R1–R4: hard fail propagation
        r1_r4_fail = redline_fail
        if redline_fail:
            reason_codes.append("REDLINE_CASE_FAIL")

        if not assertion_passed:
            reason_codes.append("ASSERTION_DSL_FAIL")

        # Separate votes by provider
        ds_votes = [v for v in votes if v.get("model") == "deepseek"]
        wb_votes = [v for v in votes if v.get("model") == "gemini"]

        ds_score: float | None = None
        wb_score: float | None = None

        if ds_votes:
            ds_score = round(
                sum(v["score_total"] for v in ds_votes) / len(ds_votes), 1
            )
        if wb_votes:
            wb_score = round(
                sum(v["score_total"] for v in wb_votes) / len(wb_votes), 1
            )

        # R5: disagreement detection
        r5_triggered = False
        score_total: float | None = None
        score_total_source = "not_applicable"

        if ds_score is not None and wb_score is not None:
            gap = abs(ds_score - wb_score)

            # Derive per-provider bundle-level status (majority vote if multiple cases)
            def _bundle_status(model_votes: list[dict]) -> str:
                statuses = [v.get("suggested_review_status", "warn") for v in model_votes]
                return "pass" if statuses.count("pass") > len(statuses) / 2 else "fail"

            ds_bundle_status = _bundle_status(ds_votes)
            wb_bundle_status = _bundle_status(wb_votes)
            status_mismatch = (
                (ds_bundle_status == "pass") != (wb_bundle_status == "pass")
            )

            if gap >= _R5_GAP_THRESHOLD or status_mismatch:
                r5_triggered = True
                score_total = None
                score_total_source = "null_due_to_disagreement"
                reason_codes.append("MODEL_DISAGREEMENT_R5")
            else:
                score_total = round((ds_score + wb_score) / 2, 1)
                score_total_source = "aggregated_mean"

        return {
            "r5_triggered": r5_triggered,
            "r1_r4_fail": r1_r4_fail,
            "score_total": score_total,
            "score_total_source": score_total_source,
            "completeness_score": completeness_score,
            "reason_codes": reason_codes,
            "ds_score": ds_score,
            "wb_score": wb_score,
        }
