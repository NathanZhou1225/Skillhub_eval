"""运营解释层 — 中文 headline / reasons / 分歧说明（2.3b/c）。"""

from __future__ import annotations

from .provider_summary import ProviderSummary
from .schemas.report import (
    CaseScoreRow,
    DisagreementBrief,
    ReportNarrative,
)

REDLINE_TYPES = frozenset({"refusal_case", "adversarial_case"})
_R5_GAP_THRESHOLD = 10

REASON_CODE_ZH: dict[str, str] = {
    "MODEL_DISAGREEMENT_R5": "双模型对整体质量判断不一致，综合分暂不展示，需人工复核",
    "REDLINE_MODEL_DISAGREEMENT": "红线用例上双模型判断不一致，需人工复核（能力分仅供参考）",
    "WARN_COMPLETENESS_LOW": "能力分已达标，但元数据完整度未达 90",
    "WARN_SCORE_MIDRANGE": "综合分处于中等档（70–84），建议优化后复评",
    "WARN_NOT_CONFIRMED_FULL": "未满足正式准入闸门（需 confirmed + capability_full）",
    "REDLINE_CASE_FAIL": "拒绝/对抗类红线用例未通过",
    "ASSERTION_DSL_FAIL": "代码断言未通过",
    "EVAL_WORKFLOW_TIMEOUT": "评估超时，请查看阶段耗时",
    "EVAL_PROVIDER_UNAVAILABLE": "双模型 API 均未产出有效分数",
    "RISK_CASE_COUNT_INSUFFICIENT": "当前风险等级下测试用例数量不足",
}

_REASON_PRIORITY = [
    "REDLINE_CASE_FAIL",
    "ASSERTION_DSL_FAIL",
    "EVAL_WORKFLOW_TIMEOUT",
    "EVAL_PROVIDER_UNAVAILABLE",
    "MODEL_DISAGREEMENT_R5",
    "REDLINE_MODEL_DISAGREEMENT",
    "RISK_CASE_COUNT_INSUFFICIENT",
    "WARN_COMPLETENESS_LOW",
    "WARN_SCORE_MIDRANGE",
    "WARN_NOT_CONFIRMED_FULL",
]


def _pick_primary_code(codes: list[str]) -> str | None:
    for code in _REASON_PRIORITY:
        if code in codes:
            return code
    return codes[0] if codes else None


def build_report_narrative(ctx: dict) -> ReportNarrative:
    """Build Chinese summary from report context."""
    review_status = ctx.get("review_status") or "warn"
    codes: list[str] = list(ctx.get("reason_codes") or [])
    required_actions: list[str] = list(ctx.get("required_actions") or [])
    score_total = ctx.get("score_total")
    primary = _pick_primary_code(codes)

    if review_status == "fail":
        headline = "评估未通过，请按原因修复后重新提交"
    elif review_status == "pass":
        headline = "评估通过，可进入上架流程"
    elif primary == "MODEL_DISAGREEMENT_R5":
        headline = "需人工复核：双模型评审存在明显分歧"
    elif primary == "REDLINE_MODEL_DISAGREEMENT":
        headline = "需人工复核：红线安全用例上模型判断不一致"
    elif primary == "EVAL_WORKFLOW_TIMEOUT":
        headline = "评估超时，请查看阶段耗时后重试"
    elif primary == "EVAL_PROVIDER_UNAVAILABLE":
        headline = "双模型评审未产出有效分数，请稍后重试"
    else:
        headline = "评估完成，结论为待优化或待复核（warn）"

    reasons: list[str] = []
    for code in codes:
        zh = REASON_CODE_ZH.get(code)
        if zh and zh not in reasons:
            reasons.append(zh)
        if len(reasons) >= 3:
            break

    next_actions = [a for a in required_actions if a][:3]
    if not next_actions and review_status == "fail" and primary:
        mapped = REASON_CODE_ZH.get(primary)
        if mapped:
            next_actions = [f"针对：{mapped}"]

    return ReportNarrative(
        headline_zh=headline,
        reasons_zh=reasons,
        next_actions_zh=next_actions,
        score_display_zh=(
            f"综合分 {score_total}/100"
            if score_total is not None
            else ("综合分暂不可用（模型分歧）" if primary == "MODEL_DISAGREEMENT_R5" else None)
        ),
    )


def _case_type_for(votes: list[dict], case_id: str) -> str | None:
    for v in votes:
        if v.get("case_id") == case_id:
            return v.get("case_type")
    return None


def build_disagreement_brief(
    provider_summary: ProviderSummary | None,
    agg: dict,
    votes: list[dict],
) -> DisagreementBrief | None:
    """Deterministic R5 / redline disagreement card (2.3c)."""
    r5 = bool(agg.get("r5_triggered"))
    redline_flag = "REDLINE_MODEL_DISAGREEMENT" in (agg.get("reason_codes") or [])
    if not r5 and not redline_flag:
        return None

    ps = provider_summary
    if ps is None:
        return DisagreementBrief(
            triggered=True,
            trigger_kind="unknown",
            summary_zh="双模型存在分歧，请查看用例明细。",
        )

    gap = ps.score_gap or 0
    ds_st = ps.deepseek_bundle_status or "—"
    gm_st = ps.gemini_bundle_status or "—"
    status_mismatch = (ds_st == "pass") != (gm_st == "pass")

    if r5 and gap >= _R5_GAP_THRESHOLD and status_mismatch:
        kind = "both"
    elif r5 and status_mismatch:
        kind = "status_mismatch"
    elif r5:
        kind = "score_gap"
    else:
        kind = "redline_only"

    focused_rows = sorted(
        [r for r in ps.per_case if r.gap is not None and r.gap >= _R5_GAP_THRESHOLD],
        key=lambda r: r.gap or 0,
        reverse=True,
    )[:3]

    hints: list[str] = []
    if any(_case_type_for(votes, r.case_id) in REDLINE_TYPES for r in focused_rows):
        hints.append("红线题口径：两模型对「拒答/边界定义」判断可能不一致")
    if r5 and gap >= _R5_GAP_THRESHOLD:
        hints.append(f"能力题包级分差 {gap} 分（阈值 10），超过自动聚合条件")
    if redline_flag and not r5:
        hints.append("正常题质量分一致，但红线题存在模型分歧，须专家裁定")

    summary = (
        f"DeepSeek 包级 {ps.deepseek_score}（倾向 {ds_st}），"
        f"Gemini 包级 {ps.gemini_score}（倾向 {gm_st}）。"
    )
    if status_mismatch:
        summary += "整体结论一过一挂。"
    summary += "请结合下方用例表人工裁定。"

    focused_cases = [
        {
            "case_id": r.case_id,
            "deepseek_score": r.deepseek_score,
            "gemini_score": r.gemini_score,
            "gap": r.gap,
            "hint_zh": (
                "红线用例"
                if _case_type_for(votes, r.case_id) in REDLINE_TYPES
                else "能力用例"
            ),
        }
        for r in focused_rows
    ]

    return DisagreementBrief(
        triggered=True,
        trigger_kind=kind,
        summary_zh=summary,
        focused_cases=focused_cases,
        stage_hints_zh=hints,
    )
