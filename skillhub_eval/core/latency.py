"""T7 — workflow timeout, case concurrency, and provider call budgets."""

from __future__ import annotations

from .schemas.enums import RiskLevel

# grill-me Q2 (Phase 1 plan T7)
CASE_JUDGE_CONCURRENCY = 3
PROVIDER_CALL_TIMEOUT_S = 45.0
# high-risk bundles (e.g. stock-radar 9 cases + long SKILL excerpt) need longer judge calls
PROVIDER_CALL_TIMEOUT_HIGH_RISK_S = 90.0
PROVIDER_RETRY_MAX = 3
PROVIDER_RETRY_BASE_S = 1.0
RETRYABLE_HTTP_STATUS = frozenset({429, 503})

WORKFLOW_TIMEOUT_BY_RISK: dict[RiskLevel, int] = {
    RiskLevel.low: 300,
    RiskLevel.medium: 300,
    RiskLevel.high: 600,
}


def workflow_timeout_seconds(risk: RiskLevel) -> int:
    return WORKFLOW_TIMEOUT_BY_RISK.get(risk, 300)
