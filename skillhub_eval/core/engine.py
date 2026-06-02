"""
EvaluationEngine — 1.3 v0.2 Architecture Contract state machine.

grill-me corrections applied:
  C-3: Explicit dual-phase execution
       • Pre-review phase: ingest → level0 → risk_lock → normalize
         ◦ If bundle NOT confirmed AND mode != degraded → stop at awaiting_confirm
         ◦ Degraded mode: continue but DecisionStage caps at warn
       • Post-confirm phase: triggered by POST /bundle/confirm → new run (mode D)
  C-5: Explicit ModelVote field mapping (no double ** expansion)
  C-6: scan_risk() for risk level locking (step ①+②)
  C-2: AggregateStage + DecisionStage enforce strict R1–R8
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from .aggregate import AggregateStage
from .assert_.dsl import DslEngine
from .decision import DecisionStage
from .ingest import ingest_bundle, load_sample_io
from .level0 import Level0Checker
from .risk_lock import scan_risk
from .schemas import (
    BundleState,
    DimensionScores,
    EvaluationMode,
    EvaluationReport,
    HumanReview,
    ModelVote,
    RunStatus,
    RiskLevel,
)

_DEFAULT_WORKFLOW_TIMEOUT = 180  # seconds


class EvaluationEngine:
    def __init__(self, repo, ds_provider, wb_provider, sandbox=None):
        self.repo = repo
        self.ds = ds_provider
        self.wb = wb_provider
        self.sandbox = sandbox
        self._agg = AggregateStage()
        self._dec = DecisionStage()
        self._dsl = DslEngine()
        self._workflow_timeout: float = _DEFAULT_WORKFLOW_TIMEOUT

    # ── public entry point ────────────────────────────────────────────────────

    async def run_async(
        self,
        run_id: str,
        skill_bundle_path: str,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
    ) -> None:
        """
        Drive the evaluation state machine.  Catches asyncio.TimeoutError and
        writes EVAL_WORKFLOW_TIMEOUT so callers always get a terminal state.
        """
        try:
            await asyncio.wait_for(
                self._execute(run_id, skill_bundle_path, bundle_state, evaluation_mode),
                timeout=self._workflow_timeout,
            )
        except asyncio.TimeoutError:
            self.repo.update_status(run_id, RunStatus.failed.value,
                                    reason_codes=["EVAL_WORKFLOW_TIMEOUT"])
            self.repo.log_event(run_id, "eval_workflow_timeout",
                                {"timeout_s": self._workflow_timeout})

    # ── state machine ─────────────────────────────────────────────────────────

    async def _execute(
        self,
        run_id: str,
        skill_bundle_path: str,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
    ) -> None:
        repo = self.repo

        # ── Phase 1a: Ingest ──────────────────────────────────────────────────
        repo.update_status(run_id, RunStatus.level0_checking.value)
        repo.append_stage(run_id, "level0_checking")
        bundle = ingest_bundle(skill_bundle_path)

        # ── Phase 1b: Level 0 ─────────────────────────────────────────────────
        l0 = Level0Checker().check(bundle)
        if not l0["passed"]:
            self._save_fail(run_id, bundle, bundle_state, evaluation_mode,
                            l0["reason_codes"], l0["evidence"])
            return

        # ── Phase 1c: Risk Lock (C-6: ①+②, ③ TODO 2.1) ──────────────────────
        repo.update_status(run_id, RunStatus.risk_locking.value)
        repo.append_stage(run_id, "risk_locking")

        declared_raw = bundle.get("risk_level_declared")
        declared = RiskLevel(declared_raw) if declared_raw else RiskLevel.low
        risk_locked = scan_risk(bundle.get("skill_md_text", ""), declared)
        repo.update_status(run_id, RunStatus.risk_locking.value,
                           risk_level_locked=risk_locked.value)

        # ── C-3: Dual-phase stop ──────────────────────────────────────────────
        # Non-confirmed + capability_full → stop; do NOT call model judges.
        # Degraded mode → continue (摸底评审), but cap at warn.
        is_confirmed = bundle_state == BundleState.confirmed
        is_degraded = evaluation_mode == EvaluationMode.degraded

        if not is_confirmed and not is_degraded:
            # Write gaps snapshot and park in awaiting_confirm
            repo.update_status(run_id, RunStatus.awaiting_confirm.value)
            repo.append_stage(run_id, "awaiting_confirm")
            gaps_json = self._build_gaps_snapshot(run_id, bundle, bundle_state)
            repo.save_gaps(run_id, gaps_json)
            # Do NOT call model judges — return here.
            return

        # ── Phase 2: Normalize (degraded / minor gaps) ────────────────────────
        repo.update_status(run_id, RunStatus.normalizing.value)
        repo.append_stage(run_id, "normalizing")
        if not is_confirmed:
            gaps_json = self._build_gaps_snapshot(run_id, bundle, bundle_state)
            repo.save_gaps(run_id, gaps_json)

        # ── Phase 3: CaseExec (Level 1 via sample_io / Level 2 via sandbox) ───
        repo.update_status(run_id, RunStatus.case_executing.value)
        repo.append_stage(run_id, "case_executing")

        level_achieved = "level_1"
        if bundle.get("has_scripts") and self.sandbox is not None:
            level_achieved = "level_2"

        cases = bundle["eval_cases"]

        # ── Phase 4: CodeAssert (DSL per case, C-1) ──────────────────────────
        repo.update_status(run_id, RunStatus.code_asserting.value)
        repo.append_stage(run_id, "code_asserting")
        redline_fail = False
        all_assertions_passed = True

        for case in cases:
            raw_assertions = case.get("assertions") or []
            if not raw_assertions:
                continue
            actual = load_sample_io(skill_bundle_path, case.get("id", ""))
            if actual is None:
                continue  # no sample_io for this case → skip, not a fail
            for assertion in raw_assertions:
                expr = self._assertion_to_expr(assertion)
                result = self._dsl.evaluate(expr, actual)
                if not result.get("passed", True):
                    all_assertions_passed = False
                    redline_fail = True
                    repo.log_event(run_id, "assertion_dsl_fail", {
                        "case_id": case.get("id"),
                        "assertion": assertion,
                        "reason": result.get("detail", ""),
                    })

        # ── Phase 5: Model Judging (DS + WB parallel per case) ───────────────
        repo.update_status(run_id, RunStatus.model_judging.value)
        repo.append_stage(run_id, "model_judging")

        all_votes: list[dict] = []
        for case in cases:
            prompt = self._build_prompt(case, bundle, bundle_state, evaluation_mode)
            ds_raw, wb_raw = await asyncio.gather(
                self.ds.judge(prompt),
                self.wb.judge(prompt),
                return_exceptions=True,
            )
            for provider_name, raw in [("deepseek", ds_raw), ("gemini", wb_raw)]:
                if isinstance(raw, Exception):
                    repo.log_event(run_id, "provider_error", {
                        "provider": provider_name,
                        "case_id": case.get("id"),
                        "error": str(raw),
                    })
                    continue
                score = self._extract_score(raw)
                status = "pass" if score >= 70 else "fail"
                all_votes.append({
                    "model": provider_name,
                    "model_version": "unknown",
                    "prompt_version": "review-agent-v0.2",
                    "case_id": case.get("id", "?"),
                    "dimension_scores": raw.get("sub_scores", {}),
                    "score_total": score,
                    "suggested_review_status": status,
                    "confidence": raw.get("confidence", "medium"),
                    "evidence_refs": [],
                    "feedback": raw.get("dimension_notes", ""),
                    "latency_ms": 0,
                })

        repo.save_votes(run_id, all_votes)

        # ── Phase 6: Aggregate ────────────────────────────────────────────────
        repo.update_status(run_id, RunStatus.aggregating.value)
        repo.append_stage(run_id, "aggregating")
        completeness_score = self._calc_completeness(bundle)
        agg = self._agg.run(
            votes=all_votes,
            assertion_passed=all_assertions_passed,
            completeness_score=completeness_score,
            redline_fail=redline_fail,
        )

        # ── Phase 7: Decision + PASS gate ─────────────────────────────────────
        dec_ctx = {
            "bundle_state": bundle_state,
            "evaluation_mode": evaluation_mode,
            "r5_triggered": agg["r5_triggered"],
            "r1_r4_fail": agg["r1_r4_fail"],
            "score_total": agg["score_total"],
            "completeness_score": completeness_score,
            "reason_codes": agg["reason_codes"],
            "level_requirement_met": True,
        }
        review_status = self._dec.decide(dec_ctx)
        human_required = self._dec.requires_human_review(dec_ctx, review_status)

        if human_required:
            repo.set_human_review_required(run_id, True, agg["reason_codes"])

        # ── Analytics events (1.3 §14 埋点) ──────────────────────────────────
        if agg["r5_triggered"]:
            repo.log_event(run_id, "eval_score_variance_detected", {
                "ds_score": agg["ds_score"],
                "wb_score": agg["wb_score"],
            })

        # ── Build ModelVote objects (C-5: explicit field mapping) ─────────────
        model_votes_obj = [
            ModelVote(
                model=v["model"],
                model_version=v.get("model_version", ""),
                prompt_version=v.get("prompt_version", "review-agent-v0.2"),
                case_id=v["case_id"],
                dimension_scores=DimensionScores(),
                score_total=v["score_total"],
                suggested_review_status=v.get("suggested_review_status", "warn"),
                confidence=v.get("confidence", "medium"),
                evidence_refs=v.get("evidence_refs", []),
                feedback=v.get("feedback", ""),
                latency_ms=v.get("latency_ms", 0),
            )
            for v in all_votes
        ]

        # ── Save report ───────────────────────────────────────────────────────
        report = EvaluationReport(
            run_id=run_id,
            skill_id=bundle["skill_id"],
            skill_bundle_path=skill_bundle_path,
            bundle_state=bundle_state,
            evaluation_mode=evaluation_mode,
            orchestration_mode=self._infer_mode(bundle_state, evaluation_mode, is_confirmed),
            status=RunStatus.completed if not human_required else RunStatus.awaiting_human_review,
            review_status=review_status,
            risk_level_locked=risk_locked,
            level_achieved=level_achieved,
            score_total=agg["score_total"],
            score_total_source=agg["score_total_source"],
            completeness_score=completeness_score,
            reason_codes=agg["reason_codes"],
            model_votes=model_votes_obj,
            human_review=HumanReview(
                required=human_required,
                trigger_codes=agg["reason_codes"] if human_required else [],
            ),
            rubric_version="v1.2",
            prompt_version="review-agent-v0.2",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )

        repo.save_report(run_id, report)
        final_status = (RunStatus.awaiting_human_review if human_required
                        else RunStatus.completed)
        repo.update_status(
            run_id,
            final_status.value,
            review_status=review_status,
            score_total=agg["score_total"],
        )

        # Persist report JSON to disk
        self._write_report_file(run_id, report)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _save_fail(
        self,
        run_id: str,
        bundle: dict,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
        reason_codes: list[str],
        evidence: list[dict],
    ) -> None:
        report = EvaluationReport(
            run_id=run_id,
            skill_id=bundle.get("skill_id", "?"),
            skill_bundle_path=bundle.get("bundle_path", "?"),
            bundle_state=bundle_state,
            evaluation_mode=evaluation_mode,
            status=RunStatus.failed,
            review_status="fail",
            reason_codes=reason_codes,
            evidence=evidence,
            rubric_version="v1.2",
            prompt_version="review-agent-v0.2",
        )
        self.repo.save_report(run_id, report)
        self.repo.update_status(run_id, RunStatus.failed.value, review_status="fail")

    def _build_gaps_snapshot(
        self,
        run_id: str,
        bundle: dict,
        bundle_state: BundleState,
    ) -> dict:
        """Minimal gaps snapshot for awaiting_confirm state."""
        gaps = []
        if not bundle["skill_meta"].get("description"):
            gaps.append({
                "field_path": "description",
                "severity": "warn",
                "message": "description is missing or empty",
                "draft_value": None,
                "confirmed": False,
            })
        return {
            "skill_id": bundle["skill_id"],
            "run_id": run_id,
            "gaps": gaps,
            "question_queue": [
                "请确认 negative_prompts 字段",
                "请确认 error_handling 字段",
            ],
        }

    def _build_prompt(
        self,
        case: dict,
        bundle: dict,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
    ) -> str:
        return (
            f"你是 SkillHub 质量评审员。仅评估本 case，不做最终 pass/fail 裁决。\n"
            f"skill_id: {bundle['skill_id']}\n"
            f"case_id: {case.get('id', '?')}\n"
            f"case_type: {case.get('type', 'happy_path')}\n"
            f"bundle_state: {bundle_state}\n"
            f"evaluation_mode: {evaluation_mode}\n"
            f"user_intent: {case.get('user_intent', '')}\n"
            f"rubric_version: v1.2\n"
            f"prompt_version: review-agent-v0.2\n"
            f'【输出格式】仅输出 JSON：{{"sub_scores":{{"step_completeness":{{"score":85,"pass":true,"reason":"ok","evidence_refs":[]}}}}'
            f',"confidence":"medium","dimension_notes":""}}'
        )

    def _extract_score(self, raw: dict) -> float:
        """Average sub-criterion scores from the provider response."""
        sub_scores = raw.get("sub_scores", {})
        scores = [
            v.get("score", 70)
            for v in sub_scores.values()
            if isinstance(v, dict)
        ]
        return round(sum(scores) / len(scores), 1) if scores else 70.0

    def _calc_completeness(self, bundle: dict) -> float:
        """Minimal completeness heuristic (full checklist in 2.1)."""
        score = 100.0
        if not bundle.get("has_sample_io"):
            score -= 15.0
        if not bundle["skill_meta"].get("description"):
            score -= 10.0
        return max(0.0, score)

    def _infer_mode(
        self,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
        is_confirmed: bool,
    ) -> str:
        if is_confirmed and evaluation_mode == EvaluationMode.capability_full:
            return "A"
        if bundle_state == BundleState.minimal:
            return "B"
        if bundle_state == BundleState.draft_enriched:
            return "C"
        return "D"

    @staticmethod
    def _assertion_to_expr(assertion: dict | str) -> str:
        """Convert a dict-form assertion (from YAML) to a DSL string expression."""
        if isinstance(assertion, str):
            return assertion
        op = assertion.get("op", "==")
        path = assertion.get("path", "response")
        expected = assertion.get("expected")
        low = assertion.get("low")
        high = assertion.get("high")
        if op == "numeric_range":
            return f"{path} numeric_range {low} {high}"
        if op in ("exists", "not_exists", "is_array", "is_string", "is_number"):
            return f"{path} {op}"
        if expected is not None:
            if isinstance(expected, str):
                return f"{path} {op} '{expected}'"
            return f"{path} {op} {expected}"
        return f"{path} {op}"

    def _write_report_file(self, run_id: str, report: EvaluationReport) -> None:
        try:
            out = Path(f"data/reports/{run_id}")
            out.mkdir(parents=True, exist_ok=True)
            (out / "evaluation_report.json").write_text(
                report.model_dump_json(indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass  # file write failure must not abort the run
