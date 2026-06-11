"""Wave 5.3 Task 9 — clarification parser."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from skillhub_eval.core.clarification_parser import (
    parse_clarification_heuristic,
    parse_clarification_message,
)


def test_heuristic_single_key():
    assert parse_clarification_heuristic("用于量化选股", ["purpose"]) == {
        "purpose": "用于量化选股"
    }


def test_heuristic_key_value_separator():
    assert parse_clarification_heuristic("purpose：量化信号", ["purpose", "category"]) == {
        "purpose": "量化信号"
    }


@pytest.mark.asyncio
async def test_llm_parser_multi_key():
    ds = AsyncMock()
    ds.judge = AsyncMock(
        return_value=json.dumps(
            {"answers": {"purpose": "选股", "category": "fin-research/quant-signal"}}
        )
    )
    result = await parse_clarification_message(
        "选股场景，类别是量化信号",
        ["purpose", "category"],
        ds,
    )
    assert result.get("purpose") == "选股"
    assert result.get("category") == "fin-research/quant-signal"


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_heuristic():
    ds = AsyncMock()
    ds.judge = AsyncMock(side_effect=RuntimeError("down"))
    result = await parse_clarification_message(
        "purpose：仅测试",
        ["purpose", "category"],
        ds,
    )
    assert result == {"purpose": "仅测试"}
