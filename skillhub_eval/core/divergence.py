"""Per-case model disagreement synthesis (Wave 5.4)."""

from __future__ import annotations

import asyncio
import json
import re
from typing import TYPE_CHECKING

from skillhub_eval.settings import settings

if TYPE_CHECKING:
    from skillhub_eval.core.ports import Repository
    from skillhub_eval.providers.base import BaseLLMProvider

_GAP_TRIGGER = 15.0
_DIMENSIONS = (
    "instruction_following",
    "output_compliance",
    "business_resolution",
)
_DIM_ZH = {
    "instruction_following": "指令遵循",
    "output_compliance": "输出合规",
    "business_resolution": "业务解决",
}


def compute_max_gap_dimension(
    ds_sub: dict | None,
    gm_sub: dict | None,
) -> tuple[str | None, float]:
    max_dim: str | None = None
    max_gap = 0.0
    ds_sub = ds_sub if isinstance(ds_sub, dict) else {}
    gm_sub = gm_sub if isinstance(gm_sub, dict) else {}

    for dim in _DIMENSIONS:
        ds_entry = ds_sub.get(dim)
        gm_entry = gm_sub.get(dim)
        ds_score = ds_entry.get("score") if isinstance(ds_entry, dict) else None
        gm_score = gm_entry.get("score") if isinstance(gm_entry, dict) else None
        if ds_score is None or gm_score is None:
            continue
        gap = abs(float(ds_score) - float(gm_score))
        if gap > max_gap:
            max_gap = gap
            max_dim = dim
    return max_dim, max_gap


def _votes_by_case(votes: list[dict]) -> dict[str, dict[str, dict]]:
    grouped: dict[str, dict[str, dict]] = {}
    for vote in votes:
        case_id = vote.get("case_id", "?")
        model = vote.get("model", "")
        grouped.setdefault(case_id, {})[model] = vote
    return grouped


def _case_gap(ds_vote: dict | None, gm_vote: dict | None) -> float | None:
    if not ds_vote or not gm_vote:
        return None
    ds_s = ds_vote.get("score_total")
    gm_s = gm_vote.get("score_total")
    if ds_s is None or gm_s is None:
        return None
    return round(abs(float(ds_s) - float(gm_s)), 1)


def build_single_sided_divergence(
    case_id: str,
    provider_errors: list[dict],
) -> dict:
    errors = [e for e in provider_errors if e.get("case_id") == case_id]
    return {
        "gap": None,
        "max_gap_dimension": None,
        "synthesis_zh": "",
        "degraded": False,
        "single_sided": True,
        "provider_errors": errors,
    }


def build_synthesis_prompt(
    case_id: str,
    case_type: str,
    ds_vote: dict,
    gm_vote: dict,
    max_gap_dimension: str | None,
) -> str:
    dim_label = _DIM_ZH.get(max_gap_dimension or "", max_gap_dimension or "未知")
    return (
        "你是 SkillHub 评估分歧解读专员。根据两侧模型的评分依据，"
        "用中文写一段不超过300字的分歧根因说明。\n"
        f"case_id: {case_id}\ncase_type: {case_type}\n"
        f"分歧最大维度（已计算，勿改）: {dim_label}\n"
        f"DeepSeek 总分: {ds_vote.get('score_total')}\n"
        f"Gemini 总分: {gm_vote.get('score_total')}\n"
        f"DeepSeek sub_scores: {json.dumps(ds_vote.get('dimension_scores', ds_vote.get('sub_scores', {})), ensure_ascii=False)}\n"
        f"Gemini sub_scores: {json.dumps(gm_vote.get('dimension_scores', gm_vote.get('sub_scores', {})), ensure_ascii=False)}\n"
        "说明：两模型逻辑差异在哪、谁的依据更贴 SKILL 原文。只输出正文，不要 JSON。"
    )


def parse_synthesis_text(raw: str) -> str:
    text = (raw or "").strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return text[:300]


async def _synthesize_one(
    repo: Repository,
    run_id: str,
    case_id: str,
    case_type: str,
    ds_vote: dict,
    gm_vote: dict,
    ds_provider: BaseLLMProvider,
    timeout_s: float,
) -> None:
    ds_sub = ds_vote.get("dimension_scores") or ds_vote.get("sub_scores") or {}
    gm_sub = gm_vote.get("dimension_scores") or gm_vote.get("sub_scores") or {}
    max_dim, _ = compute_max_gap_dimension(ds_sub, gm_sub)
    gap = _case_gap(ds_vote, gm_vote) or 0.0
    prompt = build_synthesis_prompt(case_id, case_type, ds_vote, gm_vote, max_dim)
    degraded = False
    synthesis_zh = ""
    try:
        if hasattr(ds_provider, "generate"):
            raw = await asyncio.wait_for(
                ds_provider.generate(prompt),
                timeout=timeout_s,
            )
            synthesis_zh = parse_synthesis_text(raw)
        else:
            degraded = True
    except (asyncio.TimeoutError, OSError, RuntimeError, ValueError):
        degraded = True

    divergence = {
        "gap": gap,
        "max_gap_dimension": max_dim,
        "synthesis_zh": synthesis_zh,
        "degraded": degraded,
        "single_sided": False,
    }
    repo.update_judge_trace_divergence(run_id, case_id, divergence)


async def synthesize_divergences_for_run(
    run_id: str,
    votes: list[dict],
    repo: Repository,
    ds_provider: BaseLLMProvider,
    *,
    timeout_s: float | None = None,
) -> None:
    """GQ1/GQ2: parallel synthesis for gap>=15; single-sided deterministic cards."""
    if timeout_s is None:
        timeout_s = float(settings.divergence_synthesis_timeout_s)

    grouped = _votes_by_case(votes)
    provider_errors = repo.get_provider_errors(run_id)
    tasks: list[asyncio.Task] = []

    for case_id, by_model in grouped.items():
        ds_vote = by_model.get("deepseek")
        gm_vote = by_model.get("gemini")
        case_type = (ds_vote or gm_vote or {}).get("case_type", "happy_path")

        if not ds_vote or not gm_vote:
            div = build_single_sided_divergence(case_id, provider_errors)
            repo.update_judge_trace_divergence(run_id, case_id, div)
            continue

        gap = _case_gap(ds_vote, gm_vote)
        if gap is None or gap < _GAP_TRIGGER:
            continue

        tasks.append(
            asyncio.create_task(
                _synthesize_one(
                    repo,
                    run_id,
                    case_id,
                    case_type,
                    ds_vote,
                    gm_vote,
                    ds_provider,
                    timeout_s,
                )
            )
        )

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
