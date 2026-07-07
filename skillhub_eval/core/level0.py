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

from .ingest import validate_execution_meta
from skillhub_eval.core.schemas.enums import RiskLevel, CASE_COUNT_GATES, CASE_TYPE_REQUIREMENTS, VALID_CASE_TYPES
from skillhub_eval.core.ingest import is_preflight_case


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
                "detail": "SKILL.md 文件缺失（需放置在包根目录）",
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
                "detail": f"risk_level 值无效：{risk_raw!r}，可选值为 low / high",
            })
            return {
                "passed": False,
                "reason_codes": reason_codes,
                "evidence": evidence,
            }

        meta_issues = validate_execution_meta(bundle)
        if meta_issues:
            reason_codes.append("LEVEL0_SCHEMA_FAIL")
            evidence.extend(meta_issues)
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
        type_counts: dict[str, int] = {}

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

        # Type coverage check (W3 题型完整性门槛) — only run after count passes
        if len(reason_codes) == 0:
            for c in (bundle.get("eval_cases") or []):
                if is_preflight_case(c):
                    continue
                t = c.get("type", "")
                if t in VALID_CASE_TYPES:
                    type_counts[t] = type_counts.get(t, 0) + 1
            required_types = CASE_TYPE_REQUIREMENTS.get(risk.value, {})
            missing_types = [t for t, min_n in required_types.items() if type_counts.get(t, 0) < min_n]
            if missing_types:
                reason_codes.append("MISSING_REQUIRED_CASE_TYPES")
                evidence.append({
                    "field": "eval_cases",
                    "detail": (
                        f"risk_level={risk.value} requires case types: {missing_types}. "
                        f"Current counts: {type_counts}"
                    ),
                })

        return {
            "passed": len(reason_codes) == 0,
            "risk_level": risk.value,
            "n_cases": n,
            "reason_codes": reason_codes,
            "evidence": evidence,
            "type_coverage": type_counts,
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
            "type_coverage": g.get("type_coverage", {}),
        }
