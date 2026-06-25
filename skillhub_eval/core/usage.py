"""Token usage normalization and report aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skillhub_eval.core.schemas.report import (
    TokenUsageTotals,
    UsageSummary,
    UsageSummaryRow,
)


@dataclass(frozen=True)
class UsageRecord:
    stage: str
    usage: dict[str, Any] | None
    provider_label: str | None = None
    model: str | None = None
    case_id: str | None = None


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, int] | None:
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
    completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
    total = usage.get("total_tokens")
    try:
        prompt_i = int(prompt or 0)
        completion_i = int(completion or 0)
        total_i = int(total if total is not None else prompt_i + completion_i)
    except (TypeError, ValueError):
        return None
    if prompt_i == 0 and completion_i == 0 and total_i == 0:
        return None
    return {
        "prompt_tokens": prompt_i,
        "completion_tokens": completion_i,
        "total_tokens": total_i,
    }


def build_usage_summary(records: list[UsageRecord]) -> UsageSummary:
    rows: list[UsageSummaryRow] = []
    totals = TokenUsageTotals()
    partial = False
    for record in records:
        normalized = normalize_usage(record.usage)
        if normalized is None:
            partial = True
            continue
        rows.append(
            UsageSummaryRow(
                stage=record.stage,
                provider_label=record.provider_label,
                model=record.model,
                case_id=record.case_id,
                **normalized,
            )
        )
        totals.prompt_tokens += normalized["prompt_tokens"]
        totals.completion_tokens += normalized["completion_tokens"]
        totals.total_tokens += normalized["total_tokens"]
    return UsageSummary(totals=totals, by_stage=rows, partial=partial)
