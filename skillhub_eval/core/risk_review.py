"""AI risk review — Step ③ (2.5); DeepSeek risk-only prompt."""

from __future__ import annotations

import json
import re

from .schemas.enums import RiskLevel

_RISK_ORDER = [RiskLevel.low, RiskLevel.medium, RiskLevel.high]


def merge_risk_levels(
    declared: RiskLevel,
    rule_level: RiskLevel,
    ai_level: RiskLevel | None,
) -> RiskLevel:
    """就高不就低；只抬不降。"""
    levels = [declared, rule_level]
    if ai_level is not None:
        levels.append(ai_level)
    return max(levels, key=lambda r: _RISK_ORDER.index(r))


def _parse_risk_level(raw: str | None) -> RiskLevel | None:
    if not raw:
        return None
    s = str(raw).strip().lower()
    try:
        return RiskLevel(s)
    except ValueError:
        return None


def build_risk_review_prompt(skill_md_text: str) -> str:
    excerpt = (skill_md_text or "").strip()[:2000]
    return (
        "你是 SkillHub 风险分级专员。仅根据 SKILL.md 判断 risk_level，"
        "禁止评估三维质量分或 pass/fail。\n"
        "关注：外部写入、资金交易、PII、权限提升、不可逆操作。\n"
        "\n【SKILL.md】\n"
        f"{excerpt or '(空)'}\n"
        "\n仅输出合法 JSON（勿 markdown 围栏）：\n"
        '{"suggested_risk":"low|medium|high",'
        '"confidence":"low|medium|high",'
        '"evidence_zh":"<1-2句中文依据>"}'
    )


def parse_risk_review_response(raw: dict | str) -> tuple[RiskLevel | None, str | None]:
    if isinstance(raw, str):
        text = raw.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return None, None
    if not isinstance(raw, dict):
        return None, None
    level = _parse_risk_level(raw.get("suggested_risk"))
    evidence = raw.get("evidence_zh")
    if evidence is not None:
        evidence = str(evidence)[:500]
    return level, evidence


async def review_risk_level(skill_md_text: str, ds_provider) -> tuple[RiskLevel | None, str | None]:
    """Call DeepSeek (ds_provider) for risk-only review. Returns (level, evidence_zh)."""
    prompt = build_risk_review_prompt(skill_md_text)
    try:
        raw = await ds_provider.judge(prompt)
        return parse_risk_review_response(raw)
    except Exception:
        return None, None
