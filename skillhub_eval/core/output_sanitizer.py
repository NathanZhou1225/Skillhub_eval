"""
Output Sanitizer — post-CodeAssert PII / credential leak detection (Wave 2).

Checks the *actual* sample_io output (JSON dict) for sensitive content that
should never appear in a Skill's golden output:
  - Chinese phone numbers
  - Chinese national ID card numbers
  - Email addresses that look like PII
  - Hardcoded secrets / API keys

Called once per evaluation run after the CodeAssert phase completes.
If a leak is detected the run is failed with reason_code SECURITY_OUTPUT_LEAK.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


# ── PII / secret patterns ─────────────────────────────────────────────────────

_PII_PATTERNS: list[tuple[str, str]] = [
    # Chinese mobile phone: 1 + [3-9] + 9 digits
    (r"(?<!\d)1[3-9]\d{9}(?!\d)", "PHONE_NUMBER"),
    # Chinese national ID: 17 digits + (digit or X)
    (r"\b\d{17}[\dX]\b", "NATIONAL_ID"),
    # Generic email
    (r"[A-Za-z0-9._%+\-]{2,}@[A-Za-z0-9.\-]{2,}\.[A-Za-z]{2,}", "EMAIL_ADDRESS"),
]

_SECRET_PATTERNS: list[tuple[str, str]] = [
    # OpenAI-style key
    (r"sk-[A-Za-z0-9]{20,}", "API_KEY"),
    # AWS access key
    (r"AKIA[0-9A-Z]{16}", "AWS_ACCESS_KEY"),
    # Bearer token
    (r"Bearer\s+[A-Za-z0-9\-._~+/=]{16,}", "BEARER_TOKEN"),
    # Inline password/api_key assignment
    (r'(?i)(password|passwd|api[_\-]?key|secret[_\-]?key)\s*[=:]\s*["\'][^"\']{6,}["\']', "HARDCODED_CREDENTIAL"),
]

_ALL_PATTERNS = _PII_PATTERNS + _SECRET_PATTERNS


@dataclass(frozen=True)
class SanitizerFinding:
    finding_type: str
    matched_text: str       # short excerpt
    source: str             # e.g. "case_id:case-001"


@dataclass
class SanitizeResult:
    status: str                                  # "passed" | "leak"
    findings: list[SanitizerFinding] = field(default_factory=list)

    def to_report_dict(self) -> dict:
        return {
            "status": self.status,
            "findings": [
                {
                    "finding_type": f.finding_type,
                    "matched_text": f.matched_text,
                    "source": f.source,
                }
                for f in self.findings
            ],
        }


def sanitize_output(actual: dict | None, case_id: str = "") -> list[SanitizerFinding]:
    """
    Check one case's actual sample_io dict for PII / credential leaks.

    Returns a (possibly empty) list of SanitizerFinding.  The caller
    aggregates findings across all cases.
    """
    if actual is None:
        return []

    # Flatten the dict to a single string for pattern matching
    try:
        text = json.dumps(actual, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(actual)

    findings: list[SanitizerFinding] = []
    source_label = f"case_id:{case_id}" if case_id else "sample_io"

    for pattern_str, finding_type in _ALL_PATTERNS:
        m = re.search(pattern_str, text)
        if m:
            findings.append(
                SanitizerFinding(
                    finding_type=finding_type,
                    matched_text=_excerpt(text, m.start(), m.end()),
                    source=source_label,
                )
            )

    return findings


def run_output_sanitizer(
    cases: list[dict],
    load_sample_io_fn,          # callable(bundle_path, case_id) -> dict | None
    skill_bundle_path: str,
) -> SanitizeResult:
    """
    Sanitize all cases' sample_io outputs for the current bundle.

    *load_sample_io_fn* should be the same function used in the engine's
    CodeAssert phase so we re-use the same I/O loading logic.
    """
    all_findings: list[SanitizerFinding] = []

    for case in cases:
        case_id = case.get("id", "")
        actual = load_sample_io_fn(skill_bundle_path, case_id)
        if actual is None:
            continue
        case_findings = sanitize_output(actual, case_id)
        all_findings.extend(case_findings)

    status = "leak" if all_findings else "passed"
    return SanitizeResult(status=status, findings=all_findings)


def _excerpt(text: str, start: int, end: int, context: int = 30) -> str:
    lo = max(0, start - context)
    hi = min(len(text), end + context)
    raw = text[lo:hi]
    prefix = "..." if lo > 0 else ""
    suffix = "..." if hi < len(text) else ""
    return prefix + raw + suffix
