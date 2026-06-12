"""Wave 5.4 — divergence synthesis."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from skillhub_eval.core.divergence import (
    build_single_sided_divergence,
    compute_max_gap_dimension,
    synthesize_divergences_for_run,
)


def test_compute_max_gap_dimension():
    ds = {
        "instruction_following": {"score": 80},
        "output_compliance": {"score": 10},
        "business_resolution": {"score": 75},
    }
    gm = {
        "instruction_following": {"score": 82},
        "output_compliance": {"score": 90},
        "business_resolution": {"score": 70},
    }
    dim, gap = compute_max_gap_dimension(ds, gm)
    assert dim == "output_compliance"
    assert gap == 80.0


@pytest.mark.asyncio
async def test_synthesize_skips_gap_below_15():
    repo = MagicMock()
    repo.get_provider_errors.return_value = []
    provider = MagicMock()
    votes = [
        {
            "model": "deepseek",
            "case_id": "c1",
            "score_total": 80,
            "dimension_scores": {},
        },
        {
            "model": "gemini",
            "case_id": "c1",
            "score_total": 85,
            "dimension_scores": {},
        },
    ]
    await synthesize_divergences_for_run("run-1", votes, repo, provider)
    repo.update_judge_trace_divergence.assert_not_called()


@pytest.mark.asyncio
async def test_synthesize_parallel_on_gap_ge_15():
    repo = MagicMock()
    repo.get_provider_errors.return_value = []
    provider = MagicMock()
    provider.generate = AsyncMock(return_value="两模型在输出合规维度分歧最大。")

    votes = [
        {
            "model": "deepseek",
            "case_id": "c1",
            "case_type": "adversarial_case",
            "score_total": 0,
            "dimension_scores": {
                "output_compliance": {"score": 0},
                "instruction_following": {"score": 50},
                "business_resolution": {"score": 50},
            },
        },
        {
            "model": "gemini",
            "case_id": "c1",
            "case_type": "adversarial_case",
            "score_total": 75,
            "dimension_scores": {
                "output_compliance": {"score": 90},
                "instruction_following": {"score": 70},
                "business_resolution": {"score": 72},
            },
        },
    ]
    await synthesize_divergences_for_run("run-1", votes, repo, provider, timeout_s=5.0)
    repo.update_judge_trace_divergence.assert_called_once()
    payload = repo.update_judge_trace_divergence.call_args[0][2]
    assert payload["max_gap_dimension"] == "output_compliance"
    assert payload["single_sided"] is False
    assert "分歧" in payload["synthesis_zh"] or len(payload["synthesis_zh"]) > 0


@pytest.mark.asyncio
async def test_single_sided_no_llm():
    repo = MagicMock()
    repo.get_provider_errors.return_value = [
        {"case_id": "c2", "provider": "gemini", "error": "timeout"},
    ]
    provider = MagicMock()
    votes = [
        {"model": "deepseek", "case_id": "c2", "score_total": 70, "dimension_scores": {}},
    ]
    await synthesize_divergences_for_run("run-1", votes, repo, provider)
    repo.update_judge_trace_divergence.assert_called_once()
    payload = repo.update_judge_trace_divergence.call_args[0][2]
    assert payload["single_sided"] is True
    provider.generate.assert_not_called()


def test_build_single_sided_divergence_filters_case():
    div = build_single_sided_divergence(
        "c1",
        [
            {"case_id": "c1", "error": "a"},
            {"case_id": "c2", "error": "b"},
        ],
    )
    assert div["single_sided"] is True
    assert len(div["provider_errors"]) == 1
