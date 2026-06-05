"""Shared HTTP retry for LLM providers (T7: 429/503, exponential back-off)."""

from __future__ import annotations

import asyncio

import httpx

from skillhub_eval.core.latency import (
    PROVIDER_RETRY_BASE_S,
    PROVIDER_RETRY_MAX,
    RETRYABLE_HTTP_STATUS,
)


async def post_with_retry(
    *,
    url: str,
    headers: dict,
    json_payload: dict,
    timeout: float,
    max_retries: int = PROVIDER_RETRY_MAX,
    retry_base_s: float = PROVIDER_RETRY_BASE_S,
    provider_label: str,
) -> httpx.Response:
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=json_payload)
            if resp.status_code == 200:
                return resp
            if (
                resp.status_code in RETRYABLE_HTTP_STATUS
                and attempt < max_retries - 1
            ):
                await asyncio.sleep(retry_base_s * (2**attempt))
                continue
            last_error = RuntimeError(
                f"{provider_label} HTTP {resp.status_code}: {resp.text[:200]}"
            )
        except httpx.RequestError as exc:
            last_error = exc
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_base_s * (2**attempt))
                continue

    raise RuntimeError(
        f"{provider_label} failed after {max_retries} retries: {last_error}"
    )
