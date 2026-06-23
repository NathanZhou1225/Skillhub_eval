"""Factory for the two judge provider slots."""

from __future__ import annotations

from skillhub_eval.settings import Settings

from .openai_compatible import OpenAICompatibleProvider


def build_judge_providers(
    settings: Settings,
) -> tuple[OpenAICompatibleProvider, OpenAICompatibleProvider]:
    return (
        OpenAICompatibleProvider(
            label=settings.judge_provider_a_label or "DeepSeek",
            api_key=settings.judge_provider_a_api_key or settings.deepseek_api_key,
            base_url=settings.judge_provider_a_base_url or settings.deepseek_base_url,
            model=settings.judge_provider_a_model or settings.deepseek_model,
            timeout=float(settings.provider_call_timeout_s),
        ),
        OpenAICompatibleProvider(
            label=settings.judge_provider_b_label or "Gemini",
            api_key=settings.judge_provider_b_api_key or settings.gemini_api_key,
            base_url=settings.judge_provider_b_base_url or settings.gemini_base_url,
            model=settings.judge_provider_b_model or settings.gemini_model,
            timeout=float(settings.provider_call_timeout_s),
        ),
    )
