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
    """Judge-phase budget (model_judging → report); excludes local agent case_exec."""
    s = _settings()
    mapping = {
        RiskLevel.low: int(s.workflow_timeout_low_s),
        RiskLevel.medium: int(s.workflow_timeout_medium_s),
        RiskLevel.high: int(s.workflow_timeout_high_s),
    }
    return mapping.get(risk, int(s.workflow_timeout_low_s))


def local_agent_workflow_timeout_seconds(risk: RiskLevel) -> int:
    """Wall-clock budget for local CLI case_exec (+ code_assert); not counted toward judge budget."""
    s = _settings()
    mapping = {
        RiskLevel.low: int(s.local_agent_workflow_timeout_low_s),
        RiskLevel.medium: int(s.local_agent_workflow_timeout_medium_s),
        RiskLevel.high: int(s.local_agent_workflow_timeout_high_s),
    }
    return mapping.get(risk, int(s.local_agent_workflow_timeout_low_s))


def local_agent_case_timeout_seconds(risk: RiskLevel | str) -> int:
    """Per-case local CLI agent timeout budget."""
    level = RiskLevel(risk) if isinstance(risk, str) else risk
    s = _settings()
    mapping = {
        RiskLevel.low: int(s.local_agent_case_timeout_low_s),
        RiskLevel.medium: int(s.local_agent_case_timeout_medium_s),
        RiskLevel.high: int(s.local_agent_case_timeout_high_s),
    }
    return mapping.get(level, int(s.local_agent_case_timeout_low_s))


WORKFLOW_TIMEOUT_BY_RISK: dict[RiskLevel, int] = {
    RiskLevel.low: int(_settings().workflow_timeout_low_s),
    RiskLevel.medium: int(_settings().workflow_timeout_medium_s),
    RiskLevel.high: int(_settings().workflow_timeout_high_s),
}

# Grace beyond the longest configured workflow budget before treating a run as orphaned
# (e.g. browser crash / server restart mid-eval) for session/archive locks.
RUN_LOCK_GRACE_SECONDS = 900


def run_lock_timeout_seconds() -> int:
    """Upper bound for considering a RUNNING_STATUSES run still in-flight."""
    s = _settings()
    return (
        max(
            int(s.local_agent_workflow_timeout_high_s),
            int(s.workflow_timeout_high_s),
        )
        + RUN_LOCK_GRACE_SECONDS
    )


def is_run_actively_executing(run: dict | None, *, now=None) -> bool:
    """True when run status looks in-flight and not stale after an interrupt."""
    from datetime import datetime, timezone

    from skillhub_eval.core.schemas.enums import RUNNING_STATUSES

    if not run:
        return False
    status = run.get("status")
    if status not in RUNNING_STATUSES:
        return False

    started_raw = run.get("started_at")
    if not started_raw:
        return True

    try:
        started = datetime.fromisoformat(str(started_raw).replace("Z", "+00:00"))
    except ValueError:
        return True

    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)

    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)

    elapsed = (now_dt - started).total_seconds()
    return elapsed < float(run_lock_timeout_seconds())
