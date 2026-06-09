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
import time
from datetime import UTC, datetime
from pathlib import Path

from .aggregate import AggregateStage
from .assert_.dsl import DslEngine
from .decision import DecisionStage
from .gaps import scan_gaps
from .provider_summary import build_provider_summary
from .ingest import ingest_bundle, load_sample_io
from .latency import (
    CASE_JUDGE_CONCURRENCY,
    PROVIDER_CALL_TIMEOUT_HIGH_RISK_S,
    PROVIDER_CALL_TIMEOUT_S,
    workflow_timeout_seconds,
)
from .level0 import Level0Checker
from .output_sanitizer import run_output_sanitizer
from .report_narrative import build_disagreement_brief, build_report_narrative
from .risk_lock import scan_risk_rule_only
from .security_scan import security_scan
from .risk_review import merge_risk_levels, review_risk_level
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
from .schemas.enums import VALID_CASE_TYPES
from .schemas.report import RiskLockProvenance

# 1.2 §3 rubric weights for bundle score_total derivation from sub_scores
_DIMENSION_WEIGHTS: dict[str, float] = {
    "instruction_following": 0.40,
    "output_compliance": 0.30,
    "business_resolution": 0.30,
}

_PROMPT_SKILL_EXCERPT_MAX = 1500


def _dimension_score_from_sub_scores(sub_scores: dict, key: str) -> float | None:
    entry = sub_scores.get(key) if isinstance(sub_scores, dict) else None
    if isinstance(entry, dict) and entry.get("score") is not None:
        return float(entry["score"])
    return None


def dimension_scores_from_sub_scores(sub_scores: dict) -> DimensionScores:
    """Map provider sub_scores dict to DimensionScores (public for tests)."""
    return DimensionScores(
        instruction_following=_dimension_score_from_sub_scores(sub_scores, "instruction_following"),
        output_compliance=_dimension_score_from_sub_scores(sub_scores, "output_compliance"),
        business_resolution=_dimension_score_from_sub_scores(sub_scores, "business_resolution"),
    )


class EvaluationEngine:
    def __init__(self, repo, ds_provider, wb_provider, sandbox=None):
        self.repo = repo
        self.ds = ds_provider
        self.wb = wb_provider
        self.sandbox = sandbox
        self._agg = AggregateStage()
        self._dec = DecisionStage()
        self._dsl = DslEngine()
        self._workflow_timeout: float = float(workflow_timeout_seconds(RiskLevel.low))
        self._case_judge_sem = asyncio.Semaphore(CASE_JUDGE_CONCURRENCY)

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
            self._save_timeout(
                run_id,
                skill_bundle_path,
                bundle_state,
                evaluation_mode,
            )

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
        t_level0 = time.monotonic()
        repo.update_status(run_id, RunStatus.level0_checking.value)
        repo.append_stage(run_id, "level0_checking")
        bundle = ingest_bundle(skill_bundle_path)

        # Compute case type coverage for transparency (W3-5)
        type_coverage: dict[str, int] = {}
        for _case in bundle.get("eval_cases", []):
            _t = _case.get("type", "")
            if _t in VALID_CASE_TYPES:
                type_coverage[_t] = type_coverage.get(_t, 0) + 1

        # ── Phase 1b: Level 0 structure gate ─────────────────────────────────
        # Only validates SKILL.md presence + risk_level parsability.
        # Case count gate (X1) is deferred to post-confirm phase for confirmed
        # bundles; degraded and pre-confirm paths skip it entirely (T1 fix).
        checker = Level0Checker()
        l0_struct = checker.check_structure(bundle)
        if not l0_struct["passed"]:
            self._log_stage_timing(run_id, "level0_checking", t_level0)
            self._save_fail(run_id, bundle, bundle_state, evaluation_mode,
                            l0_struct["reason_codes"], l0_struct["evidence"])
            return
        self._log_stage_timing(run_id, "level0_checking", t_level0)

        # ── Phase 1b+: Security Scan (Level 0.5, W2) ─────────────────────────
        skill_text = bundle.get("skill_md_text", "")
        sec_result = security_scan(skill_text)
        if sec_result.status == "blocked":
            self._save_fail(
                run_id, bundle, bundle_state, evaluation_mode,
                ["SECURITY_BLOCKED"],
                [
                    {"field": f.group_id, "detail": f.finding_type,
                     "matched_text": f.matched_text}
                    for f in sec_result.findings
                ],
            )
            return
        # "warning" or "passed" → carry result through pipeline

        # ── Phase 1c: Risk Lock (C-6: ①+②, ③ TODO 2.1) ──────────────────────
        t_risk = time.monotonic()
        repo.update_status(run_id, RunStatus.risk_locking.value)
        repo.append_stage(run_id, "risk_locking")

        declared_raw = bundle.get("risk_level_declared")
        declared = RiskLevel(declared_raw) if declared_raw else RiskLevel.low
        rule_scanned = scan_risk_rule_only(bundle.get("skill_md_text", ""))
        risk_locked = merge_risk_levels(declared, rule_scanned, None)
        risk_provenance = RiskLockProvenance(
            declared=declared.value,
            rule_scanned=rule_scanned.value,
            ai_reviewed=None,
            locked=risk_locked.value,
            ai_evidence_zh=None,
        )

        def _apply_risk_timeouts(level: RiskLevel) -> None:
            self._workflow_timeout = float(workflow_timeout_seconds(level))
            judge_timeout = (
                PROVIDER_CALL_TIMEOUT_HIGH_RISK_S
                if level == RiskLevel.high
                else PROVIDER_CALL_TIMEOUT_S
            )
            self.ds.timeout = judge_timeout
            self.wb.timeout = judge_timeout

        _apply_risk_timeouts(risk_locked)
        repo.update_status(run_id, RunStatus.risk_locking.value,
                           risk_level_locked=risk_locked.value)
        self._log_stage_timing(run_id, "risk_locking", t_risk)

        # ── C-3: Dual-phase stop / case gate routing ─────────────────────────
        # Pre-confirm (not confirmed, not degraded) → park at awaiting_confirm.
        # Degraded → skip case gate entirely, continue with empty case_exec.
        # Confirmed → run case gate X1; fail immediately if not met.
        is_confirmed = bundle_state == BundleState.confirmed
        is_degraded = evaluation_mode == EvaluationMode.degraded

        if not is_confirmed and not is_degraded:
            self._park_awaiting_confirm(
                run_id, bundle, bundle_state, evaluation_mode, risk_locked,
                security_status=sec_result.status,
                security_findings=[f.__dict__ for f in sec_result.findings],
            )
            return

        if is_confirmed:
            # Post-confirm: enforce case count gate X1
            l0_gate = checker.check_case_gate(bundle)
            if not l0_gate["passed"]:
                self._save_fail(run_id, bundle, bundle_state, evaluation_mode,
                                l0_gate["reason_codes"], l0_gate["evidence"])
                return
        # degraded: case gate intentionally skipped; 0-case bundles produce
        # a completeness-driven WARN via aggregate stage

        # ── Phase 1d: AI risk review Step ③ (DeepSeek) — only on eval path ───
        ai_level, ai_evidence = await review_risk_level(
            bundle.get("skill_md_text", ""), self.ds,
        )
        risk_locked = merge_risk_levels(declared, rule_scanned, ai_level)
        risk_provenance = RiskLockProvenance(
            declared=declared.value,
            rule_scanned=rule_scanned.value,
            ai_reviewed=ai_level.value if ai_level else None,
            locked=risk_locked.value,
            ai_evidence_zh=ai_evidence,
        )
        _apply_risk_timeouts(risk_locked)
        repo.update_status(
            run_id, RunStatus.risk_locking.value,
            risk_level_locked=risk_locked.value,
        )

        # ── Phase 2: Normalize (degraded / minor gaps) ────────────────────────
        repo.update_status(run_id, RunStatus.normalizing.value)
        repo.append_stage(run_id, "normalizing")
        if not is_confirmed:
            gaps_json = self._build_gaps_snapshot(run_id, bundle, bundle_state)
            repo.save_gaps(run_id, gaps_json)

        # ── Phase 3: CaseExec (Level 1 via sample_io / Level 2 via sandbox) ───
        t_case_exec = time.monotonic()
        repo.update_status(run_id, RunStatus.case_executing.value)
        repo.append_stage(run_id, "case_executing")

        level_achieved = "level_1"
        if bundle.get("has_scripts") and self.sandbox is not None:
            level_achieved = "level_2"

        cases = bundle["eval_cases"]
        self._log_stage_timing(run_id, "case_executing", t_case_exec)

        # ── Phase 4: CodeAssert (DSL per case, C-1) ──────────────────────────
        t_code_assert = time.monotonic()
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
        self._log_stage_timing(run_id, "code_asserting", t_code_assert)

        # ── Phase 4+: Output Sanitizer (PII / secret leak, W2) ───────────────
        san_result = run_output_sanitizer(cases, load_sample_io, skill_bundle_path)
        if san_result.status == "leak":
            self._save_fail(
                run_id, bundle, bundle_state, evaluation_mode,
                ["SECURITY_OUTPUT_LEAK"],
                [
                    {"field": f.source, "detail": f.finding_type,
                     "matched_text": f.matched_text}
                    for f in san_result.findings
                ],
            )
            return

        # ── Phase 5: Model Judging (T7: Semaphore-limited parallel cases) ────
        t_model_judge = time.monotonic()
        repo.update_status(run_id, RunStatus.model_judging.value)
        repo.append_stage(run_id, "model_judging")

        case_vote_lists = await asyncio.gather(
            *[
                self._judge_case(
                    run_id, case, bundle, bundle_state, evaluation_mode,
                )
                for case in cases
            ]
        )
        all_votes: list[dict] = []
        for votes in case_vote_lists:
            all_votes.extend(votes)
        self._log_stage_timing(run_id, "model_judging", t_model_judge)

        repo.save_votes(run_id, all_votes)

        if cases and not all_votes:
            provider_errors = self.repo.get_provider_errors(run_id)
            self._save_provider_failure(
                run_id,
                bundle,
                bundle_state,
                evaluation_mode,
                risk_locked,
                level_achieved,
                provider_errors,
            )
            return

        # ── Phase 6: Aggregate ────────────────────────────────────────────────
        t_aggregate = time.monotonic()
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
        warn_codes = self._dec.warn_reason_codes(dec_ctx)
        human_required = self._dec.requires_human_review(dec_ctx, review_status)

        if agg.get("redline_model_disagreement"):
            human_required = True
            if review_status == "pass":
                review_status = "warn"

        all_reason_codes = agg["reason_codes"] + warn_codes
        if human_required:
            repo.set_human_review_required(run_id, True, all_reason_codes)
        self._log_stage_timing(run_id, "aggregating", t_aggregate)

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
                prompt_version=v.get("prompt_version", "review-agent-v0.3"),
                case_id=v["case_id"],
                dimension_scores=dimension_scores_from_sub_scores(
                    v.get("dimension_scores") or {},
                ),
                score_total=v["score_total"],
                suggested_review_status=v.get("suggested_review_status", "warn"),
                confidence=v.get("confidence", "medium"),
                evidence_refs=v.get("evidence_refs", []),
                feedback=v.get("feedback", ""),
                latency_ms=v.get("latency_ms", 0),
            )
            for v in all_votes
        ]

        provider_summary = build_provider_summary(all_votes, agg)

        narrative = build_report_narrative({
            "review_status": review_status,
            "reason_codes": all_reason_codes,
            "required_actions": bundle.get("required_actions") or [],
            "score_total": agg["score_total"],
        })
        disagreement_brief = build_disagreement_brief(
            provider_summary, agg, all_votes,
        )

        # ── Phase 5.5: Skill Summary (non-blocking LLM synthesis) ─────────────
        skill_summary = await self._generate_skill_summary(
            bundle=bundle,
            all_votes=all_votes,
            completeness_score=completeness_score,
            agg=agg,
            review_status=review_status,
        )

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
            reason_codes=all_reason_codes,
            model_votes=model_votes_obj,
            provider_summary=provider_summary,
            skill_summary=skill_summary,
            narrative=narrative,
            disagreement_brief=disagreement_brief,
            risk_lock_provenance=risk_provenance,
            security_status=sec_result.status,
            security_findings=[f.__dict__ for f in sec_result.findings],
            output_sanitizer_status=san_result.status,
            output_sanitizer_findings=[f.__dict__ for f in san_result.findings],
            case_type_coverage=type_coverage,
            human_review=HumanReview(
                required=human_required,
                trigger_codes=all_reason_codes if human_required else [],
            ),
            rubric_version="v1.2",
            prompt_version="review-agent-v0.3",
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

    def _log_stage_timing(self, run_id: str, stage: str, started: float) -> None:
        ms = int((time.monotonic() - started) * 1000)
        self.repo.log_event(run_id, "stage_timing", {"stage": stage, "ms": ms})

    async def _judge_case(
        self,
        run_id: str,
        case: dict,
        bundle: dict,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
    ) -> list[dict]:
        """Judge one case under shared Semaphore(3); DS+Gemini in parallel."""
        async with self._case_judge_sem:
            case_id = case.get("id", "?")
            t_case = time.monotonic()
            prompt = self._build_prompt(case, bundle, bundle_state, evaluation_mode)
            ds_raw, wb_raw = await asyncio.gather(
                self.ds.judge(prompt),
                self.wb.judge(prompt),
                return_exceptions=True,
            )
            case_ms = int((time.monotonic() - t_case) * 1000)
            self.repo.log_event(
                run_id,
                "stage_timing",
                {"stage": "case_judge", "case_id": case_id, "ms": case_ms},
            )

            votes: list[dict] = []
            for provider_name, raw in [("deepseek", ds_raw), ("gemini", wb_raw)]:
                if isinstance(raw, Exception):
                    self.repo.log_event(run_id, "provider_error", {
                        "provider": provider_name,
                        "case_id": case_id,
                        "error": str(raw),
                    })
                    continue
                score = self._extract_score(raw)
                status = "pass" if score >= 70 else "fail"
                votes.append({
                    "model": provider_name,
                    "model_version": "unknown",
                    "prompt_version": "review-agent-v0.4",
                    "case_id": case_id,
                    "case_type": case.get("type", "happy_path"),
                    "dimension_scores": raw.get("sub_scores", {}),
                    "score_total": score,
                    "suggested_review_status": status,
                    "confidence": raw.get("confidence", "medium"),
                    "evidence_refs": [],
                    "feedback": raw.get("dimension_notes", ""),
                    "latency_ms": case_ms,
                })
            return votes

    def _save_fail(
        self,
        run_id: str,
        bundle: dict,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
        reason_codes: list[str],
        evidence: list[dict],
        *,
        risk_level_locked: RiskLevel | None = None,
    ) -> None:
        run = self.repo.get_run(run_id)
        locked = risk_level_locked
        if locked is None and run and run.get("risk_level_locked"):
            locked = RiskLevel(run["risk_level_locked"])

        report = EvaluationReport(
            run_id=run_id,
            skill_id=bundle.get("skill_id", "?"),
            skill_bundle_path=bundle.get("bundle_path", "?"),
            bundle_state=bundle_state,
            evaluation_mode=evaluation_mode,
            orchestration_mode=self._infer_mode(
                bundle_state, evaluation_mode,
                bundle_state == BundleState.confirmed,
            ),
            status=RunStatus.failed,
            review_status="fail",
            risk_level_locked=locked,
            score_total=run.get("score_total") if run else None,
            score_total_source="not_applicable",
            completeness_score=self._calc_completeness(bundle),
            reason_codes=reason_codes,
            evidence=evidence,
            stage_progress=self.repo.get_stage_progress(run_id),
            rubric_version="v1.2",
            prompt_version="review-agent-v0.3",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        self.repo.save_report(run_id, report)
        self.repo.update_status(
            run_id, RunStatus.failed.value,
            review_status="fail",
            reason_codes=reason_codes,
        )
        self._write_report_file(run_id, report)

    def _save_provider_failure(
        self,
        run_id: str,
        bundle: dict,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
        risk_locked: RiskLevel,
        level_achieved: str,
        provider_errors: list[dict],
    ) -> None:
        """All LLM judge calls failed — fail fast with visible provider_errors."""
        reason_codes = ["EVAL_PROVIDER_UNAVAILABLE"]
        report = EvaluationReport(
            run_id=run_id,
            skill_id=bundle["skill_id"],
            skill_bundle_path=bundle.get("bundle_path", "?"),
            bundle_state=bundle_state,
            evaluation_mode=evaluation_mode,
            orchestration_mode=self._infer_mode(
                bundle_state, evaluation_mode,
                bundle_state == BundleState.confirmed,
            ),
            status=RunStatus.failed,
            review_status="fail",
            risk_level_locked=risk_locked,
            level_achieved=level_achieved,
            score_total=None,
            score_total_source="not_applicable",
            completeness_score=self._calc_completeness(bundle),
            reason_codes=reason_codes,
            evidence=[{"kind": "provider_error", **e} for e in provider_errors[:20]],
            stage_progress=self.repo.get_stage_progress(run_id),
            provider_summary=None,
            human_review=HumanReview(required=False),
            error_detail=(
                "双模型评审全部失败（超时或 API 错误）。请检查网络/密钥后重试；"
                "high-risk 包已自动使用 90s 单 call 超时。"
            ),
            rubric_version="v1.2",
            prompt_version="review-agent-v0.4",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        self.repo.save_report(run_id, report)
        self.repo.update_status(
            run_id, RunStatus.failed.value,
            review_status="fail",
            reason_codes=reason_codes,
        )
        self._write_report_file(run_id, report)

    def _park_awaiting_confirm(
        self,
        run_id: str,
        bundle: dict,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
        risk_locked: RiskLevel,
        *,
        security_status: str | None = None,
        security_findings: list[dict] | None = None,
    ) -> None:
        """T4: persist awaiting_confirm with lightweight self-contained report."""
        self.repo.update_status(run_id, RunStatus.awaiting_confirm.value)
        self.repo.append_stage(run_id, "awaiting_confirm")

        gaps_json = self._build_gaps_snapshot(run_id, bundle, bundle_state)
        self.repo.save_gaps(run_id, gaps_json)

        report = EvaluationReport(
            run_id=run_id,
            skill_id=bundle["skill_id"],
            skill_bundle_path=bundle.get("bundle_path", "?"),
            bundle_state=bundle_state,
            evaluation_mode=evaluation_mode,
            orchestration_mode=self._infer_mode(
                bundle_state, evaluation_mode, False,
            ),
            status=RunStatus.awaiting_confirm,
            review_status=None,
            risk_level_locked=risk_locked,
            score_total=None,
            score_total_source="not_applicable",
            completeness_score=self._calc_completeness(bundle),
            reason_codes=[],
            gaps=gaps_json["gaps"],
            required_actions=gaps_json["required_actions"],
            stage_progress=self.repo.get_stage_progress(run_id),
            security_status=security_status,
            security_findings=security_findings or [],
            rubric_version="v1.2",
            prompt_version="review-agent-v0.3",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        self.repo.save_report(run_id, report)
        self._write_report_file(run_id, report)

    def _save_timeout(
        self,
        run_id: str,
        skill_bundle_path: str,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
    ) -> None:
        """T4: workflow timeout — failed report with stage_progress preserved."""
        self.repo.log_event(
            run_id, "eval_workflow_timeout",
            {"timeout_s": self._workflow_timeout},
        )

        run = self.repo.get_run(run_id)
        bundle: dict = {
            "skill_id": run.get("skill_id", "?") if run else "?",
            "bundle_path": skill_bundle_path,
            "skill_meta": {},
        }
        try:
            bundle = ingest_bundle(skill_bundle_path)
        except Exception:
            pass

        locked: RiskLevel | None = None
        if run and run.get("risk_level_locked"):
            locked = RiskLevel(run["risk_level_locked"])

        reason_codes = ["EVAL_WORKFLOW_TIMEOUT"]
        report = EvaluationReport(
            run_id=run_id,
            skill_id=bundle.get("skill_id", "?"),
            skill_bundle_path=skill_bundle_path,
            bundle_state=bundle_state,
            evaluation_mode=evaluation_mode,
            orchestration_mode=self._infer_mode(
                bundle_state, evaluation_mode,
                bundle_state == BundleState.confirmed,
            ),
            status=RunStatus.failed,
            review_status="fail",
            risk_level_locked=locked,
            score_total=run.get("score_total") if run else None,
            score_total_source=(
                run.get("score_total_source") if run else "not_applicable"
            ),
            completeness_score=self._calc_completeness(bundle),
            reason_codes=reason_codes,
            stage_progress=self.repo.get_stage_progress(run_id),
            error_detail=f"Workflow exceeded {self._workflow_timeout}s timeout",
            rubric_version="v1.2",
            prompt_version="review-agent-v0.3",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        self.repo.save_report(run_id, report)
        self.repo.update_status(
            run_id, RunStatus.failed.value,
            review_status="fail",
            reason_codes=reason_codes,
        )
        self._write_report_file(run_id, report)

    async def _generate_skill_summary(
        self,
        bundle: dict,
        all_votes: list[dict],
        completeness_score: float,
        agg: dict,
        review_status: str,
    ) -> dict | None:
        """Phase 5.5: call wb_provider (Gemini) to synthesise a skill-level quality report.

        Non-blocking — any exception returns None silently; the main pipeline is not affected.
        """
        if not all_votes:
            return None

        skill_excerpt = (bundle.get("skill_md_text") or "").strip()[:800]

        # Compact per-case summary for the synthesis prompt
        by_case: dict[str, dict] = {}
        for v in all_votes:
            cid = v["case_id"]
            by_case.setdefault(cid, {"deepseek": None, "gemini": None})[v["model"]] = v

        case_lines: list[str] = []
        for cid, pair in by_case.items():
            ds = pair.get("deepseek") or {}
            gm = pair.get("gemini") or {}
            ds_dim = ds.get("dimension_scores") or {}
            gm_dim = gm.get("dimension_scores") or {}
            line = (
                f"- {cid}: DS总分={ds.get('score_total')}"
                f" [IF={ds_dim.get('instruction_following')} OC={ds_dim.get('output_compliance')} BR={ds_dim.get('business_resolution')}]"
                f" 反馈={str(ds.get('feedback',''))[:120]}  ||  "
                f"GM总分={gm.get('score_total')}"
                f" [IF={gm_dim.get('instruction_following')} OC={gm_dim.get('output_compliance')} BR={gm_dim.get('business_resolution')}]"
                f" 反馈={str(gm.get('feedback',''))[:120]}"
            )
            case_lines.append(line)

        prompt = (
            "你是 SkillHub 质量分析师。根据以下双模型 per-case 评审数据，"
            f"为技能 {bundle['skill_id']} 出具一份质量诊断摘要，供人工专家参考。\n"
            f"评审结论：{review_status} | 完整度分：{completeness_score:.0f}/100"
            f" | DS包级：{agg.get('ds_score')} | Gemini包级：{agg.get('wb_score')}\n"
            "\n【技能正文摘录】\n"
            f"{skill_excerpt or '(无)'}\n"
            "\n【per-case 双模型评分与反馈】\n"
            + "\n".join(case_lines) + "\n"
            "\n请输出合法 JSON（禁止 markdown 围栏）："
            "{\n"
            '  "overall_verdict": "<1句话总结，不超过20字>",\n'
            '  "strengths": ["<优势，不超过15字>", "<优势，不超过15字>"],\n'
            '  "weaknesses": ["<不足，不超过15字>", "<不足，不超过15字>"],\n'
            '  "dimension_notes": {'
            '"instruction_following": "<该维度总体表现>", '
            '"output_compliance": "<总体表现>", '
            '"business_resolution": "<总体表现>"},\n'
            '  "recommendation": "<给作者或专家的1–2句建议>"\n'
            "}"
        )

        try:
            raw = await self.wb.judge(prompt)
            if isinstance(raw, dict) and "overall_verdict" in raw:
                return raw
            return None
        except Exception:
            return None

    def _build_gaps_snapshot(
        self,
        run_id: str,
        bundle: dict,
        bundle_state: BundleState,
    ) -> dict:
        """Structured gaps snapshot for awaiting_confirm / degraded paths."""
        skill_id = bundle["skill_id"]
        confirmed = frozenset(self.repo.get_confirmations(skill_id).keys())
        scanned = scan_gaps(
            bundle,
            bundle_state,
            confirmed_field_paths=confirmed,
        )
        return {
            "skill_id": skill_id,
            "run_id": run_id,
            "gaps": scanned["gaps"],
            "required_actions": scanned["required_actions"],
        }

    def _build_prompt(
        self,
        case: dict,
        bundle: dict,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
    ) -> str:
        skill_excerpt = (bundle.get("skill_md_text") or "").strip()
        if len(skill_excerpt) > _PROMPT_SKILL_EXCERPT_MAX:
            skill_excerpt = skill_excerpt[:_PROMPT_SKILL_EXCERPT_MAX] + "\n…(truncated)"

        case_type = case.get("type", "happy_path")
        case_type_hint = ""
        if case_type in ("refusal_case", "adversarial_case"):
            case_type_hint = (
                f"\n【红线 case 评分口径 · {case_type}】"
                "仅评估 SKILL.md 是否明确定义拒答/边界/ forbidden 场景与合规话术；"
                "勿假设已有一次 Agent 执行输出。"
                "文档边界充分→各维 80+；边界缺失或自相矛盾→各维低于 60。"
                "DeepSeek 与 Gemini 须采用同一口径。\n"
            )
        elif case_type == "edge_case":
            case_type_hint = (
                "\n【edge_case】允许部分信息缺口，但须在 dimension_notes 写明缺口。\n"
            )

        return (
            "你是 SkillHub 质量评审员。仅评估本 case，不做最终 pass/fail 裁决。\n"
            f"skill_id: {bundle['skill_id']}\n"
            f"case_id: {case.get('id', '?')}\n"
            f"case_type: {case_type}\n"
            f"{case_type_hint}"
            f"bundle_state: {bundle_state}\n"
            f"evaluation_mode: {evaluation_mode}\n"
            f"user_intent: {case.get('user_intent', '')}\n"
            f"rubric_version: v1.2\n"
            f"prompt_version: review-agent-v0.4\n"
            "\n【技能正文摘录】\n"
            f"{skill_excerpt or '(无 SKILL.md 正文)'}\n"
            "\n【评分规则】根据本 case 与技能正文真实评估，给出 0–100 整数分。"
            "禁止照抄下方格式示例中的占位符或任何固定数值。\n"
            "- 90–100：完全满足，证据充分\n"
            "- 80–89：基本满足，有小缺口\n"
            "- 60–79：部分满足，有明显缺陷\n"
            "- 0–59：严重不足\n"
            "\n【三维子项】instruction_following（指令遵循 40%）、"
            "output_compliance（输出合规 30%）、"
            "business_resolution（业务解决 30%）。\n"
            "\n请用简洁中文填写所有 reason、dimension_notes 字段，每项不超过 30 字，禁止技术术语。\n"
            "\n【输出格式】仅输出合法 JSON，勿 markdown 围栏。"
            "score/pass/reason 须反映真实评估；<...> 为待填占位，勿原样输出：\n"
            '{"sub_scores":{'
            '"instruction_following":{"score":<integer 0-100>,"pass":<bool>,'
            '"reason":"<中文，≤30字，说明模型做到了什么或未做到什么>","evidence_refs":[]},'
            '"output_compliance":{"score":<integer 0-100>,"pass":<bool>,'
            '"reason":"<中文，≤30字，说明模型做到了什么或未做到什么>","evidence_refs":[]},'
            '"business_resolution":{"score":<integer 0-100>,"pass":<bool>,'
            '"reason":"<中文，≤30字，说明模型做到了什么或未做到什么>","evidence_refs":[]}},'
            '"confidence":"<low|medium|high>",'
            '"dimension_notes":"<中文，≤30字，总结本用例的核心表现>"}'
        )

    def _extract_score(self, raw: dict) -> float:
        """Weighted 40/30/30 on rubric dimensions; fallback to mean of all sub_scores."""
        sub_scores = raw.get("sub_scores", {})
        if not isinstance(sub_scores, dict):
            return 70.0

        weighted = 0.0
        weight_sum = 0.0
        for key, weight in _DIMENSION_WEIGHTS.items():
            entry = sub_scores.get(key)
            if isinstance(entry, dict) and entry.get("score") is not None:
                weighted += float(entry["score"]) * weight
                weight_sum += weight

        if weight_sum > 0:
            return round(weighted / weight_sum, 1)

        scores = [
            float(v["score"])
            for v in sub_scores.values()
            if isinstance(v, dict) and v.get("score") is not None
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
