import pytest

from skillhub_eval.core.schemas import (
    BundleState,
    EvaluationMode,
    EvalRunRequest,
    EvaluationReport,
)


def test_bundle_state_enum():
    assert BundleState.confirmed == "confirmed"


def test_eval_request_rejects_unknown_bundle_state():
    with pytest.raises(Exception):
        EvalRunRequest(
            skill_id="s1",
            skill_bundle_path="/tmp/skill",
            bundle_state="invalid",
            evaluation_mode="capability_full",
        )


def test_pass_allowed_fields_present():
    r = EvaluationReport(
        run_id="r1",
        skill_id="s1",
        skill_bundle_path="/tmp",
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
        status="completed",
        review_status="pass",
        rubric_version="v1.2",
        prompt_version="review-agent-v0.2",
    )
    assert r.bundle_state == BundleState.confirmed


def test_case_count_gates_x1():
    from skillhub_eval.core.schemas import CASE_COUNT_GATES, RiskLevel

    assert CASE_COUNT_GATES[RiskLevel.low] == (3, 6)
    assert CASE_COUNT_GATES[RiskLevel.medium] == (5, 8)
    assert CASE_COUNT_GATES[RiskLevel.high] == (9, 12)
