import json

import httpx
import pytest
import respx

from skillhub_eval.providers.factory import build_judge_providers
from skillhub_eval.providers.openai_compatible import OpenAICompatibleProvider
from skillhub_eval.settings import Settings


def test_build_judge_providers_uses_new_env_driven_slots():
    cfg = Settings(
        _env_file=None,
        judge_provider_a_label="Model A",
        judge_provider_a_api_key="key-a",
        judge_provider_a_base_url="https://a.example/v1",
        judge_provider_a_model="a-model",
        judge_provider_b_label="Model B",
        judge_provider_b_api_key="key-b",
        judge_provider_b_base_url="https://b.example/v1",
        judge_provider_b_model="b-model",
        provider_call_timeout_s=123,
    )

    provider_a, provider_b = build_judge_providers(cfg)

    assert isinstance(provider_a, OpenAICompatibleProvider)
    assert provider_a.label == "Model A"
    assert provider_a.api_key == "key-a"
    assert provider_a.base_url == "https://a.example/v1"
    assert provider_a.model == "a-model"
    assert provider_a.timeout == 123

    assert isinstance(provider_b, OpenAICompatibleProvider)
    assert provider_b.label == "Model B"
    assert provider_b.api_key == "key-b"
    assert provider_b.base_url == "https://b.example/v1"
    assert provider_b.model == "b-model"


def test_build_judge_providers_falls_back_to_legacy_deepseek_gemini_settings():
    cfg = Settings(
        _env_file=None,
        deepseek_api_key="legacy-ds",
        deepseek_base_url="https://legacy-ds.example/v1",
        deepseek_model="legacy-ds-model",
        gemini_api_key="legacy-gm",
        gemini_base_url="https://legacy-gm.example/v1",
        gemini_model="legacy-gm-model",
    )

    provider_a, provider_b = build_judge_providers(cfg)

    assert provider_a.label == "DeepSeek"
    assert provider_a.api_key == "legacy-ds"
    assert provider_a.base_url == "https://legacy-ds.example/v1"
    assert provider_a.model == "legacy-ds-model"

    assert provider_b.label == "Gemini"
    assert provider_b.api_key == "legacy-gm"
    assert provider_b.base_url == "https://legacy-gm.example/v1"
    assert provider_b.model == "legacy-gm-model"


@respx.mock
@pytest.mark.asyncio
async def test_openai_compatible_provider_judge_parses_json_response():
    payload = {"sub_scores": {}, "confidence": "high", "dimension_notes": ""}
    respx.post("https://provider.example/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": f"```json\n{json.dumps(payload)}\n```"}}]},
        )
    )
    provider = OpenAICompatibleProvider(
        label="Provider A",
        api_key="key-a",
        base_url="https://provider.example/v1",
        model="model-a",
    )

    assert await provider.judge("prompt") == payload


@respx.mock
@pytest.mark.asyncio
async def test_openai_compatible_provider_generate_returns_text_response():
    respx.post("https://provider.example/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "draft text"}}]},
        )
    )
    provider = OpenAICompatibleProvider(
        label="Provider A",
        api_key="key-a",
        base_url="https://provider.example/v1",
        model="model-a",
    )

    assert await provider.generate("prompt") == "draft text"
