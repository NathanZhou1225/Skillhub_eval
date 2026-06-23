"""
Dependency injection for FastAPI routes.

C-4 compliance: All dependencies are factory functions that can be cleanly
overridden in tests via `app.dependency_overrides[get_repo] = lambda: stub`.
No global state is mutated through these functions.
"""

from __future__ import annotations

from pathlib import Path

from skillhub_eval.core.ports import Repository
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.providers.base import BaseLLMProvider
from skillhub_eval.providers.factory import build_judge_providers
from skillhub_eval.settings import settings


def get_repo() -> Repository:
    db_path = settings.eval_db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    repo = SqliteRepository(db_path)
    repo.init_db()
    return repo


def get_ds_provider() -> BaseLLMProvider:
    provider_a, _ = build_judge_providers(settings)
    return provider_a


def get_gemini_provider() -> BaseLLMProvider:
    _, provider_b = build_judge_providers(settings)
    return provider_b
