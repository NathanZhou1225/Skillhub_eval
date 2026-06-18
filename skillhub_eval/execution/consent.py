"""Execution consent gate for local agent runs."""

from __future__ import annotations

from skillhub_eval.settings import settings

_consented_skill_ids: set[str] = set()


def grant_exec_consent(skill_id: str) -> None:
    _consented_skill_ids.add(skill_id)


def clear_exec_consent() -> None:
    _consented_skill_ids.clear()


def hydrate_exec_consent_from_db() -> None:
    """Sync in-memory consent gate from persisted sqlite preferences (survives serve restart)."""
    try:
        from skillhub_eval.execution.preferences import get_preferences

        if bool(get_preferences().get("consent_granted")):
            grant_exec_consent("*")
    except Exception:
        pass


def has_exec_consent(skill_id: str) -> bool:
    if not settings.exec_consent_required:
        return True
    if "*" in _consented_skill_ids or skill_id in _consented_skill_ids:
        return True
    try:
        from skillhub_eval.execution.preferences import get_preferences

        if bool(get_preferences().get("consent_granted")):
            grant_exec_consent("*")
            return True
    except Exception:
        pass
    return False
