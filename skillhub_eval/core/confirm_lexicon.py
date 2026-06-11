"""Unified confirm / synonym detection for LUI gates (Wave 5.3)."""

from __future__ import annotations

CONFIRM_SYNONYMS = frozenset(
    {
        "确认",
        "确定",
        "对",
        "是的",
        "yes",
        "ok",
        "好",
        "好的",
        "可以",
        "正确",
        "没错",
        "行",
        "同意",
        "y",
        "yeah",
    }
)

_DRAFT_CONFIRM_PREFIXES = (
    "确认",
    "可以",
    "按这个补",
    "没问题",
    "好的",
    "好",
    "行",
    "同意",
    "确定",
)


def is_confirm_message(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    if normalized in CONFIRM_SYNONYMS:
        return True
    return normalized in {s.lower() for s in CONFIRM_SYNONYMS if s.isascii()}


def is_draft_confirm_message(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    if is_confirm_message(normalized):
        return True
    lowered = normalized.lower()
    return any(
        lowered == prefix or lowered.startswith(prefix)
        for prefix in _DRAFT_CONFIRM_PREFIXES
    )
