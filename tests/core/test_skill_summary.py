"""Tests for skill_summary parsing and fallback."""

from skillhub_eval.core.skill_summary import (
    build_fallback_skill_summary,
    parse_skill_summary_response,
)


def test_parse_accepts_standard_shape():
    raw = {
        "overall_verdict": "质量良好",
        "strengths": ["合规完整"],
        "weaknesses": ["样例偏少"],
        "dimension_notes": {"instruction_following": "优秀"},
        "recommendation": "可上架",
    }
    out = parse_skill_summary_response(raw)
    assert out is not None
    assert out["overall_verdict"] == "质量良好"
    assert out["source"] == "llm"


def test_parse_rejects_judge_sub_scores_payload():
    raw = {
        "sub_scores": {
            "instruction_following": {"score": 90, "pass": True},
        },
        "confidence": "high",
    }
    assert parse_skill_summary_response(raw) is None


def test_fallback_pass_includes_strengths():
    agg = {"score_total": 97.2, "ds_score": 97.5, "wb_score": 97.0}
    votes = [
        {
            "model": "deepseek",
            "case_id": "h01",
            "score_total": 100,
            "feedback": "合规",
            "dimension_scores": {
                "instruction_following": 98,
                "output_compliance": 97,
                "business_resolution": 96,
            },
        },
    ]
    out = build_fallback_skill_summary(
        review_status="pass",
        completeness_score=100,
        agg=agg,
        all_votes=votes,
    )
    assert out["overall_verdict"]
    assert len(out["strengths"]) >= 2
    assert out["source"] == "fallback"
