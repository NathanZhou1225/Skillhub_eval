"""
Case Sanitizer — W3-2.

Runs before CasePropagator. Analyzes staging eval_cases/:
  1. Moves malformed cases to staging/_broken/
  2. Computes type-coverage gap based on valid-type cases only
  3. Returns SanitizerResult indicating what Propagator needs to generate
"""

import shutil
from dataclasses import dataclass
from pathlib import Path

from skillhub_eval.core.ingest import _load_cases
from skillhub_eval.core.schemas.enums import CASE_TYPE_REQUIREMENTS, VALID_CASE_TYPES


@dataclass
class SanitizerResult:
    broken_moved: int           # number of malformed cases moved to _broken/
    invalid_type_count: int     # cases with type not in VALID_CASE_TYPES (kept in place)
    gap_by_type: dict[str, int] # {type: count_needed}; 0 means already satisfied
    needs_propagation: bool     # True if any gap_by_type value > 0
    existing_counts: dict[str, int]  # counts of cases with valid types only


class CaseSanitizer:
    def __init__(self, risk_level: str, staging_path: Path) -> None:
        """
        risk_level: "low" | "medium" | "high"
        staging_path: root of the staging directory (eval_cases/ is a subdirectory)
        """
        self.risk_level = risk_level
        self.staging_path = staging_path

    def run(self) -> SanitizerResult:
        """
        Execute sanitization:
        1. Load cases from staging_path/eval_cases/ via ingest._load_cases
        2. Move malformed_cases to staging_path/_broken/ (create dir if needed)
        3. Count existing_counts (only VALID_CASE_TYPES)
        4. Compute gap_by_type from CASE_TYPE_REQUIREMENTS[risk_level]
        5. Return SanitizerResult
        """
        eval_cases_dir = self.staging_path / "eval_cases"
        cases, malformed_cases = _load_cases(eval_cases_dir)

        # Move malformed cases to _broken/
        broken_moved = 0
        if malformed_cases:
            broken_dir = self.staging_path / "_broken"
            broken_dir.mkdir(exist_ok=True)
            for item in malformed_cases:
                src = item["path"]
                dst = broken_dir / Path(src).name
                shutil.move(src, str(dst))
                broken_moved += 1

        # Classify valid cases by type
        existing_counts: dict[str, int] = {}
        invalid_type_count = 0
        for case in cases:
            case_type = case.get("type")
            if case_type is None or case_type not in VALID_CASE_TYPES:
                invalid_type_count += 1
            else:
                existing_counts[case_type] = existing_counts.get(case_type, 0) + 1

        # Compute type-coverage gap
        requirements = CASE_TYPE_REQUIREMENTS.get(
            self.risk_level, CASE_TYPE_REQUIREMENTS["low"]
        )
        gap_by_type: dict[str, int] = {
            t: max(0, required - existing_counts.get(t, 0))
            for t, required in requirements.items()
        }
        needs_propagation = any(v > 0 for v in gap_by_type.values())

        return SanitizerResult(
            broken_moved=broken_moved,
            invalid_type_count=invalid_type_count,
            gap_by_type=gap_by_type,
            needs_propagation=needs_propagation,
            existing_counts=existing_counts,
        )
