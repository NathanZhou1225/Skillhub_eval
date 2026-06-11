"""LLM enrichment for propagation_plan rows — Wave 5.3."""

from __future__ import annotations

import json
import re
from typing import Any

import logging

from skillhub_eval.core.propagation_plan import TYPE_ZH
from skillhub_eval.core.propagator import TYPE_DESCRIPTIONS
from skillhub_eval.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

_MD_FENCE_RE = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.IGNORECASE)
_MAX_EXCERPT = 3000


def _skill_excerpt(skill_md_text: str) -> str:
    text = (skill_md_text or "").strip()
    if len(text) <= _MAX_EXCERPT:
        return text
    return text[:_MAX_EXCERPT] + "\n…（摘录截断）"


def _parse_enrich_payload(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ValueError("unsupported enrich response")
    text = raw.strip()
    fenced = _MD_FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("enrich payload not object")
    return parsed


def _apply_row_enrichment(plan: dict, enriched_rows: list[dict]) -> None:
    by_type = {
        str(row.get("type", "")).strip(): row
        for row in enriched_rows
        if isinstance(row, dict) and row.get("type")
    }
    for row in plan.get("rows") or []:
        if not isinstance(row, dict):
            continue
        case_type = str(row.get("type", ""))
        enriched = by_type.get(case_type)
        if not enriched:
            row["enrichment_source"] = "deterministic"
            continue
        if enriched.get("tests_what"):
            row["tests_what"] = str(enriched["tests_what"]).strip()
        if enriched.get("business_expectation"):
            row["business_expectation"] = str(enriched["business_expectation"]).strip()
        note = enriched.get("redline_note")
        if note:
            row["redline_note"] = str(note).strip()
        row["enrichment_source"] = "llm"


def _degraded_business_expectation(case_type: str) -> str:
    type_zh = TYPE_ZH.get(case_type, case_type)
    base = TYPE_DESCRIPTIONS.get(case_type, "")
    if base:
        return f"在{type_zh}下：{base}"
    return f"验证本 Skill 在{type_zh}场景下的行为符合 SKILL.md 描述。"


async def _llm_json_object(ds_provider: BaseLLMProvider, prompt: str) -> dict:
    """Prefer generate()+fence parse; judge() only accepts strict JSON bodies."""
    generate = getattr(ds_provider, "generate", None)
    if callable(generate):
        return _parse_enrich_payload(await generate(prompt))
    return _parse_enrich_payload(await ds_provider.judge(prompt))


async def enrich_propagation_plan(
    plan: dict,
    *,
    skill_md_text: str,
    skill_id: str,
    category_slug: str,
    clarifications: dict | None,
    ds_provider: BaseLLMProvider,
) -> dict:
    """Fill rows with Skill-specific copy; degrade to deterministic on failure."""
    rows = plan.get("rows") or []
    if not rows:
        plan["enrichment_status"] = "skipped"
        plan["enrichment_snapshot"] = {"skill_id": skill_id, "rows": []}
        return plan

    row_specs = [
        {
            "type": r.get("type"),
            "type_zh": r.get("type_zh"),
            "gap_count": r.get("gap_count", r.get("gap", 0)),
        }
        for r in rows
        if isinstance(r, dict)
    ]
    clarifications_json = json.dumps(clarifications or {}, ensure_ascii=False)
    rows_json = json.dumps(row_specs, ensure_ascii=False)
    prompt = (
        "你是 SkillHub 评估规划助手。根据 Skill 说明，为补题计划每一行生成 Skill 专属的评估文案。\n"
        "输出必须是单个 JSON 对象，不允许 markdown 代码块。\n"
        '格式: {"rows":[{"type":"happy_path","tests_what":"...","business_expectation":"...",'
        '"redline_note":"..."}]}\n'
        "规则:\n"
        "1) 每行 tests_what / business_expectation 必须不同且贴合 Skill，禁止泛泛模板。\n"
        "2) refusal/adversarial 的 redline_note 写清拒绝边界；其他类型 redline_note 可为空字符串。\n"
        "3) 不得编造 Skill 未声明的能力或 API。\n"
        "4) 对用户可见概念用「评估条件/评估场景」，避免只说「题型」。\n"
        "5) tests_what / business_expectation / redline_note 必须使用简体中文，禁止英文句子。\n"
        f"skill_id: {skill_id}\n"
        f"category: {category_slug or 'unknown'}\n"
        f"clarifications: {clarifications_json}\n"
        f"rows_to_enrich: {rows_json}\n"
        f"SKILL.md 摘录:\n{_skill_excerpt(skill_md_text)}\n"
    )
    try:
        payload = await _llm_json_object(ds_provider, prompt)
        enriched_rows = payload.get("rows")
        if not isinstance(enriched_rows, list):
            raise ValueError("rows missing")
        _apply_row_enrichment(plan, enriched_rows)
        plan["enrichment_status"] = "ok"
    except Exception as exc:
        logger.warning("propagation_plan enrich degraded: %s", exc)
        for row in rows:
            if isinstance(row, dict):
                case_type = str(row.get("type", ""))
                row["enrichment_source"] = "deterministic"
                row["tests_what"] = TYPE_DESCRIPTIONS.get(case_type, case_type)
                row["business_expectation"] = _degraded_business_expectation(case_type)
        plan["enrichment_status"] = "degraded"
        plan["enrichment_degraded_hint"] = (
            "补题计划说明未能由模型个性化生成（可能超时或解析失败），已使用分场景中文模板。"
            "可通过对话补充场景后刷新计划。"
        )

    plan["enrichment_snapshot"] = {
        "skill_id": skill_id,
        "rows": [
            {
                "type": r.get("type"),
                "tests_what": r.get("tests_what"),
                "business_expectation": r.get("business_expectation"),
            }
            for r in rows
            if isinstance(r, dict)
        ],
    }
    return plan
