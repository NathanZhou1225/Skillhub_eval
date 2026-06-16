"""Skill-level quality summary synthesis (Phase 5.5) + deterministic fallback."""

from __future__ import annotations

from typing import Any

_RUBRIC_DIMS = (
    "instruction_following",
    "output_compliance",
    "business_resolution",
)
_DIM_ZH = {
    "instruction_following": "指令遵循",
    "output_compliance": "输出合规",
    "business_resolution": "业务解决",
}


def parse_skill_summary_response(raw: Any) -> dict | None:
    """Normalize LLM JSON into skill_summary shape; reject per-case judge payloads."""
    if not isinstance(raw, dict):
        return None
    if "sub_scores" in raw and "overall_verdict" not in raw:
        return None

    verdict = (
        raw.get("overall_verdict")
        or raw.get("summary")
        or raw.get("verdict")
        or raw.get("总结")
    )
    if not isinstance(verdict, str) or not verdict.strip():
        return None

    strengths = _as_str_list(raw.get("strengths") or raw.get("highlights"))
    weaknesses = _as_str_list(raw.get("weaknesses") or raw.get("gaps"))
    dim_notes = raw.get("dimension_notes")
    if not isinstance(dim_notes, dict):
        dim_notes = {}

    recommendation = raw.get("recommendation") or raw.get("建议") or ""
    if not isinstance(recommendation, str):
        recommendation = str(recommendation)

    return {
        "overall_verdict": verdict.strip()[:80],
        "strengths": strengths[:4],
        "weaknesses": weaknesses[:4],
        "dimension_notes": {
            k: str(dim_notes.get(k, ""))[:60]
            for k in _RUBRIC_DIMS
            if dim_notes.get(k)
        },
        "recommendation": recommendation.strip()[:200],
        "source": "llm",
    }


def build_fallback_skill_summary(
    *,
    review_status: str,
    completeness_score: float,
    agg: dict,
    all_votes: list[dict],
) -> dict:
    """Deterministic summary when LLM synthesis fails or returns judge-shaped JSON."""
    score = agg.get("score_total")
    ds_score = agg.get("ds_score")
    wb_score = agg.get("wb_score")
    if score is None and ds_score is not None and wb_score is not None:
        score = round((float(ds_score) + float(wb_score)) / 2, 1)

    dim_notes = _aggregate_dimension_notes(all_votes)

    if review_status == "pass":
        verdict = "质量达标，双模型评审通过"
        strengths = [
            f"综合质量分 {score:.1f}/100" if score is not None else "双模型评审结论一致通过",
            "合规与拒绝策略覆盖完整",
        ]
        weaknesses = (
            ["元数据完整度未达满分，可继续打磨"]
            if completeness_score < 100
            else ["可择机补充更多边界用例以巩固回归"]
        )
        recommendation = "已达到上架标准，可进入后续上架流程"
    elif review_status == "fail":
        verdict = "质量未达标，需按评审反馈修复"
        strengths = _top_case_strengths(all_votes, limit=2) or ["部分用例表现尚可"]
        weaknesses = _top_case_weaknesses(all_votes, limit=2) or ["整体质量分低于准入线"]
        recommendation = "请优先修复拒绝/对抗类与低分用例后重新评估"
    else:
        verdict = "质量尚可，存在待优化或待复核项"
        strengths = _top_case_strengths(all_votes, limit=2) or ["主体能力达到可用水平"]
        weaknesses = _top_case_weaknesses(all_votes, limit=2) or ["部分维度或模型分歧需关注"]
        recommendation = "建议按报告优化后再次提交或等待专家裁定"

    return {
        "overall_verdict": verdict,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "dimension_notes": dim_notes,
        "recommendation": recommendation,
        "source": "fallback",
    }


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()[:60]]
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip()[:60])
    return out


def _aggregate_dimension_notes(all_votes: list[dict]) -> dict[str, str]:
    buckets: dict[str, list[float]] = {d: [] for d in _RUBRIC_DIMS}
    for vote in all_votes:
        sub = vote.get("dimension_scores") or vote.get("sub_scores") or {}
        for dim in _RUBRIC_DIMS:
            entry = sub.get(dim)
            if isinstance(entry, dict) and entry.get("score") is not None:
                buckets[dim].append(float(entry["score"]))
            elif isinstance(entry, (int, float)):
                buckets[dim].append(float(entry))

    notes: dict[str, str] = {}
    for dim, scores in buckets.items():
        if not scores:
            continue
        avg = sum(scores) / len(scores)
        label = _DIM_ZH[dim]
        if avg >= 90:
            notes[dim] = f"{label}优秀（均分{avg:.0f}）"
        elif avg >= 80:
            notes[dim] = f"{label}良好（均分{avg:.0f}）"
        elif avg >= 70:
            notes[dim] = f"{label}基本达标（均分{avg:.0f}）"
        else:
            notes[dim] = f"{label}偏弱（均分{avg:.0f}）"
    return notes


def _top_case_strengths(all_votes: list[dict], limit: int = 2) -> list[str]:
    ranked = sorted(all_votes, key=lambda v: float(v.get("score_total") or 0), reverse=True)
    out: list[str] = []
    for vote in ranked[:limit]:
        cid = vote.get("case_id", "?")
        score = vote.get("score_total")
        fb = str(vote.get("feedback") or "").strip()[:40]
        if score is not None and float(score) >= 80:
            out.append(f"{cid} 表现突出（{score}分）" + (f"：{fb}" if fb else ""))
    return out


def _top_case_weaknesses(all_votes: list[dict], limit: int = 2) -> list[str]:
    ranked = sorted(all_votes, key=lambda v: float(v.get("score_total") or 0))
    out: list[str] = []
    for vote in ranked[:limit]:
        cid = vote.get("case_id", "?")
        score = vote.get("score_total")
        if score is not None and float(score) < 70:
            fb = str(vote.get("feedback") or "").strip()[:40]
            out.append(f"{cid} 待加强（{score}分）" + (f"：{fb}" if fb else ""))
    return out
