"""Wave 5.3 Task 3 — propagation plan LLM enricher."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from skillhub_eval.core.propagation_plan_enricher import enrich_propagation_plan


def _sample_plan() -> dict:
    return {
        "rows": [
            {"type": "happy_path", "type_zh": "主流程", "gap_count": 2},
            {"type": "edge", "type_zh": "边界", "gap_count": 1},
        ],
        "plan_version": 1,
    }


@pytest.mark.asyncio
async def test_enrich_propagation_plan_fills_distinct_business_expectations():
    ds = AsyncMock()
    ds.generate = AsyncMock(
        return_value=json.dumps(
            {
                "rows": [
                    {
                        "type": "happy_path",
                        "tests_what": "验证量化信号主流程",
                        "business_expectation": "输出含 direction 字段",
                        "redline_note": "",
                    },
                    {
                        "type": "edge",
                        "tests_what": "验证空输入边界",
                        "business_expectation": "应返回明确错误而非崩溃",
                        "redline_note": "",
                    },
                ]
            },
            ensure_ascii=False,
        )
    )
    plan = _sample_plan()
    result = await enrich_propagation_plan(
        plan,
        skill_md_text="# Demo Skill\n用于测试 enrich。",
        skill_id="demo-skill",
        category_slug="fin-research/quant-signal",
        clarifications={"purpose": "量化信号"},
        ds_provider=ds,
    )
    assert result["enrichment_status"] == "ok"
    rows = result["rows"]
    expectations = [r["business_expectation"] for r in rows]
    assert len(set(expectations)) == 2
    assert rows[0]["enrichment_source"] == "llm"
    ds.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_enrich_uses_generate_with_markdown_fence():
    ds = AsyncMock()
    ds.generate = AsyncMock(
        return_value=(
            '```json\n{"rows":[{"type":"happy_path","tests_what":"主流程",'
            '"business_expectation":"专属A","redline_note":""}]}\n```'
        )
    )
    plan = {"rows": [_sample_plan()["rows"][0]]}
    result = await enrich_propagation_plan(
        plan,
        skill_md_text="# Demo",
        skill_id="demo",
        category_slug="fin-research/quant-signal",
        clarifications=None,
        ds_provider=ds,
    )
    assert result["enrichment_status"] == "ok"
    assert result["rows"][0]["business_expectation"] == "专属A"


@pytest.mark.asyncio
async def test_enrich_propagation_plan_degrades_on_llm_failure():
    ds = AsyncMock()
    ds.generate = AsyncMock(side_effect=RuntimeError("llm down"))
    plan = _sample_plan()
    result = await enrich_propagation_plan(
        plan,
        skill_md_text="# Demo",
        skill_id="demo-skill",
        category_slug="unknown",
        clarifications=None,
        ds_provider=ds,
    )
    assert result["enrichment_status"] == "degraded"
    assert "enrichment_degraded_hint" in result
    for row in result["rows"]:
        assert row.get("enrichment_source") == "deterministic"
    expectations = [r["business_expectation"] for r in result["rows"]]
    assert len(set(expectations)) == len(expectations)


@pytest.mark.asyncio
async def test_enrich_skips_when_no_rows():
    ds = AsyncMock()
    plan: dict = {"rows": []}
    result = await enrich_propagation_plan(
        plan,
        skill_md_text="",
        skill_id="x",
        category_slug="",
        clarifications=None,
        ds_provider=ds,
    )
    assert result["enrichment_status"] == "skipped"
    ds.generate.assert_not_called()
