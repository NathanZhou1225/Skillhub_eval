import pytest

from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.core.level0 import Level0Checker
from skillhub_eval.core.risk_lock import scan_risk
from skillhub_eval.core.schemas import RiskLevel


# ─── fixtures ────────────────────────────────────────────────────────────────

def make_bundle(tmp_path, n_cases: int = 3, risk: str = "low", has_skill_md: bool = True):
    if has_skill_md:
        (tmp_path / "SKILL.md").write_text(
            f"---\nname: test\nrisk_level: {risk}\n---\n# Test Skill\n",
            encoding="utf-8",
        )
    ec = tmp_path / "eval_cases"
    ec.mkdir(exist_ok=True)
    for i in range(n_cases):
        (ec / f"case_{i:02d}.yaml").write_text(
            f"id: case_{i:02d}\ntype: happy_path\nuser_intent: test intent\n",
            encoding="utf-8",
        )
    return tmp_path


# ─── ingest ──────────────────────────────────────────────────────────────────

def test_ingest_ok(tmp_path):
    make_bundle(tmp_path, n_cases=3, risk="low")
    bundle = ingest_bundle(str(tmp_path))
    assert bundle["skill_id"] is not None
    assert bundle["risk_level_declared"] == "low"
    assert len(bundle["eval_cases"]) == 3


def test_ingest_no_skill_md(tmp_path):
    make_bundle(tmp_path, n_cases=3, has_skill_md=False)
    bundle = ingest_bundle(str(tmp_path))
    assert bundle["has_skill_md"] is False


# ─── Level 0 ─────────────────────────────────────────────────────────────────

def test_level0_pass_low(tmp_path):
    make_bundle(tmp_path, n_cases=3, risk="low")
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check(bundle)
    assert result["passed"] is True


def test_level0_fail_no_skill_md(tmp_path):
    make_bundle(tmp_path, n_cases=3, has_skill_md=False)
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check(bundle)
    assert result["passed"] is False
    assert "LEVEL0_SCHEMA_FAIL" in result["reason_codes"]


def test_level0_fail_too_few_cases(tmp_path):
    # low risk min = 3, submit 1
    make_bundle(tmp_path, n_cases=1, risk="low")
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check(bundle)
    assert result["passed"] is False
    assert "RISK_CASE_COUNT_INSUFFICIENT" in result["reason_codes"]


def test_level0_fail_too_many_cases(tmp_path):
    # low risk ceiling = 6, submit 7
    make_bundle(tmp_path, n_cases=7, risk="low")
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check(bundle)
    assert result["passed"] is False
    assert "CASE_COUNT_EXCEEDS_LIMIT" in result["reason_codes"]


def test_level0_pass_medium(tmp_path):
    # medium: min=5, ceiling=8 → 5 cases OK
    make_bundle(tmp_path, n_cases=5, risk="medium")
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check(bundle)
    assert result["passed"] is True


def test_level0_pass_high(tmp_path):
    # high: min=9, ceiling=12 → 9 cases OK
    make_bundle(tmp_path, n_cases=9, risk="high")
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check(bundle)
    assert result["passed"] is True


def test_level0_fail_high_too_many(tmp_path):
    # high ceiling = 12
    make_bundle(tmp_path, n_cases=13, risk="high")
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check(bundle)
    assert result["passed"] is False
    assert "CASE_COUNT_EXCEEDS_LIMIT" in result["reason_codes"]


# ─── risk_lock scan (C-6) ────────────────────────────────────────────────────

def test_risk_scan_stays_low():
    text = "This skill answers general questions about policy documents."
    result = scan_risk(text, RiskLevel.low)
    assert result == RiskLevel.low


def test_risk_scan_elevates_to_medium():
    text = "此技能查询员工工资及薪酬记录。"
    result = scan_risk(text, RiskLevel.low)
    assert result == RiskLevel.medium


def test_risk_scan_elevates_to_high():
    text = "此技能执行转账操作，涉及资金划拨。"
    result = scan_risk(text, RiskLevel.low)
    assert result == RiskLevel.high


def test_risk_scan_never_lowers():
    # declared medium, patterns only match medium → stays medium (just-high rule)
    text = "This skill queries employee information."
    result = scan_risk(text, RiskLevel.high)
    assert result == RiskLevel.high  # declared high, never lowered


def test_risk_scan_elevates_from_medium_to_high():
    text = "此技能对客户账户执行下单与转账操作。"
    result = scan_risk(text, RiskLevel.medium)
    assert result == RiskLevel.high
