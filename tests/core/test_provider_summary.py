"""T5 — provider_summary builder tests."""

from skillhub_eval.core.provider_summary import build_provider_summary, per_case_row_highlight
from skillhub_eval.core.schemas.report import ExecResult


def _votes_r5():
    return [
        {"model": "deepseek", "case_id": "c01", "score_total": 88.0, "suggested_review_status": "pass"},
        {"model": "gemini", "case_id": "c01", "score_total": 60.0, "suggested_review_status": "fail"},
        {"model": "deepseek", "case_id": "c02", "score_total": 85.0, "suggested_review_status": "pass"},
        {"model": "gemini", "case_id": "c02", "score_total": 82.0, "suggested_review_status": "pass"},
    ]


def test_build_provider_summary_r5():
    agg = {
        "ds_score": 86.5,
        "wb_score": 71.0,
        "r5_triggered": True,
    }
    summary = build_provider_summary(_votes_r5(), agg)
    assert summary.r5_triggered is True
    assert summary.deepseek_score == 86.5
    assert summary.gemini_score == 71.0
    assert summary.score_gap == 15.5
    assert len(summary.per_case) == 2
    c01 = next(r for r in summary.per_case if r.case_id == "c01")
    assert c01.gap == 28.0
    assert per_case_row_highlight(c01) is True


def test_build_provider_summary_no_disagreement():
    votes = [
        {"model": "deepseek", "case_id": "c01", "score_total": 80.0, "suggested_review_status": "pass"},
        {"model": "gemini", "case_id": "c01", "score_total": 78.0, "suggested_review_status": "pass"},
    ]
    agg = {"ds_score": 80.0, "wb_score": 78.0, "r5_triggered": False}
    summary = build_provider_summary(votes, agg)
    assert summary.r5_triggered is False
    assert summary.score_gap == 2.0


def test_build_provider_summary_carries_env_labels():
    summary = build_provider_summary(
        [],
        {},
        provider_a_label="Provider A",
        provider_b_label="Provider B",
    )

    assert summary.provider_a_label == "Provider A"
    assert summary.provider_b_label == "Provider B"


def test_build_provider_summary_surfaces_exec_degrade_reason():
    """Q-27 hardening: per-case local-agent failure reason should reach the report, not dead-end on ExecResult."""
    votes = [
        {"model": "deepseek", "case_id": "c01", "score_total": 80.0, "suggested_review_status": "pass"},
        {"model": "deepseek", "case_id": "c02", "score_total": 75.0, "suggested_review_status": "pass"},
    ]
    exec_results = {
        "c01": ExecResult(status="incomplete", degrade_reason="run_incomplete"),
        "c02": ExecResult(status="ok"),
    }
    summary = build_provider_summary(votes, {}, exec_results=exec_results)

    c01 = next(r for r in summary.per_case if r.case_id == "c01")
    c02 = next(r for r in summary.per_case if r.case_id == "c02")
    assert c01.exec_status == "incomplete"
    assert c01.exec_degrade_reason == "run_incomplete"
    assert c02.exec_status == "ok"
    assert c02.exec_degrade_reason is None


def test_build_provider_summary_without_exec_results_leaves_fields_none():
    """Backward compat: sample_io-only runs (no exec_results) must not set exec fields."""
    summary = build_provider_summary(_votes_r5(), {"ds_score": 86.5, "wb_score": 71.0})
    assert all(row.exec_status is None and row.exec_degrade_reason is None for row in summary.per_case)
