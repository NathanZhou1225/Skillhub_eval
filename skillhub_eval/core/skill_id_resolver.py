"""Deterministic Skill ID resolution for Wave 5 bootstrap (EQ2 / EQ2b / EQ2c)."""

from __future__ import annotations

import re
from typing import Literal

from skillhub_eval.core.confirm_lexicon import is_confirm_message

SkillIdSource = Literal[
    "user_message",
    "explicit_request",
    "skill_md",
    "zip_name",
    "unknown",
]

_SKILL_ID_PATTERNS = (
    re.compile(
        r"(?:skill[_\s-]?id|技能[_\s-]?id|skill名称|skill name)\s*[:：=]\s*['\"]?([a-zA-Z0-9._-]+)",
        re.I,
    ),
    re.compile(r"^(?:skill_id|id)\s*[:：=]\s*['\"]?([a-zA-Z0-9._-]+)", re.I),
)

SOURCE_LABELS = {
    "user_message": "用户消息",
    "explicit_request": "用户指定",
    "skill_md": "SKILL.md",
    "zip_name": "压缩包文件名",
    "unknown": "未知",
}


def _normalize_skill_id(raw: str) -> str:
    return raw.strip().strip("\"'").lower()


def parse_user_message_skill_id(message: str | None) -> str | None:
    if not message or not message.strip():
        return None
    for pattern in _SKILL_ID_PATTERNS:
        match = pattern.search(message.strip())
        if match:
            return _normalize_skill_id(match.group(1))
    return None


def _skill_id_from_bundle(bundle: dict) -> str | None:
    meta = bundle.get("skill_meta") or {}
    for key in ("id", "name", "skill_id"):
        value = meta.get(key)
        if value:
            return _normalize_skill_id(str(value))
    bundled = bundle.get("skill_id")
    if bundled:
        return _normalize_skill_id(str(bundled))
    return None


def resolve_skill_id(
    *,
    user_message: str | None = None,
    explicit_skill_id: str | None = None,
    bundle: dict | None = None,
    zip_stem: str | None = None,
) -> tuple[str | None, SkillIdSource, list[str]]:
    """
    Resolve skill_id with priority:
      user message > explicit request > SKILL.md > zip stem.
    """
    warnings: list[str] = []

    from_user = parse_user_message_skill_id(user_message)
    if from_user:
        if bundle:
            from_md = _skill_id_from_bundle(bundle)
            if from_md and from_md != from_user:
                warnings.append(
                    f"用户指定的 Skill ID ({from_user}) 与包内元数据 ({from_md}) 不一致，以用户消息为准。"
                )
        return from_user, "user_message", warnings

    if explicit_skill_id and explicit_skill_id.strip():
        return _normalize_skill_id(explicit_skill_id), "explicit_request", warnings

    if bundle:
        from_md = _skill_id_from_bundle(bundle)
        if from_md:
            return from_md, "skill_md", warnings

    if zip_stem:
        stem = _normalize_skill_id(zip_stem)
        if stem:
            return stem, "zip_name", warnings

    return None, "unknown", warnings


def needs_user_confirm(source: SkillIdSource) -> bool:
    """EQ2c: only auto-identified sources require user confirmation."""
    return source in ("skill_md", "zip_name")


def is_confirm_reply(message: str) -> bool:
    return is_confirm_message(message)


def source_label(source: SkillIdSource) -> str:
    return SOURCE_LABELS.get(source, source)
