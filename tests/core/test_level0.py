import pytest

from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.core.level0 import Level0Checker
from skillhub_eval.core.risk_lock import scan_risk
from skillhub_eval.core.schemas import RiskLevel


# ─── T1: check_structure / check_case_gate 拆分 ───────────────────────────────

def test_check_structure_passes_with_zero_cases(tmp_path):
    """check_structure() must pass even when there are 0 eval_cases (no case gate)."""
    (tmp_path / "SKILL.md").write_text(
        "---\nname: minimal-skill\nrisk_level: low\n---\n# Minimal\n",
        encoding="utf-8",
    )
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check_structure(bundle)
    assert result["passed"] is True
    assert result["reason_codes"] == []


def test_check_structure_fails_no_skill_md(tmp_path):
    """check_structure() must fail when SKILL.md is absent."""
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check_structure(bundle)
    assert result["passed"] is False
    assert "LEVEL0_SCHEMA_FAIL" in result["reason_codes"]


def test_check_structure_fails_invalid_risk_level(tmp_path):
    """check_structure() must fail when risk_level value is unrecognised."""
    (tmp_path / "SKILL.md").write_text(
        "---\nname: x\nrisk_level: extreme\n---\n",
        encoding="utf-8",
    )
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check_structure(bundle)
    assert result["passed"] is False
    assert "LEVEL0_SCHEMA_FAIL" in result["reason_codes"]


def test_check_case_gate_passes(tmp_path):
    """check_case_gate() must pass for a low-risk bundle with exactly 3 cases."""
    make_bundle(tmp_path, n_cases=3, risk="low")
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check_case_gate(bundle)
    assert result["passed"] is True


def test_check_case_gate_fails_too_few(tmp_path):
    """check_case_gate() must fail when n_cases < X1 min."""
    make_bundle(tmp_path, n_cases=1, risk="low")
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check_case_gate(bundle)
    assert result["passed"] is False
    assert "RISK_CASE_COUNT_INSUFFICIENT" in result["reason_codes"]


def test_check_case_gate_independent_of_structure(tmp_path):
    """check_case_gate() operates independently—no SKILL.md check."""
    # Bundle with valid cases but no SKILL.md (structure would fail, gate should still run)
    ec = tmp_path / "eval_cases"
    ec.mkdir()
    for i in range(3):
        (ec / f"c{i:02d}.yaml").write_text(
            f"id: c{i:02d}\ntype: happy_path\nuser_intent: test\n",
            encoding="utf-8",
        )
    bundle = ingest_bundle(str(tmp_path))
    # Gate uses declared risk (None → low default) and n_cases=3 → passes
    result = Level0Checker().check_case_gate(bundle)
    assert result["passed"] is True


# ─── fixtures ────────────────────────────────────────────────────────────────

def make_bundle(tmp_path, n_cases: int = 3, risk: str = "low", has_skill_md: bool = True):
    if has_skill_md:
        (tmp_path / "SKILL.md").write_text(
            f"---\nname: test\nrisk_level: {risk}\n---\n# Test Skill\n",
            encoding="utf-8",
        )
    ec = tmp_path / "eval_cases"
    ec.mkdir(exist_ok=True)
    # Generate a type sequence that satisfies W3 type coverage for the given risk level.
    # Pattern: 3 happy_path, then 2 edge, 2 refusal, 2 adversarial (cycling for extras).
    _type_sequence = [
        "happy_path", "happy_path", "happy_path",
        "edge", "edge",
        "refusal", "refusal",
        "adversarial", "adversarial",
        "edge", "edge", "edge",  # extra slots for high-ceiling bundles
    ]
    for i in range(n_cases):
        ctype = _type_sequence[i] if i < len(_type_sequence) else "edge"
        (ec / f"case_{i:02d}.yaml").write_text(
            f"id: case_{i:02d}\ntype: {ctype}\nuser_intent: test intent\n",
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


def test_high_risk_nine_case_mix_passes_gate(tmp_path):
    """2.2 stock-radar quota: 3 happy + 2 edge + 2 refusal + 2 adversarial."""
    (tmp_path / "SKILL.md").write_text(
        "---\nname: stock-radar\nrisk_level: high\n---\n# Stock radar\n",
        encoding="utf-8",
    )
    ec = tmp_path / "eval_cases"
    ec.mkdir()
    spec = [
        ("h01", "happy_path"), ("h02", "happy_path"), ("h03", "happy_path"),
        ("e01", "edge"), ("e02", "edge"),
        ("r01", "refusal"), ("r02", "refusal"),
        ("a01", "adversarial"), ("a02", "adversarial"),
    ]
    for cid, ctype in spec:
        (ec / f"{cid}.yaml").write_text(
            f"id: {cid}\ntype: {ctype}\nuser_intent: test\n",
            encoding="utf-8",
        )
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check_case_gate(bundle)
    assert result["passed"] is True


# ─── W3 type coverage tests ───────────────────────────────────────────────────

def test_check_case_gate_low_risk_missing_happy_path():
    """low risk: needs 3 happy_path; fewer triggers MISSING_REQUIRED_CASE_TYPES"""
    checker = Level0Checker()
    bundle = {
        "risk_level_declared": "low",
        "n_cases": 3,
        "eval_cases": [
            {"id": "c1", "type": "edge"},
            {"id": "c2", "type": "edge"},
            {"id": "c3", "type": "edge"},
        ],
    }
    result = checker.check_case_gate(bundle)
    assert result["passed"] is False
    assert "MISSING_REQUIRED_CASE_TYPES" in result["reason_codes"]


def test_check_case_gate_medium_risk_complete():
    """medium risk with 3 happy + 2 edge passes"""
    checker = Level0Checker()
    bundle = {
        "risk_level_declared": "medium",
        "n_cases": 5,
        "eval_cases": [
            {"id": "c1", "type": "happy_path"},
            {"id": "c2", "type": "happy_path"},
            {"id": "c3", "type": "happy_path"},
            {"id": "c4", "type": "edge"},
            {"id": "c5", "type": "edge"},
        ],
    }
    result = checker.check_case_gate(bundle)
    assert result["passed"] is True
    assert "MISSING_REQUIRED_CASE_TYPES" not in result["reason_codes"]


def test_check_case_gate_high_risk_missing_adversarial():
    """high risk: missing adversarial type triggers MISSING_REQUIRED_CASE_TYPES"""
    checker = Level0Checker()
    bundle = {
        "risk_level_declared": "high",
        "n_cases": 9,
        "eval_cases": (
            [{"id": f"h{i}", "type": "happy_path"} for i in range(3)]
            + [{"id": f"e{i}", "type": "edge"} for i in range(2)]
            + [{"id": f"r{i}", "type": "refusal"} for i in range(2)]
            + [{"id": f"x{i}", "type": "edge"} for i in range(2)]  # extra edge, no adversarial
        ),
    }
    result = checker.check_case_gate(bundle)
    assert result["passed"] is False
    assert "MISSING_REQUIRED_CASE_TYPES" in result["reason_codes"]


def test_check_case_gate_high_risk_complete():
    """high risk with full type coverage passes"""
    checker = Level0Checker()
    bundle = {
        "risk_level_declared": "high",
        "n_cases": 9,
        "eval_cases": (
            [{"id": f"h{i}", "type": "happy_path"} for i in range(3)]
            + [{"id": f"e{i}", "type": "edge"} for i in range(2)]
            + [{"id": f"r{i}", "type": "refusal"} for i in range(2)]
            + [{"id": f"a{i}", "type": "adversarial"} for i in range(2)]
        ),
    }
    result = checker.check_case_gate(bundle)
    assert result["passed"] is True


def test_check_case_gate_type_missing_field_ignored():
    """cases without type field are not counted toward required types"""
    checker = Level0Checker()
    bundle = {
        "risk_level_declared": "low",
        "n_cases": 3,
        "eval_cases": [
            {"id": "c1"},  # no type field
            {"id": "c2"},
            {"id": "c3"},
        ],
    }
    result = checker.check_case_gate(bundle)
    assert result["passed"] is False
    assert "MISSING_REQUIRED_CASE_TYPES" in result["reason_codes"]


def test_case_type_requirements_constant_structure():
    """CASE_TYPE_REQUIREMENTS has correct structure for all risk levels"""
    from skillhub_eval.core.schemas.enums import CASE_TYPE_REQUIREMENTS, VALID_CASE_TYPES
    assert set(CASE_TYPE_REQUIREMENTS.keys()) == {"low", "medium", "high"}
    assert CASE_TYPE_REQUIREMENTS["low"]["happy_path"] == 3
    assert CASE_TYPE_REQUIREMENTS["medium"]["edge"] == 2
    assert CASE_TYPE_REQUIREMENTS["high"]["adversarial"] == 2
    for types in CASE_TYPE_REQUIREMENTS.values():
        for t in types:
            assert t in VALID_CASE_TYPES
