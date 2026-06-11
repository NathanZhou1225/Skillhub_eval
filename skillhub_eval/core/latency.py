"""T7 — workflow timeout, case concurrency, and provider call budgets."""

from __future__ import annotations

from .schemas.enums import RiskLevel


def _settings():
    from skillhub_eval.settings import settings

    return settings


# grill-me Q2 (Phase 1 plan T7) — defaults raised; override in .env via Settings
CASE_JUDGE_CONCURRENCY = 3
PROVIDER_RETRY_MAX = 3
PROVIDER_RETRY_BASE_S = 1.0
RETRYABLE_HTTP_STATUS = frozenset({429, 503})


def provider_call_timeout_s() -> float:
    return float(_settings().provider_call_timeout_s)


def provider_call_timeout_high_risk_s() -> float:
    return float(_settings().provider_call_timeout_high_risk_s)


# Back-compat module constants (tests / imports)
PROVIDER_CALL_TIMEOUT_S = provider_call_timeout_s()
PROVIDER_CALL_TIMEOUT_HIGH_RISK_S = provider_call_timeout_high_risk_s()


def workflow_timeout_seconds(risk: RiskLevel) -> int:
    s = _settings()
    mapping = {
        RiskLevel.low: int(s.workflow_timeout_low_s),
        RiskLevel.medium: int(s.workflow_timeout_medium_s),
        RiskLevel.high: int(s.workflow_timeout_high_s),
    }
    return mapping.get(risk, int(s.workflow_timeout_low_s))


WORKFLOW_TIMEOUT_BY_RISK: dict[RiskLevel, int] = {
    RiskLevel.low: int(_settings().workflow_timeout_low_s),
    RiskLevel.medium: int(_settings().workflow_timeout_medium_s),
    RiskLevel.high: int(_settings().workflow_timeout_high_s),
}
