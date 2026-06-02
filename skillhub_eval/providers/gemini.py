"""
Gemini LLM provider — Google Generative AI via OpenAI-compatible endpoint.

Google exposes an OpenAI-compatible API at:
  https://generativelanguage.googleapis.com/v1beta/openai/

Authentication: standard Bearer token with GEMINI_API_KEY.
Recommended model: gemini-2.0-flash (fast, cheap) or gemini-1.5-pro (higher quality).
"""

import asyncio
import json

import httpx

from .base import BaseLLMProvider

_OPENAI_COMPAT_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


class GeminiProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = _OPENAI_COMPAT_BASE,
        model: str = "gemini-2.0-flash",
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

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
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                if resp.status_code == 200:
                    raw_content = resp.json()["choices"][0]["message"]["content"]
                    # Gemini sometimes wraps JSON in markdown code fences
                    content = raw_content.strip()
                    if content.startswith("```"):
                        content = content.split("```")[1]
                        if content.startswith("json"):
                            content = content[4:]
                        content = content.strip()
                    return json.loads(content)
                last_error = RuntimeError(
                    f"Gemini HTTP {resp.status_code}: {resp.text[:200]}"
                )
            except (httpx.RequestError, json.JSONDecodeError, KeyError) as exc:
                last_error = exc

            if attempt < self.max_retries - 1:
                await asyncio.sleep(2**attempt)

        raise RuntimeError(
            f"Gemini failed after {self.max_retries} retries: {last_error}"
        )
