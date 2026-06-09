"""
Security Intake Gate — Level 0.5 (Wave 2).

Performs static-rule scanning of Skill bundle text before any LLM call.
Patterns are loaded from a YAML file so the security team can update rules
without touching Python code.

Result status hierarchy:
  "passed"  → all clear, continue pipeline
  "warning" → suspicious signals, continue but include findings in report
  "blocked" → hard violations → engine sets SECURITY_BLOCKED + FAIL
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATTERNS_PATH = _REPO_ROOT / "data" / "security_patterns.yaml"

_STATUS_RANK = {"passed": 0, "warning": 1, "blocked": 2}


@dataclass(frozen=True)
class SecurityFinding:
    group_id: str
    finding_type: str
    result_status: str      # "warning" or "blocked"
    matched_text: str       # excerpt of what triggered the rule
    pattern: str


@dataclass
class SecurityScanResult:
    status: str                              # "passed" | "warning" | "blocked"
    findings: list[SecurityFinding] = field(default_factory=list)

    def to_report_dict(self) -> dict:
        return {
            "status": self.status,
            "findings": [
                {
                    "group_id": f.group_id,
                    "finding_type": f.finding_type,
                    "result_status": f.result_status,
                    "matched_text": f.matched_text,
                }
                for f in self.findings
            ],
        }


def _load_patterns(path: Path) -> list[dict]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw.get("pattern_groups", [])


def security_scan(
    text: str,
    patterns_path: Path | None = None,
) -> SecurityScanResult:
    """
    Scan *text* (typically SKILL.md content + eval_cases YAML concatenated)
    against all pattern groups.

    Returns a SecurityScanResult with the aggregate status and individual
    findings.  The caller decides what to do based on status:
      - "blocked" → terminate evaluation with SECURITY_BLOCKED
      - "warning"  → continue, store findings in report
      - "passed"   → continue normally
    """
    path = patterns_path or _DEFAULT_PATTERNS_PATH
    groups = _load_patterns(path)

    findings: list[SecurityFinding] = []
    aggregate_rank = 0

    for group in groups:
        group_id = group["id"]
        result_status = group["result_status"]
        finding_type = group["finding_type"]
        for pattern_str in group.get("patterns", []):
            try:
                m = re.search(pattern_str, text)
            except re.error:
                continue
            if m:
                findings.append(
                    SecurityFinding(
                        group_id=group_id,
                        finding_type=finding_type,
                        result_status=result_status,
                        matched_text=_excerpt(text, m.start(), m.end()),
                        pattern=pattern_str,
                    )
                )
                rank = _STATUS_RANK.get(result_status, 0)
                if rank > aggregate_rank:
                    aggregate_rank = rank
                break  # one finding per group is enough

    status = {0: "passed", 1: "warning", 2: "blocked"}[aggregate_rank]
    return SecurityScanResult(status=status, findings=findings)


def _excerpt(text: str, start: int, end: int, context: int = 40) -> str:
    """Return a short excerpt around the match position."""
    lo = max(0, start - context)
    hi = min(len(text), end + context)
    raw = text[lo:hi]
    return "..." + raw + "..." if (lo > 0 or hi < len(text)) else raw
