"""Parse and validate per-case judge LLM JSON (Wave 5.4 / GQ6)."""

from __future__ import annotations

import json
import re

_DIMENSIONS = (
    "instruction_following",
    "output_compliance",
    "business_resolution",
)

_MD_FENCE_RE = re.compile(r"^```(?:json)?\s*([\s\S]*?)```\s*$", re.MULTILINE)


def _strip_fences(text: str) -> str:
    text = text.strip()
    match = _MD_FENCE_RE.match(text)
    if match:
        return match.group(1).strip()
    inline = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if inline:
        return inline.group(1).strip()
    return text


def parse_judge_response(raw: dict | str) -> dict:
    """
    Normalize judge JSON. Requires sub_scores.*.score; analysis fields optional.
    """
    if isinstance(raw, str):
        raw = json.loads(_strip_fences(raw))
    if not isinstance(raw, dict):
        raise ValueError("judge response must be a JSON object")

    sub_scores = raw.get("sub_scores")
    if not isinstance(sub_scores, dict):
        raise ValueError("sub_scores must be an object")

    raw["sub_scores"] = _normalize_sub_scores(sub_scores)
    return raw


def _normalize_sub_scores(sub_scores: dict) -> dict:
    """Ensure rubric dimensions exist; backfill from legacy keys (e.g. step_completeness)."""
    out = dict(sub_scores)
    if all(
        isinstance(out.get(dim), dict) and out[dim].get("score") is not None
        for dim in _DIMENSIONS
    ):
        return out

    fallback_entry: dict | None = None
    for key in (*_DIMENSIONS, "step_completeness"):
        entry = out.get(key)
        if isinstance(entry, dict) and entry.get("score") is not None:
            fallback_entry = entry
            break
    if fallback_entry is None:
        for entry in out.values():
            if isinstance(entry, dict) and entry.get("score") is not None:
                fallback_entry = entry
                break
    if fallback_entry is None:
        raise ValueError("missing score in sub_scores")

    score = fallback_entry["score"]
    for dim in _DIMENSIONS:
        entry = out.get(dim)
        if isinstance(entry, dict) and entry.get("score") is not None:
            continue
        out[dim] = {
            "score": score,
            "pass": fallback_entry.get("pass", float(score) >= 70),
            "reason": fallback_entry.get("reason", ""),
        }
        for optional in ("analysis", "evidence_quotes", "deductions", "evidence_refs"):
            if optional in fallback_entry:
                out[dim][optional] = fallback_entry[optional]
    return out
