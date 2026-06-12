"""Wave 5.4 — parse_judge_response (GQ6)."""

import json
import pytest

from skillhub_eval.core.judge_parse import parse_judge_response


def _minimal_sub_scores(ds: int = 80, oc: int = 70, br: int = 75) -> dict:
    def dim(score: int) -> dict:
        return {"score": score, "pass": score >= 70, "reason": "ok"}

    return {
        "instruction_following": dim(ds),
        "output_compliance": dim(oc),
        "business_resolution": dim(br),
    }


def test_parse_strips_markdown_fence():
    raw = {
        "sub_scores": _minimal_sub_scores(),
        "confidence": "high",
        "dimension_notes": "summary",
    }
    fenced = "```json\n" + json.dumps(raw, ensure_ascii=False) + "\n```"
    parsed = parse_judge_response(fenced)
    assert parsed["sub_scores"]["instruction_following"]["score"] == 80


def test_parse_dict_requires_scores():
    parsed = parse_judge_response(
        {
            "sub_scores": _minimal_sub_scores(),
            "confidence": "medium",
            "dimension_notes": "x",
        }
    )
    assert parsed["sub_scores"]["business_resolution"]["score"] == 75


def test_parse_optional_analysis_fields_preserved():
    sub = _minimal_sub_scores()
    sub["instruction_following"]["analysis"] = "专业分析" * 5
    sub["instruction_following"]["evidence_quotes"] = ["引用一句"]
    sub["instruction_following"]["deductions"] = ["扣分点"]
    parsed = parse_judge_response({"sub_scores": sub, "confidence": "high"})
    entry = parsed["sub_scores"]["instruction_following"]
    assert entry["analysis"].startswith("专业分析")
    assert entry["evidence_quotes"] == ["引用一句"]


def test_parse_missing_score_raises():
    sub = {"output_compliance": {"pass": False, "reason": "no score"}}
    with pytest.raises(ValueError, match="missing score"):
        parse_judge_response({"sub_scores": sub})


def test_parse_backfills_dimension_without_score_from_siblings():
    sub = _minimal_sub_scores()
    sub["output_compliance"] = {"pass": False, "reason": "no score"}
    parsed = parse_judge_response({"sub_scores": sub})
    assert parsed["sub_scores"]["output_compliance"]["score"] == 80
