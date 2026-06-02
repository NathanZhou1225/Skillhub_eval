"""
Tests for the §6.4 DSL assertion engine (C-1 correction).
Covers all 8 protocol operators + 2 extension operators.
Must include at least one ASSERTION_DSL_FAIL case (grill-me C-1 requirement).
"""

import pytest

from skillhub_eval.core.assert_.dsl import DslEngine, DslParseError


# ─── shared test data ────────────────────────────────────────────────────────

SAMPLE_OUTPUT = {
    "status": "success",
    "employee_id": "E123",
    "abnormal_days": [3, 5, 8],
    "count": 42,
    "active": True,
    "note": "no issues found",
    "nested": {"level": "high"},
}


@pytest.fixture
def engine():
    return DslEngine()


# ─── == (equals) ─────────────────────────────────────────────────────────────

def test_equals_string_pass(engine):
    result = engine.evaluate("response.status == 'success'", SAMPLE_OUTPUT)
    assert result["passed"] is True


def test_equals_string_fail(engine):
    result = engine.evaluate("response.status == 'failure'", SAMPLE_OUTPUT)
    assert result["passed"] is False
    assert result["reason_code"] == "ASSERTION_DSL_FAIL"


def test_equals_number_pass(engine):
    result = engine.evaluate("response.count == 42", SAMPLE_OUTPUT)
    assert result["passed"] is True


def test_equals_bool_pass(engine):
    result = engine.evaluate("response.active == true", SAMPLE_OUTPUT)
    assert result["passed"] is True


# ─── != (not equals) ─────────────────────────────────────────────────────────

def test_not_equals_pass(engine):
    result = engine.evaluate("response.status != 'error'", SAMPLE_OUTPUT)
    assert result["passed"] is True


def test_not_equals_fail(engine):
    result = engine.evaluate("response.status != 'success'", SAMPLE_OUTPUT)
    assert result["passed"] is False
    assert result["reason_code"] == "ASSERTION_DSL_FAIL"


# ─── exists / not_exists ─────────────────────────────────────────────────────

def test_exists_pass(engine):
    result = engine.evaluate("response.employee_id exists", SAMPLE_OUTPUT)
    assert result["passed"] is True


def test_exists_fail_missing_field(engine):
    result = engine.evaluate("response.missing_field exists", SAMPLE_OUTPUT)
    assert result["passed"] is False
    assert result["reason_code"] == "ASSERTION_DSL_FAIL"


def test_not_exists_pass(engine):
    result = engine.evaluate("response.ghost_field not_exists", SAMPLE_OUTPUT)
    assert result["passed"] is True


def test_not_exists_fail(engine):
    result = engine.evaluate("response.status not_exists", SAMPLE_OUTPUT)
    assert result["passed"] is False
    assert result["reason_code"] == "ASSERTION_DSL_FAIL"


# ─── is_array / is_string / is_number ────────────────────────────────────────

def test_is_array_pass(engine):
    result = engine.evaluate("response.abnormal_days is_array", SAMPLE_OUTPUT)
    assert result["passed"] is True


def test_is_array_fail(engine):
    result = engine.evaluate("response.status is_array", SAMPLE_OUTPUT)
    assert result["passed"] is False
    assert result["reason_code"] == "ASSERTION_DSL_FAIL"


def test_is_string_pass(engine):
    result = engine.evaluate("response.employee_id is_string", SAMPLE_OUTPUT)
    assert result["passed"] is True


def test_is_number_pass(engine):
    result = engine.evaluate("response.count is_number", SAMPLE_OUTPUT)
    assert result["passed"] is True


def test_is_number_fail(engine):
    result = engine.evaluate("response.abnormal_days is_number", SAMPLE_OUTPUT)
    assert result["passed"] is False
    assert result["reason_code"] == "ASSERTION_DSL_FAIL"


# ─── contains ────────────────────────────────────────────────────────────────

def test_contains_string_pass(engine):
    result = engine.evaluate("response.note contains 'no issues'", SAMPLE_OUTPUT)
    assert result["passed"] is True


def test_contains_array_pass(engine):
    result = engine.evaluate("response.abnormal_days contains 5", SAMPLE_OUTPUT)
    assert result["passed"] is True


def test_contains_fail(engine):
    result = engine.evaluate("response.note contains 'critical error'", SAMPLE_OUTPUT)
    assert result["passed"] is False
    assert result["reason_code"] == "ASSERTION_DSL_FAIL"


# ─── nested path ─────────────────────────────────────────────────────────────

def test_nested_path_pass(engine):
    result = engine.evaluate("response.nested.level == 'high'", SAMPLE_OUTPUT)
    assert result["passed"] is True


def test_nested_path_missing(engine):
    result = engine.evaluate("response.nested.deep.key exists", SAMPLE_OUTPUT)
    assert result["passed"] is False


# ─── extension: regex_match ──────────────────────────────────────────────────

def test_regex_match_pass(engine):
    result = engine.evaluate(r"response.employee_id regex_match 'E\d+'", SAMPLE_OUTPUT)
    assert result["passed"] is True


def test_regex_match_fail(engine):
    result = engine.evaluate(r"response.employee_id regex_match '^\d+$'", SAMPLE_OUTPUT)
    assert result["passed"] is False
    assert result["reason_code"] == "ASSERTION_DSL_FAIL"


# ─── extension: numeric_range ────────────────────────────────────────────────

def test_numeric_range_pass(engine):
    result = engine.evaluate("response.count numeric_range 10 100", SAMPLE_OUTPUT)
    assert result["passed"] is True


def test_numeric_range_fail_below(engine):
    result = engine.evaluate("response.count numeric_range 50 100", SAMPLE_OUTPUT)
    assert result["passed"] is False
    assert result["reason_code"] == "ASSERTION_DSL_FAIL"


# ─── batch evaluate (used by engine) ─────────────────────────────────────────

def test_batch_all_pass(engine):
    assertions = [
        "response.status == 'success'",
        "response.employee_id exists",
        "response.abnormal_days is_array",
    ]
    results = engine.evaluate_all(assertions, SAMPLE_OUTPUT, case_id="c01")
    assert all(r["passed"] for r in results)


def test_batch_with_one_fail_returns_fail_entry(engine):
    """
    C-1 grill-me requirement: ASSERTION_DSL_FAIL must be verifiable in batch.
    """
    assertions = [
        "response.status == 'success'",           # pass
        "response.employee_id == 'WRONG_ID'",     # ASSERTION_DSL_FAIL
        "response.abnormal_days is_array",         # pass
    ]
    results = engine.evaluate_all(assertions, SAMPLE_OUTPUT, case_id="c02")
    failed = [r for r in results if not r["passed"]]
    assert len(failed) == 1
    assert failed[0]["reason_code"] == "ASSERTION_DSL_FAIL"
    assert "WRONG_ID" in failed[0]["detail"] or "employee_id" in failed[0]["detail"]


# ─── parse error ─────────────────────────────────────────────────────────────

def test_parse_error_raises(engine):
    with pytest.raises(DslParseError):
        engine.evaluate("response.status ??? 'value'", SAMPLE_OUTPUT)
