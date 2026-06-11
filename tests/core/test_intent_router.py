"""Wave 5.3 Task 5 — IntentRouter."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from skillhub_eval.core.intent_router import (
    CONFIDENCE_THRESHOLD,
    ACTION_PROPAGATE,
    IntentRouter,
)


@pytest.mark.asyncio
async def test_classify_returns_whitelisted_action():
    ds = AsyncMock()
    ds.judge = AsyncMock(
        return_value=json.dumps(
            {
                "action": "propagate",
                "confidence": 0.92,
                "reply": "好的，开始自动出题。",
            }
        )
    )
    router = IntentRouter(ds)
    result = await router.classify(
        "帮我自动出题",
        conversation_status="awaiting_propagation_confirm",
    )
    assert result.action == ACTION_PROPAGATE
    assert result.confidence >= CONFIDENCE_THRESHOLD
    assert result.reply


@pytest.mark.asyncio
async def test_classify_rejects_unknown_action():
    ds = AsyncMock()
    ds.judge = AsyncMock(
        return_value=json.dumps(
            {"action": "delete_everything", "confidence": 0.99, "reply": "x"}
        )
    )
    router = IntentRouter(ds)
    result = await router.classify("随便说", conversation_status="active")
    assert result.action is None


@pytest.mark.asyncio
async def test_classify_degrades_on_parse_error():
    ds = AsyncMock()
    ds.judge = AsyncMock(return_value="not json")
    router = IntentRouter(ds)
    result = await router.classify("嗯", conversation_status="awaiting_propagation_confirm")
    assert result.action is None
    assert result.confidence == 0.0
    assert "理解" in result.reply or "按钮" in result.reply
