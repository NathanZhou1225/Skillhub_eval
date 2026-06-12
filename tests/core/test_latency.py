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
from skillhub_eval.settings import Settings


def test_workflow_timeout_by_risk():
    assert workflow_timeout_seconds(RiskLevel.low) == 600
    assert workflow_timeout_seconds(RiskLevel.medium) == 600
    assert workflow_timeout_seconds(RiskLevel.high) == 900
    assert WORKFLOW_TIMEOUT_BY_RISK[RiskLevel.high] == 900


def test_case_concurrency_and_provider_timeout_constants():
    assert CASE_JUDGE_CONCURRENCY == 3
    assert Settings.model_fields["provider_call_timeout_s"].default == 90.0
    assert isinstance(PROVIDER_CALL_TIMEOUT_S, float)
    assert PROVIDER_CALL_TIMEOUT_S > 0


def test_providers_default_call_timeout():
    default_s = float(Settings.model_fields["provider_call_timeout_s"].default)
    ds = DeepSeekProvider(api_key="x", timeout=default_s)
    gm = GeminiProvider(api_key="x", timeout=default_s)
    assert ds.timeout == default_s
    assert gm.timeout == default_s
