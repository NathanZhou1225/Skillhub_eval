"""Tests for report_narrative (2.3b/c)."""

from skillhub_eval.core.provider_summary import build_provider_summary
from skillhub_eval.core.report_narrative import (
    build_disagreement_brief,
    build_report_narrative,
)


def test_r5_headline_and_reasons():
    nar = build_report_narrative({
        "review_status": "warn",
        "reason_codes": ["MODEL_DISAGREEMENT_R5"],
        "required_actions": [],
        "score_total": None,
    })
    assert "人工复核" in nar.headline_zh
    assert any("不一致" in r for r in nar.reasons_zh)


def test_redline_disagreement_brief():
    votes = [
        {"model": "deepseek", "case_id": "r01", "case_type": "refusal_case",
         "score_total": 0, "suggested_review_status": "fail"},
        {"model": "gemini", "case_id": "r01", "case_type": "refusal_case",
         "score_total": 95, "suggested_review_status": "pass"},
        {"model": "deepseek", "case_id": "h01", "case_type": "happy_path",
         "score_total": 85, "suggested_review_status": "pass"},
        {"model": "gemini", "case_id": "h01", "case_type": "happy_path",
         "score_total": 86, "suggested_review_status": "pass"},
    ]
    agg = {
        "r5_triggered": False,
        "reason_codes": ["REDLINE_MODEL_DISAGREEMENT"],
        "ds_score": 85.5,
        "wb_score": 86.0,
    }
    ps = build_provider_summary(votes, agg)
    brief = build_disagreement_brief(ps, agg, votes)
    assert brief is not None
    assert brief.triggered is True
    assert "红线" in brief.summary_zh or any("红线" in h for h in brief.stage_hints_zh)
