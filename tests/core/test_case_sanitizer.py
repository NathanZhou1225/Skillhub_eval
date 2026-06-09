"""Tests for CaseSanitizer (W3-2)."""

from pathlib import Path

import pytest

from skillhub_eval.core.case_sanitizer import CaseSanitizer, SanitizerResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_case_file(cases_dir: Path, case_id: str, case_type: str | None = None) -> None:
    """Write a valid YAML case file into cases_dir."""
    content = f"id: {case_id}\n"
    if case_type is not None:
        content += f"type: {case_type}\n"
    content += "user_intent: test intent\n"
    (cases_dir / f"{case_id}.yaml").write_text(content, encoding="utf-8")


def make_malformed_file(cases_dir: Path, filename: str) -> None:
    """Write an invalid YAML file (missing id)."""
    (cases_dir / filename).write_text(
        "type: happy_path\nuser_intent: no id here\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Test 1: no eval_cases directory
# ---------------------------------------------------------------------------

def test_no_eval_cases_dir(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    result = CaseSanitizer("low", staging).run()

    assert isinstance(result, SanitizerResult)
    assert result.broken_moved == 0
    assert result.invalid_type_count == 0
    assert result.gap_by_type == {"happy_path": 3}
    assert result.needs_propagation is True
    assert result.existing_counts == {}


# ---------------------------------------------------------------------------
# Test 2: all valid, types complete for low risk
# ---------------------------------------------------------------------------

def test_all_valid_low_risk_complete(tmp_path):
    staging = tmp_path / "staging"
    cases_dir = staging / "eval_cases"
    cases_dir.mkdir(parents=True)
    for i in range(3):
        make_case_file(cases_dir, f"h{i}", "happy_path")

    result = CaseSanitizer("low", staging).run()

    assert result.broken_moved == 0
    assert result.invalid_type_count == 0
    assert result.gap_by_type == {"happy_path": 0}
    assert result.needs_propagation is False
    assert result.existing_counts == {"happy_path": 3}


# ---------------------------------------------------------------------------
# Test 3: medium risk with only happy_path cases
# ---------------------------------------------------------------------------

def test_medium_only_happy_path(tmp_path):
    staging = tmp_path / "staging"
    cases_dir = staging / "eval_cases"
    cases_dir.mkdir(parents=True)
    for i in range(3):
        make_case_file(cases_dir, f"h{i}", "happy_path")

    result = CaseSanitizer("medium", staging).run()

    assert result.gap_by_type == {"happy_path": 0, "edge": 2}
    assert result.needs_propagation is True
    assert result.broken_moved == 0
    assert result.invalid_type_count == 0


# ---------------------------------------------------------------------------
# Test 4: malformed YAML case moved to _broken/
# ---------------------------------------------------------------------------

def test_malformed_case_moved(tmp_path):
    staging = tmp_path / "staging"
    cases_dir = staging / "eval_cases"
    cases_dir.mkdir(parents=True)
    make_malformed_file(cases_dir, "bad.yaml")

    result = CaseSanitizer("low", staging).run()

    assert result.broken_moved == 1
    broken_dir = staging / "_broken"
    assert broken_dir.exists()
    assert (broken_dir / "bad.yaml").exists()
    assert not (cases_dir / "bad.yaml").exists()
    assert result.gap_by_type == {"happy_path": 3}
    assert result.needs_propagation is True
    assert result.existing_counts == {}


# ---------------------------------------------------------------------------
# Test 5: case with missing type field
# ---------------------------------------------------------------------------

def test_missing_type_field(tmp_path):
    staging = tmp_path / "staging"
    cases_dir = staging / "eval_cases"
    cases_dir.mkdir(parents=True)
    make_case_file(cases_dir, "c1", None)  # no type field

    result = CaseSanitizer("low", staging).run()

    assert result.invalid_type_count == 1
    assert result.broken_moved == 0
    assert result.existing_counts == {}
    assert result.gap_by_type == {"happy_path": 3}
    # file stays in place (not moved)
    assert (cases_dir / "c1.yaml").exists()


# ---------------------------------------------------------------------------
# Test 6: case with unknown type value
# ---------------------------------------------------------------------------

def test_unknown_type_value(tmp_path):
    staging = tmp_path / "staging"
    cases_dir = staging / "eval_cases"
    cases_dir.mkdir(parents=True)
    make_case_file(cases_dir, "c1", "custom_type")

    result = CaseSanitizer("low", staging).run()

    assert result.invalid_type_count == 1
    assert result.broken_moved == 0
    assert result.existing_counts == {}
    assert result.gap_by_type == {"happy_path": 3}
    # file stays in place (not moved)
    assert (cases_dir / "c1.yaml").exists()


# ---------------------------------------------------------------------------
# Test 7: high risk fully covered
# ---------------------------------------------------------------------------

def test_high_risk_fully_covered(tmp_path):
    staging = tmp_path / "staging"
    cases_dir = staging / "eval_cases"
    cases_dir.mkdir(parents=True)
    for i in range(3):
        make_case_file(cases_dir, f"h{i}", "happy_path")
    for i in range(2):
        make_case_file(cases_dir, f"e{i}", "edge")
    for i in range(2):
        make_case_file(cases_dir, f"r{i}", "refusal")
    for i in range(2):
        make_case_file(cases_dir, f"a{i}", "adversarial")

    result = CaseSanitizer("high", staging).run()

    assert result.needs_propagation is False
    assert all(v == 0 for v in result.gap_by_type.values())
    assert result.broken_moved == 0
    assert result.invalid_type_count == 0
    assert result.existing_counts == {
        "happy_path": 3,
        "edge": 2,
        "refusal": 2,
        "adversarial": 2,
    }


# ---------------------------------------------------------------------------
# Test 8: mixed — malformed + missing type + 2 valid happy_path (medium)
# ---------------------------------------------------------------------------

def test_mixed_malformed_missing_type_and_valid(tmp_path):
    staging = tmp_path / "staging"
    cases_dir = staging / "eval_cases"
    cases_dir.mkdir(parents=True)
    make_malformed_file(cases_dir, "bad.yaml")
    make_case_file(cases_dir, "no_type")       # no type field
    make_case_file(cases_dir, "h1", "happy_path")
    make_case_file(cases_dir, "h2", "happy_path")

    result = CaseSanitizer("medium", staging).run()

    assert result.broken_moved == 1
    assert result.invalid_type_count == 1
    assert result.existing_counts == {"happy_path": 2}
    assert result.gap_by_type == {"happy_path": 1, "edge": 2}
    assert result.needs_propagation is True
    assert (staging / "_broken" / "bad.yaml").exists()


# ---------------------------------------------------------------------------
# Test 9: unknown risk_level defaults to low
# ---------------------------------------------------------------------------

def test_unknown_risk_level_defaults_to_low(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()

    result = CaseSanitizer("ultra_high", staging).run()

    # Should not raise; treat as low
    assert result.gap_by_type == {"happy_path": 3}
    assert result.needs_propagation is True


# ---------------------------------------------------------------------------
# Test 10: existing_counts only includes types with cases present
# ---------------------------------------------------------------------------

def test_existing_counts_only_present_types(tmp_path):
    staging = tmp_path / "staging"
    cases_dir = staging / "eval_cases"
    cases_dir.mkdir(parents=True)
    make_case_file(cases_dir, "h1", "happy_path")
    make_case_file(cases_dir, "h2", "happy_path")

    result = CaseSanitizer("high", staging).run()

    # Only happy_path in existing_counts (edge/refusal/adversarial have no cases)
    assert result.existing_counts == {"happy_path": 2}
    assert result.gap_by_type["happy_path"] == 1
    assert result.gap_by_type["edge"] == 2
    assert result.gap_by_type["refusal"] == 2
    assert result.gap_by_type["adversarial"] == 2
    assert result.needs_propagation is True
