"""T7 — workflow timeout mapping and provider budgets."""

from skillhub_eval.core.latency import (
    CASE_JUDGE_CONCURRENCY,
    PROVIDER_CALL_TIMEOUT_S,
    WORKFLOW_TIMEOUT_BY_RISK,
    workflow_timeout_seconds,
)
from skillhub_eval.core.schemas import RiskLevel
from skillhub_eval.providers.deepseek import DeepSeekProvider
from skillhub_eval.providers.gemini import GeminiProvider


def test_workflow_timeout_by_risk():
    assert workflow_timeout_seconds(RiskLevel.low) == 300
    assert workflow_timeout_seconds(RiskLevel.medium) == 300
    assert workflow_timeout_seconds(RiskLevel.high) == 600
    assert WORKFLOW_TIMEOUT_BY_RISK[RiskLevel.high] == 600


def test_case_concurrency_and_provider_timeout_constants():
    assert CASE_JUDGE_CONCURRENCY == 3
    assert PROVIDER_CALL_TIMEOUT_S == 45.0


def test_providers_default_call_timeout():
    ds = DeepSeekProvider(api_key="x")
    gm = GeminiProvider(api_key="x")
    assert ds.timeout == 45.0
    assert gm.timeout == 45.0
