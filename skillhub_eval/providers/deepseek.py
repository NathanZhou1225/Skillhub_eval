"""
DeepSeek LLM provider — live API implementation.

Default mode: EVAL_LLM_MODE=live (no mock/replay in MVP).
Retry with exponential back-off on 5xx or network errors.
"""

import asyncio
import json

import httpx

from .base import BaseLLMProvider


class DeepSeekProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
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
                    return json.loads(raw_content)
                last_error = RuntimeError(
                    f"DeepSeek HTTP {resp.status_code}: {resp.text[:200]}"
                )
            except (httpx.RequestError, json.JSONDecodeError, KeyError) as exc:
                last_error = exc

            if attempt < self.max_retries - 1:
                await asyncio.sleep(2**attempt)

        raise RuntimeError(
            f"DeepSeek failed after {self.max_retries} retries: {last_error}"
        )
