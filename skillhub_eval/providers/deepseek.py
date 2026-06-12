"""
DeepSeek LLM provider — live API implementation.

T7: 45s per-call timeout; retry 429/503 with exponential back-off (base 1s, max 3).
"""

import json

from skillhub_eval.core.latency import PROVIDER_CALL_TIMEOUT_S, PROVIDER_RETRY_MAX

from .base import BaseLLMProvider
from .http_retry import post_with_retry


class DeepSeekProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        timeout: float = PROVIDER_CALL_TIMEOUT_S,
        max_retries: int = PROVIDER_RETRY_MAX,
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
        try:
            resp = await post_with_retry(
                url=f"{self.base_url}/chat/completions",
                headers=headers,
                json_payload=payload,
                timeout=self.timeout,
                max_retries=self.max_retries,
                provider_label="DeepSeek",
            )
            raw_content = resp.json()["choices"][0]["message"]["content"]
            content = raw_content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            return json.loads(content)
        except (json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(f"DeepSeek invalid response: {exc}") from exc

    async def generate(self, prompt: str) -> str:
        """Send a single user message and return raw text content (not parsed)."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        }
        try:
            resp = await post_with_retry(
                url=f"{self.base_url}/chat/completions",
                headers=headers,
                json_payload=payload,
                timeout=self.timeout,
                max_retries=self.max_retries,
                provider_label="DeepSeek",
            )
            return resp.json()["choices"][0]["message"]["content"]
        except KeyError as exc:
            raise RuntimeError(f"DeepSeek generate invalid response: {exc}") from exc
