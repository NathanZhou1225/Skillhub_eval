"""Execution consent gate for local agent runs."""

from __future__ import annotations

from skillhub_eval.settings import settings

_consented_skill_ids: set[str] = set()


def grant_exec_consent(skill_id: str) -> None:
    _consented_skill_ids.add(skill_id)


def clear_exec_consent() -> None:
    _consented_skill_ids.clear()


def has_exec_consent(skill_id: str) -> bool:
    if not settings.exec_consent_required:
        return True
    return "*" in _consented_skill_ids or skill_id in _consented_skill_ids
