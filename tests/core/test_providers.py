"""
Tests for BaseLLMProvider + DeepSeekProvider + GeminiProvider.
Uses respx to mock HTTP — no real API calls are made.
"""

import json
import inspect
import pytest
import respx
import httpx

from skillhub_eval.providers.base import BaseLLMProvider
from skillhub_eval.providers.deepseek import DeepSeekProvider
from skillhub_eval.providers.gemini import GeminiProvider


FAKE_RESPONSE = {
    "sub_scores": {
        "step_completeness": {
            "score": 85,
            "pass": True,
            "reason": "steps complete",
            "evidence_refs": [],
        }
    },
    "confidence": "high",
    "dimension_notes": "",
}

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


def _mock_200(content: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps(content)}}]},
    )


# ─── BaseLLMProvider is abstract ──────────────────────────────────────────────

def test_base_provider_is_abstract():
    assert inspect.isabstract(BaseLLMProvider)


def test_base_provider_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseLLMProvider()  # type: ignore[abstract]


# ─── DeepSeekProvider ─────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_deepseek_judge_returns_dict():
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=_mock_200(FAKE_RESPONSE)
    )
    provider = DeepSeekProvider(
        api_key="test-key",
        base_url="https://api.deepseek.com/v1",
    )
    result = await provider.judge("test prompt")
    assert "sub_scores" in result
    assert result["confidence"] == "high"


@respx.mock
@pytest.mark.asyncio
async def test_deepseek_retries_on_503_then_succeeds():
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(503, json={"error": "unavailable"})
        return _mock_200(FAKE_RESPONSE)

    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        side_effect=side_effect
    )
    provider = DeepSeekProvider(
        api_key="test-key",
        base_url="https://api.deepseek.com/v1",
        max_retries=3,
    )
    result = await provider.judge("test prompt")
    assert call_count == 3
    assert "sub_scores" in result


@respx.mock
@pytest.mark.asyncio
async def test_deepseek_raises_after_max_retries():
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=httpx.Response(503, json={"error": "permanent failure"})
    )
    provider = DeepSeekProvider(
        api_key="test-key",
        base_url="https://api.deepseek.com/v1",
        max_retries=2,
    )
    with pytest.raises(RuntimeError, match="DeepSeek failed"):
        await provider.judge("test prompt")


@respx.mock
@pytest.mark.asyncio
async def test_deepseek_raises_on_invalid_json():
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not valid json {"}}]},
        )
    )
    provider = DeepSeekProvider(
        api_key="test-key",
        base_url="https://api.deepseek.com/v1",
        max_retries=1,
    )
    with pytest.raises(RuntimeError):
        await provider.judge("test prompt")


# ─── GeminiProvider ───────────────────────────────────────────────────────────

@respx.mock
@pytest.mark.asyncio
async def test_gemini_judge_returns_dict():
    respx.post(f"{_GEMINI_BASE}/chat/completions").mock(
        return_value=_mock_200(FAKE_RESPONSE)
    )
    provider = GeminiProvider(api_key="gemini-key", base_url=_GEMINI_BASE)
    result = await provider.judge("test prompt")
    assert "sub_scores" in result
    assert result["confidence"] == "high"


@respx.mock
@pytest.mark.asyncio
async def test_gemini_retries_on_503():
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            return httpx.Response(503, json={"error": "unavailable"})
        return _mock_200(FAKE_RESPONSE)

    respx.post(f"{_GEMINI_BASE}/chat/completions").mock(side_effect=side_effect)
    provider = GeminiProvider(api_key="gemini-key", base_url=_GEMINI_BASE, max_retries=3)
    result = await provider.judge("test prompt")
    assert call_count == 2
    assert "sub_scores" in result


@respx.mock
@pytest.mark.asyncio
async def test_gemini_strips_markdown_code_fence():
    """Gemini sometimes wraps JSON in ```json ... ``` — must be stripped."""
    wrapped = f"```json\n{json.dumps(FAKE_RESPONSE)}\n```"
    respx.post(f"{_GEMINI_BASE}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": wrapped}}]},
        )
    )
    provider = GeminiProvider(api_key="gemini-key", base_url=_GEMINI_BASE)
    result = await provider.judge("test prompt")
    assert "sub_scores" in result


# ─── Provider satisfies BaseLLMProvider interface ─────────────────────────────

def test_deepseek_is_instance_of_base():
    provider = DeepSeekProvider(api_key="x", base_url="https://api.deepseek.com/v1")
    assert isinstance(provider, BaseLLMProvider)


def test_gemini_is_instance_of_base():
    provider = GeminiProvider(api_key="x")
    assert isinstance(provider, BaseLLMProvider)
