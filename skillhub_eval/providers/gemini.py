"""
Gemini LLM provider — Google Generative AI via OpenAI-compatible endpoint.

.. deprecated::
    Main judge path uses ``build_judge_providers`` + ``OpenAICompatibleProvider``.
    Retained for legacy unit tests and backward-compatible imports.

Google exposes an OpenAI-compatible API at:
  https://generativelanguage.googleapis.com/v1beta/openai/

Authentication: standard Bearer token with GEMINI_API_KEY.
Recommended model: gemini-2.0-flash (fast, cheap) or gemini-1.5-pro (higher quality).
"""

import json

from skillhub_eval.core.latency import PROVIDER_CALL_TIMEOUT_S, PROVIDER_RETRY_MAX

from .base import BaseLLMProvider
from .http_retry import post_with_retry

_OPENAI_COMPAT_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


class GeminiProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = _OPENAI_COMPAT_BASE,
        model: str = "gemini-2.0-flash",
        timeout: float = PROVIDER_CALL_TIMEOUT_S,
        max_retries: int = PROVIDER_RETRY_MAX,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.last_usage: dict | None = None

    async def judge(self, prompt: str) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }
        try:
            resp = await post_with_retry(
                url=f"{self.base_url}/chat/completions",
                headers=headers,
                json_payload=payload,
                timeout=self.timeout,
                max_retries=self.max_retries,
                provider_label="Gemini",
            )
            data = resp.json()
            usage = data.get("usage")
            self.last_usage = usage if isinstance(usage, dict) else None
            raw_content = data["choices"][0]["message"]["content"]
            content = raw_content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            return json.loads(content)
        except (json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(f"Gemini invalid response: {exc}") from exc
