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
from skillhub_eval.providers.deepseek import DeepSeekProvider
from skillhub_eval.providers.gemini import GeminiProvider
from skillhub_eval.settings import settings


def get_repo() -> Repository:
    db_path = settings.eval_db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    repo = SqliteRepository(db_path)
    repo.init_db()
    return repo


def get_ds_provider() -> DeepSeekProvider:
    return DeepSeekProvider(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        timeout=float(settings.provider_call_timeout_s),
    )


def get_gemini_provider() -> GeminiProvider:
    return GeminiProvider(
        api_key=settings.gemini_api_key,
        base_url=settings.gemini_base_url,
        model=settings.gemini_model,
        timeout=float(settings.provider_call_timeout_s),
    )
