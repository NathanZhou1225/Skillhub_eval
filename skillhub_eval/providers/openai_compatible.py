"""Generic OpenAI-compatible chat completions provider."""

from __future__ import annotations

import json

from skillhub_eval.core.latency import PROVIDER_CALL_TIMEOUT_S, PROVIDER_RETRY_MAX

from .base import BaseLLMProvider
from .http_retry import post_with_retry


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(
        self,
        *,
        label: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = PROVIDER_CALL_TIMEOUT_S,
        max_retries: int = PROVIDER_RETRY_MAX,
    ) -> None:
        self.label = label
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    async def judge(self, prompt: str) -> dict:
        try:
            content = await self._chat(prompt, temperature=0.0)
            return json.loads(_strip_json_fence(content))
        except (json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(f"{self.label} invalid response: {exc}") from exc

    async def generate(self, prompt: str) -> str:
        try:
            return await self._chat(prompt, temperature=0.7)
        except KeyError as exc:
            raise RuntimeError(f"{self.label} generate invalid response: {exc}") from exc

    async def _chat(self, prompt: str, *, temperature: float) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        resp = await post_with_retry(
            url=f"{self.base_url}/chat/completions",
            headers=headers,
            json_payload=payload,
            timeout=self.timeout,
            max_retries=self.max_retries,
            provider_label=self.label,
        )
        return resp.json()["choices"][0]["message"]["content"]


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```")[1]
        if stripped.startswith("json"):
            stripped = stripped[4:]
    return stripped.strip()
