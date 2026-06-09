"""
Risk level locking — Step ①+② (C-6).

Step ①: read declared risk_level from SKILL.md frontmatter.
Step ②: pure-regex rules scan of SKILL.md text → elevate if needed (就高不就低).
Step ③: LLM risk-review via `risk_review.review_risk_level` (DeepSeek).
"""

import re

from .schemas.enums import RiskLevel

# Patterns that immediately lock risk to HIGH (finance/ops keywords)
_HIGH_RISK_PATTERNS: list[str] = [
    r"交易",
    r"下单",
    r"转账",
    r"扣款",
    r"delete\b",
    r"DROP\s+TABLE",
    r"wire\s+transfer",
    r"payment",
]

# Patterns that lock risk to at least MEDIUM (PII / HR data)
_MEDIUM_RISK_PATTERNS: list[str] = [
    r"员工",
    r"salary",
    r"工资",
    r"身份证",
    r"客户",
    r"个人信息",
    r"personnel",
]

_RISK_ORDER = [RiskLevel.low, RiskLevel.medium, RiskLevel.high]


def _higher(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    """Return the higher of two risk levels (就高不就低)."""
    return a if _RISK_ORDER.index(a) >= _RISK_ORDER.index(b) else b


def scan_risk_rule_only(skill_md_text: str) -> RiskLevel:
    """Step ②: regex rules only (no declared merge)."""
    flags = re.IGNORECASE
    if any(re.search(p, skill_md_text, flags) for p in _HIGH_RISK_PATTERNS):
        return RiskLevel.high
    if any(re.search(p, skill_md_text, flags) for p in _MEDIUM_RISK_PATTERNS):
        return RiskLevel.medium
    return RiskLevel.low


def scan_risk(skill_md_text: str, declared: RiskLevel) -> RiskLevel:
    """Step ①+②: max(declared, rule_scan)."""
    return _higher(scan_risk_rule_only(skill_md_text), declared)
