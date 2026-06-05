"""
Level 0 checker: structural validation + Case count gate X1.

Runs synchronously before any LLM call or sandbox execution.
Failure here terminates the run immediately (no LLM spend).

T1 fix: split into check_structure() and check_case_gate() so the engine
can apply them at different points in the pipeline:
  - check_structure() → always; fail stops the run immediately
  - check_case_gate() → only for confirmed bundles (post-confirm phase)
                        degraded and pre-confirm paths skip the gate
"""

from .schemas.enums import RiskLevel, CASE_COUNT_GATES


class Level0Checker:
    """
    Validates Skill package structure (check_structure) and enforces Case
    count gate X1 (check_case_gate) independently.

        risk    min_cases   mvp_ceiling
        low         3           6
        medium      5           8
        high        9          12

    Both bounds are hard-fail (no truncation, no smart selection).
    """

    # ── check_structure: SKILL.md present + risk_level parseable ─────────────

    def check_structure(self, bundle: dict) -> dict:
        """
        Structural gate only — does NOT check case count.
        Returns dict: {passed, reason_codes, evidence, risk_level (if parsed)}
        """
        reason_codes: list[str] = []
        evidence: list[dict] = []

        if not bundle.get("has_skill_md"):
            reason_codes.append("LEVEL0_SCHEMA_FAIL")
            evidence.append({
                "field": "SKILL.md",
                "detail": "SKILL.md missing from bundle root",
            })
            return {
                "passed": False,
                "reason_codes": reason_codes,
                "evidence": evidence,
            }

        risk_raw = bundle.get("risk_level_declared")
        try:
            risk = RiskLevel(risk_raw) if risk_raw else RiskLevel.low
        except ValueError:
            reason_codes.append("LEVEL0_SCHEMA_FAIL")
            evidence.append({
                "field": "risk_level",
                "detail": f"Unknown risk_level value: {risk_raw!r}",
            })
            return {
                "passed": False,
                "reason_codes": reason_codes,
                "evidence": evidence,
            }

        return {
            "passed": True,
            "reason_codes": [],
            "evidence": [],
            "risk_level": risk.value,
        }

    # ── check_case_gate: X1 case count bounds ────────────────────────────────

    def check_case_gate(self, bundle: dict) -> dict:
        """
        Case count gate X1 — independent of structural checks.
        Caller is responsible for only invoking this when appropriate
        (i.e. confirmed bundles in post-confirm phase).
        """
        reason_codes: list[str] = []
        evidence: list[dict] = []

        risk_raw = bundle.get("risk_level_declared")
        try:
            risk = RiskLevel(risk_raw) if risk_raw else RiskLevel.low
        except ValueError:
            risk = RiskLevel.low

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

        return {
            "passed": len(reason_codes) == 0,
            "risk_level": risk.value,
            "n_cases": n,
            "reason_codes": reason_codes,
            "evidence": evidence,
        }

    # ── check: backward-compat combined gate ─────────────────────────────────

    def check(self, bundle: dict) -> dict:
        """
        Combined structure + case gate check (legacy / test compat).
        Equivalent to check_structure() then check_case_gate() in sequence.
        """
        s = self.check_structure(bundle)
        if not s["passed"]:
            return s
        g = self.check_case_gate(bundle)
        return {
            "passed": g["passed"],
            "risk_level": g["risk_level"],
            "n_cases": g["n_cases"],
            "reason_codes": g["reason_codes"],
            "evidence": g["evidence"],
        }
