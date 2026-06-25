"""T7 — workflow timeout mapping and provider budgets."""

from skillhub_eval.core.latency import (
    CASE_JUDGE_CONCURRENCY,
    PROVIDER_CALL_TIMEOUT_S,
    workflow_timeout_seconds,
)
from skillhub_eval.core.schemas import RiskLevel
from skillhub_eval.providers.deepseek import DeepSeekProvider
from skillhub_eval.providers.gemini import GeminiProvider
from skillhub_eval.settings import Settings


def _default_settings():
    return Settings(_env_file=None)


def test_workflow_timeout_by_risk(monkeypatch):
    monkeypatch.setattr("skillhub_eval.core.latency._settings", _default_settings)

    assert workflow_timeout_seconds(RiskLevel.low) == 600
    assert workflow_timeout_seconds(RiskLevel.medium) == 600
    assert workflow_timeout_seconds(RiskLevel.high) == 900


def test_local_agent_workflow_timeout_by_risk(monkeypatch):
    from skillhub_eval.core.latency import local_agent_workflow_timeout_seconds

    monkeypatch.setattr("skillhub_eval.core.latency._settings", _default_settings)

    assert local_agent_workflow_timeout_seconds(RiskLevel.low) == 1800
    assert local_agent_workflow_timeout_seconds(RiskLevel.high) == 5400


def test_local_agent_case_timeout_by_risk(monkeypatch):
    from skillhub_eval.core.latency import local_agent_case_timeout_seconds

    monkeypatch.setattr("skillhub_eval.core.latency._settings", _default_settings)

    assert local_agent_case_timeout_seconds(RiskLevel.low) == 600
    assert local_agent_case_timeout_seconds(RiskLevel.medium) == 900
    assert local_agent_case_timeout_seconds(RiskLevel.high) == 1800


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
