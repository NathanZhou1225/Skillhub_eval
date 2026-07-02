"""Build provider_summary for reports (T5 — R5 dual-model visualization)."""

from __future__ import annotations

from .schemas.report import CaseScoreRow, ExecResult, ProviderSummary

_R5_UI_HIGHLIGHT_GAP = 15


def _bundle_status(model_votes: list[dict]) -> str:
    statuses = [v.get("suggested_review_status", "warn") for v in model_votes]
    return "pass" if statuses.count("pass") > len(statuses) / 2 else "fail"


def build_provider_summary(
    votes: list[dict],
    agg: dict,
    *,
    provider_a_label: str = "DeepSeek",
    provider_b_label: str = "Gemini",
    exec_results: dict[str, ExecResult] | None = None,
) -> ProviderSummary:
    """
    Derive bundle-level and per-case scores from raw votes + aggregate output.
    """
    ds_votes = [v for v in votes if v.get("model") == "deepseek"]
    wb_votes = [v for v in votes if v.get("model") == "gemini"]

    ds_score = agg.get("ds_score")
    wb_score = agg.get("wb_score")
    score_gap: float | None = None
    if ds_score is not None and wb_score is not None:
        score_gap = round(abs(ds_score - wb_score), 1)

    ds_bundle_status = _bundle_status(ds_votes) if ds_votes else None
    wb_bundle_status = _bundle_status(wb_votes) if wb_votes else None

    case_ids: list[str] = []
    seen: set[str] = set()
    for v in votes:
        cid = v.get("case_id", "?")
        if cid not in seen:
            seen.add(cid)
            case_ids.append(cid)

    per_case: list[CaseScoreRow] = []
    for case_id in case_ids:
        ds_v = next((v for v in ds_votes if v.get("case_id") == case_id), None)
        wb_v = next((v for v in wb_votes if v.get("case_id") == case_id), None)
        ds_s = ds_v["score_total"] if ds_v else None
        wb_s = wb_v["score_total"] if wb_v else None
        gap: float | None = None
        if ds_s is not None and wb_s is not None:
            gap = round(abs(ds_s - wb_s), 1)
        exec_result = (exec_results or {}).get(case_id)
        per_case.append(
            CaseScoreRow(
                case_id=case_id,
                deepseek_score=ds_s,
                gemini_score=wb_s,
                gap=gap,
                ds_suggested_status=(
                    ds_v.get("suggested_review_status") if ds_v else None
                ),
                gemini_suggested_status=(
                    wb_v.get("suggested_review_status") if wb_v else None
                ),
                exec_status=exec_result.status if exec_result else None,
                exec_degrade_reason=exec_result.degrade_reason if exec_result else None,
            )
        )

    return ProviderSummary(
        provider_a_label=provider_a_label,
        provider_b_label=provider_b_label,
        deepseek_score=ds_score,
        gemini_score=wb_score,
        score_gap=score_gap,
        r5_triggered=bool(agg.get("r5_triggered")),
        deepseek_bundle_status=ds_bundle_status,
        gemini_bundle_status=wb_bundle_status,
        per_case=per_case,
    )


def per_case_row_highlight(row: CaseScoreRow) -> bool:
    """UI helper: Δ≥15 for expert table highlighting (grill-me Q4)."""
    return row.gap is not None and row.gap >= _R5_UI_HIGHLIGHT_GAP
