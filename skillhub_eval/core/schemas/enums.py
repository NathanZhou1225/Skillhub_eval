from enum import Enum


class BundleState(str, Enum):
    minimal = "minimal"
    draft_enriched = "draft_enriched"
    eval_ready = "eval_ready"
    confirmed = "confirmed"


class EvaluationMode(str, Enum):
    degraded = "degraded"
    capability_full = "capability_full"
    post_listing_health_check = "post_listing_health_check"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class OrchestrationMode(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class ReviewStatus(str, Enum):
    passed = "pass"
    warned = "warn"
    failed = "fail"


class RunStatus(str, Enum):
    pending = "pending"
    level0_checking = "level0_checking"
    risk_locking = "risk_locking"
    normalizing = "normalizing"
    awaiting_confirm = "awaiting_confirm"
    case_executing = "case_executing"
    code_asserting = "code_asserting"
    model_judging = "model_judging"
    aggregating = "aggregating"
    awaiting_human_review = "awaiting_human_review"
    completed = "completed"
    failed = "failed"
    superseded = "superseded"


# Case count gate (X1): low/medium/high → (min_cases, mvp_ceiling)
CASE_COUNT_GATES: dict[RiskLevel, tuple[int, int]] = {
    RiskLevel.low: (3, 6),
    RiskLevel.medium: (5, 8),
    RiskLevel.high: (9, 12),
}

# Valid case types recognized by the evaluation engine
VALID_CASE_TYPES: frozenset[str] = frozenset({"happy_path", "edge", "refusal", "adversarial"})

# Case type requirements per risk level (W3 题型完整性门槛)
# Keys are case type strings; values are minimum required counts
CASE_TYPE_REQUIREMENTS: dict[str, dict[str, int]] = {
    "low":    {"happy_path": 3},
    "medium": {"happy_path": 3, "edge": 2},
    "high":   {"happy_path": 3, "edge": 2, "refusal": 2, "adversarial": 2},
}
