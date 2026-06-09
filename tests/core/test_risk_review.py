"""Tests for AI risk review (2.5)."""

import pytest

from skillhub_eval.core.risk_review import merge_risk_levels, parse_risk_review_response
from skillhub_eval.core.schemas.enums import RiskLevel


def test_merge_risk_never_lowers():
    locked = merge_risk_levels(
        RiskLevel.high, RiskLevel.low, RiskLevel.medium,
    )
    assert locked == RiskLevel.high


def test_merge_risk_ai_raises():
    locked = merge_risk_levels(
        RiskLevel.low, RiskLevel.low, RiskLevel.medium,
    )
    assert locked == RiskLevel.medium


def test_parse_risk_review_response():
    level, ev = parse_risk_review_response({
        "suggested_risk": "medium",
        "evidence_zh": "涉及员工数据",
    })
    assert level == RiskLevel.medium
    assert "员工" in ev
