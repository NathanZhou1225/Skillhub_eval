"""
Level 0 checker: structural validation + Case count gate X1.

Runs synchronously before any LLM call or sandbox execution.
Failure here terminates the run immediately (no LLM spend).
"""

from .schemas.enums import RiskLevel, CASE_COUNT_GATES


class Level0Checker:
    """
    Validates Skill package structure and enforces Case count gate X1:

        risk    min_cases   mvp_ceiling
        low         3           6
        medium      5           8
        high        9          12

    Both bounds are hard-fail (no truncation, no smart selection).
    """

    def check(self, bundle: dict) -> dict:
        reason_codes: list[str] = []
        evidence: list[dict] = []

        # ── Structural: SKILL.md must be present ──────────────────────────────
        if not bundle.get("has_skill_md"):
            reason_codes.append("LEVEL0_SCHEMA_FAIL")
            evidence.append({
                "field": "SKILL.md",
                "detail": "SKILL.md missing from bundle root",
            })
            return {"passed": False, "reason_codes": reason_codes, "evidence": evidence}

        # ── Risk level: parse or fall back to low ─────────────────────────────
        risk_raw = bundle.get("risk_level_declared")
        try:
            risk = RiskLevel(risk_raw) if risk_raw else RiskLevel.low
        except ValueError:
            reason_codes.append("LEVEL0_SCHEMA_FAIL")
            evidence.append({
                "field": "risk_level",
                "detail": f"Unknown risk_level value: {risk_raw!r}",
            })
            return {"passed": False, "reason_codes": reason_codes, "evidence": evidence}

        # ── Case count gate X1 ────────────────────────────────────────────────
        n = bundle.get("n_cases", 0)
        min_cases, ceiling = CASE_COUNT_GATES[risk]

        if n < min_cases:
            reason_codes.append("RISK_CASE_COUNT_INSUFFICIENT")
            evidence.append({
                "field": "eval_cases",
                "detail": (
                    f"risk_level={risk.value} requires >= {min_cases} cases; "
                    f"found {n}. Add {min_cases - n} more case(s)."
                ),
            })
        elif n > ceiling:
            reason_codes.append("CASE_COUNT_EXCEEDS_LIMIT")
            evidence.append({
                "field": "eval_cases",
                "detail": (
                    f"risk_level={risk.value} MVP ceiling={ceiling}; "
                    f"found {n}. Remove {n - ceiling} case(s) — "
                    "do not rely on auto-truncation."
                ),
            })

        passed = len(reason_codes) == 0
        return {
            "passed": passed,
            "risk_level": risk.value,
            "n_cases": n,
            "reason_codes": reason_codes,
            "evidence": evidence,
        }
