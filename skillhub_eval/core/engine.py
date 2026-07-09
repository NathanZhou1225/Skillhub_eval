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
import concurrent.futures
import json
import threading
import time
from datetime import UTC, datetime

from .aggregate import AggregateStage
from .assert_.dsl import DslEngine
from .decision import DecisionStage
from .gaps import scan_gaps
from .provider_summary import build_provider_summary
from .execution_source import RoutingExecutionSource
from .ingest import ingest_bundle
from .judge_prompt import build_case_judge_prompt
from .latency import (
    CASE_JUDGE_CONCURRENCY,
    local_agent_case_timeout_seconds,
    local_agent_workflow_timeout_seconds,
    workflow_timeout_seconds,
)
from .level0 import Level0Checker
from .output_sanitizer import run_output_sanitizer
from .report_narrative import build_disagreement_brief, build_report_narrative
from .report_files import write_evaluation_report_file
from .sample_io_source import SampleIoSource
from .skill_summary import build_fallback_skill_summary, parse_skill_summary_response
from .risk_lock import scan_risk_rule_only
from .security_scan import security_scan
from .risk_review import merge_risk_levels, review_risk_level
from .judge_parse import parse_judge_response
from .divergence import synthesize_divergences_for_run
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
from .chat_notifications import on_run_terminal_chat_notifications
from .eval_stage_messages import maybe_append_formal_eval_stage_notice, maybe_append_local_execution_check_notice
from .schemas.enums import VALID_CASE_TYPES
from .schemas.report import RiskLockProvenance, ExecResult
from skillhub_eval.execution.safe_preflight_case import formal_eval_cases
from skillhub_eval.settings import settings

# 1.2 §3 rubric weights for bundle score_total derivation from sub_scores
_DIMENSION_WEIGHTS: dict[str, float] = {
    "instruction_following": 0.40,
    "output_compliance": 0.30,
    "business_resolution": 0.30,
}

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
    def __init__(self, repo, ds_provider, wb_provider, sandbox=None, execution_source=None):
        self.repo = repo
        self.ds = ds_provider
        self.wb = wb_provider
        self.sandbox = sandbox
        self._execution_source = execution_source or SampleIoSource()
        self._execution_source_override = execution_source
        self._case_exec_results: dict[str, ExecResult] = {}
        self._current_bundle: dict = {}
        self._agg = AggregateStage()
        self._dec = DecisionStage()
        self._dsl = DslEngine()
        self._workflow_timeout: float = float(workflow_timeout_seconds(RiskLevel.low))
        self._local_agent_workflow_timeout: float = float(
            local_agent_workflow_timeout_seconds(RiskLevel.low)
        )
        self._local_agent_case_timeout: float = float(
            local_agent_case_timeout_seconds(RiskLevel.low)
        )
        self._case_exec_lock = threading.Lock()
        self._case_judge_sem = asyncio.Semaphore(CASE_JUDGE_CONCURRENCY)

    def _resolve_exec_for_case(
        self,
        bundle_path: str,
        case_id: str,
        case: dict | None = None,
        bundle: dict | None = None,
    ) -> ExecResult:
        with self._case_exec_lock:
            if case_id in self._case_exec_results:
                return self._case_exec_results[case_id]
        started = time.monotonic()
        if self._uses_local_execution(bundle or self._current_bundle):
            self._log_local_agent_case_started(case_id, case)
        result = self._execution_source.get_actual_output(
            bundle_path,
            case_id,
            case=case,
            bundle=bundle or self._current_bundle,
        )
        if result.source == "local_agent" and result.status != "ok":
            self._log_local_agent_failure(case_id, result)
            self._log_local_agent_case_finished(case_id, result, started)
        elif result.source == "local_agent":
            self._log_local_agent_case_finished(case_id, result, started)
        with self._case_exec_lock:
            self._case_exec_results[case_id] = result
        return result

    def _log_local_agent_case_started(self, case_id: str, case: dict | None) -> None:
        run_id = getattr(self, "_current_run_id", None)
        if not run_id:
            return
        self.repo.log_event(run_id, "local_agent_case_started", {
            "case_id": case_id,
            "case_type": (case or {}).get("type"),
        })

    def _log_local_agent_case_finished(
        self,
        case_id: str,
        result: ExecResult,
        started: float,
    ) -> None:
        run_id = getattr(self, "_current_run_id", None)
        if not run_id:
            return
        event_name = (
            "local_agent_case_succeeded"
            if result.status == "ok"
            else "local_agent_case_failed"
        )
        payload = {
            "case_id": case_id,
            "status": result.status,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "degrade_reason": result.degrade_reason,
            "stderr_excerpt": result.stderr_excerpt,
            "agent_label": result.agent_label,
            "model_label": result.model_label,
        }
        self.repo.log_event(run_id, event_name, payload)

    def _log_local_agent_failure(self, case_id: str, result: ExecResult) -> None:
        """Persist the real failure reason so it survives even though the
        run/case is no longer silently masked by a sample_io substitution."""
        from skillhub_eval.execution.failure_taxonomy import runtime_failure_code

        run_id = getattr(self, "_current_run_id", None)
        if not run_id:
            return
        self.repo.log_event(run_id, "local_agent_failure", {
            "case_id": case_id,
            "degrade_reason": result.degrade_reason,
            "runtime_failure_code": runtime_failure_code(result.degrade_reason),
            "stderr_excerpt": result.stderr_excerpt,
        })

    def _get_case_actual_output(
        self,
        bundle_path: str,
        case_id: str,
        *,
        case: dict | None = None,
        bundle: dict | None = None,
    ) -> dict | None:
        """Resolve actual_output for a case via ExecutionSource (default: sample_io)."""
        return self._resolve_exec_for_case(
            bundle_path, case_id, case=case, bundle=bundle,
        ).actual_output

    def _sample_io_loader(self, bundle_path: str, case_id: str) -> dict | None:
        return self._get_case_actual_output(bundle_path, case_id)

    def _compute_level_achieved(self) -> str:
        if any(
            r.level == "level_2" and r.status == "ok"
            for r in self._case_exec_results.values()
        ):
            return "level_2"
        return "level_1"

    def _compute_execution_source_used(self, bundle: dict) -> str:
        if not self._case_exec_results:
            return str(bundle.get("execution_source") or "sample_io")
        sources = {r.source for r in self._case_exec_results.values()}
        if sources == {"local_agent"}:
            return "local_agent"
        if sources == {"sample_io"}:
            return "sample_io"
        return "mixed"

    def _exec_agent_report_fields(self, bundle: dict) -> dict[str, str | None]:
        """Local exec agent/model for report header.

        `exec_agent_*`/`exec_model_*` SHALL only be populated when a case
        genuinely executed via `local_agent` with `status=="ok"` — never
        inferred from the user's mere preference selection (that would claim
        execution that never happened). `exec_requested_*` always reflects
        what the user selected, regardless of whether it actually ran, so the
        UI can distinguish "requested but not executed" from "executed".
        """
        from skillhub_eval.core.execution_source import resolve_execution_source_name

        requested = self._exec_requested_fields()
        if resolve_execution_source_name(bundle) != "local":
            requested = {"exec_requested_agent_label": None, "exec_requested_model_label": None}

        for result in self._case_exec_results.values():
            if result.source == "local_agent" and result.status == "ok" and result.agent_id:
                return {
                    "exec_agent_id": result.agent_id,
                    "exec_agent_label": result.agent_label,
                    "exec_model_id": result.model_id,
                    "exec_model_label": result.model_label,
                    **requested,
                }
        return {
            "exec_agent_id": None,
            "exec_agent_label": None,
            "exec_model_id": None,
            "exec_model_label": None,
            **requested,
        }

    def _exec_requested_fields(self) -> dict[str, str | None]:
        from skillhub_eval.execution.agent_registry import DEFAULT_MODEL_ID, get_agent_def
        from skillhub_eval.execution.preferences import get_exec_agent, get_exec_model

        agent_id = get_exec_agent()
        agent = get_agent_def(agent_id)
        model_id = get_exec_model()
        return {
            "exec_requested_agent_label": agent.label if agent else agent_id,
            "exec_requested_model_label": (
                "默认模型" if model_id == DEFAULT_MODEL_ID else model_id
            ),
        }

    def _local_exec_attempted_results(self) -> list[ExecResult]:
        """Case results counted for the local-exec-health check.

        Excludes cases that deliberately degraded to sample_io for a spec'd
        reason (e.g. redline case on an agent without a hardened profile) —
        those are by-design substitutions, not evidence the agent is broken.
        """
        return [
            r for r in self._case_exec_results.values()
            if r.degrade_reason != "redline_no_hardened_profile"
        ]

    def _local_exec_all_failed(self, bundle: dict) -> bool:
        """True when local execution was requested but every attempted case
        failed — i.e. nothing was genuinely scored via a real local agent run."""
        if not self._uses_local_execution(bundle):
            return False
        attempted = self._local_exec_attempted_results()
        if not attempted:
            return False
        return not any(r.source == "local_agent" and r.status == "ok" for r in attempted)

    def _save_local_exec_blocked(
        self,
        run_id: str,
        bundle: dict,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
    ) -> None:
        """Local execution was requested but produced zero successful cases —
        block the run with the real reasons instead of returning a report
        built on nothing (see local-agent-trial-hardening)."""
        from skillhub_eval.execution.failure_taxonomy import runtime_failure_code

        attempted = self._local_exec_attempted_results()
        unavailable_reasons = {"agent_unavailable", "consent_required"}
        all_unavailable = bool(attempted) and all(
            r.degrade_reason in unavailable_reasons for r in attempted
        )
        reason_code = "LOCAL_EXEC_UNAVAILABLE" if all_unavailable else "LOCAL_EXEC_ALL_CASES_FAILED"
        evidence = [
            {
                "case_id": case_id,
                "degrade_reason": result.degrade_reason,
                "runtime_failure_code": runtime_failure_code(result.degrade_reason),
                "stderr_excerpt": result.stderr_excerpt,
            }
            for case_id, result in self._case_exec_results.items()
            if result.degrade_reason != "redline_no_hardened_profile"
        ]
        self._save_fail(
            run_id, bundle, bundle_state, evaluation_mode, [reason_code], evidence,
        )

    def _compute_spot_check_eligible(
        self,
        review_status: str,
        human_required: bool,
    ) -> bool:
        if review_status != "pass" or human_required:
            return False
        return any(
            r.source == "local_agent" and r.status == "ok"
            for r in self._case_exec_results.values()
        )

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
        self._terminal_run_ids: list[str] = []
        try:
            await self._execute(run_id, skill_bundle_path, bundle_state, evaluation_mode)
        finally:
            for terminal_run_id in self._terminal_run_ids:
                await on_run_terminal_chat_notifications(
                    terminal_run_id,
                    self.repo,
                    self.ds,
                    self.wb,
                )
            self._terminal_run_ids.clear()

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
        self._current_bundle = bundle
        self._current_run_id = run_id
        self._case_exec_results = {}
        if self._execution_source_override is not None:
            self._execution_source = self._execution_source_override
        else:
            self._execution_source = RoutingExecutionSource(bundle)

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
            self._local_agent_workflow_timeout = float(
                local_agent_workflow_timeout_seconds(level)
            )
            self._local_agent_case_timeout = float(
                local_agent_case_timeout_seconds(level)
            )
            if hasattr(self._execution_source, "set_local_timeout"):
                self._execution_source.set_local_timeout(self._local_agent_case_timeout)
            elif hasattr(self._execution_source, "set_timeout_s"):
                self._execution_source.set_timeout_s(self._local_agent_case_timeout)
            from skillhub_eval.core.latency import (
                provider_call_timeout_high_risk_s,
                provider_call_timeout_s,
            )

            judge_timeout = (
                provider_call_timeout_high_risk_s()
                if level == RiskLevel.high
                else provider_call_timeout_s()
            )
            self.ds.timeout = judge_timeout
            self.wb.timeout = judge_timeout

        _apply_risk_timeouts(risk_locked)
        repo.update_status(run_id, RunStatus.risk_locking.value,
                           risk_level_locked=risk_locked.value)
        self._log_stage_timing(run_id, "risk_locking", t_risk)

        # ── C-3: Dual-phase stop / case gate routing ─────────────────────────
        # Degraded (W5.2 GQ12 R2) → readiness-only terminal:
        # run case gate + gaps + completeness, skip heavy eval stages.
        # Pre-confirm (not confirmed, not degraded) → park at awaiting_confirm.
        # Confirmed → run case gate X1; fail immediately if not met.
        is_confirmed = bundle_state == BundleState.confirmed
        is_degraded = evaluation_mode == EvaluationMode.degraded

        if is_degraded:
            l0_gate = checker.check_case_gate(bundle)
            repo.update_status(run_id, RunStatus.normalizing.value)
            repo.append_stage(run_id, "normalizing")
            gaps_json = self._build_gaps_snapshot(run_id, bundle, bundle_state)
            repo.save_gaps(run_id, gaps_json)
            self._save_degraded_readiness(
                run_id=run_id,
                skill_bundle_path=skill_bundle_path,
                bundle=bundle,
                bundle_state=bundle_state,
                evaluation_mode=evaluation_mode,
                risk_locked=risk_locked,
                risk_provenance=risk_provenance,
                l0_gate=l0_gate,
                gaps_json=gaps_json,
                security_status=sec_result.status,
                security_findings=[f.__dict__ for f in sec_result.findings],
                type_coverage=type_coverage,
            )
            return

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
        self._log_provider_usage(
            run_id,
            stage="risk_review",
            provider=self.ds,
            provider_name="deepseek",
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

        # ── Phase 3: CaseExec (local agent or sample_io per ExecutionSource) ───
        t_case_exec = time.monotonic()
        repo.update_status(run_id, RunStatus.case_executing.value)
        repo.append_stage(run_id, "case_executing")
        maybe_append_formal_eval_stage_notice(
            repo,
            run_id,
            "case_executing",
            uses_local_execution=self._uses_local_execution(bundle),
        )
        if self._uses_local_execution(bundle):
            repo.log_event(run_id, "stage_budget", {
                "stage": "case_executing",
                "budget_s": self._local_agent_workflow_timeout,
                "agent_phase": "local_agent",
                "started_at": datetime.now(UTC).isoformat(),
            })

        cases = formal_eval_cases(bundle)
        try:
            if self._uses_local_execution(bundle):
                await asyncio.wait_for(
                    asyncio.to_thread(
                        self._run_case_exec_phase,
                        skill_bundle_path,
                        cases,
                        bundle,
                    ),
                    timeout=self._local_agent_workflow_timeout,
                )
            else:
                self._run_case_exec_phase(skill_bundle_path, cases, bundle)
        except asyncio.TimeoutError:
            self._save_timeout(
                run_id,
                skill_bundle_path,
                bundle_state,
                evaluation_mode,
                timeout_phase="local_agent",
            )
            return
        self._log_local_agent_usage(run_id)
        if self._local_exec_all_failed(bundle):
            self._log_stage_timing(run_id, "case_executing", t_case_exec)
            self._save_local_exec_blocked(run_id, bundle, bundle_state, evaluation_mode)
            return
        level_achieved = self._compute_level_achieved()
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
            actual = self._get_case_actual_output(
                skill_bundle_path,
                case.get("id", ""),
                case=case,
                bundle=bundle,
            )
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
        san_result = run_output_sanitizer(cases, self._sample_io_loader, skill_bundle_path)
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

        # ── Phase 5–7: Model judging + aggregate (judge-phase timeout only) ────
        try:
            await asyncio.wait_for(
                self._judge_and_finalize(
                    run_id=run_id,
                    skill_bundle_path=skill_bundle_path,
                    bundle=bundle,
                    bundle_state=bundle_state,
                    evaluation_mode=evaluation_mode,
                    cases=cases,
                    is_confirmed=is_confirmed,
                    risk_locked=risk_locked,
                    risk_provenance=risk_provenance,
                    sec_result=sec_result,
                    san_result=san_result,
                    type_coverage=type_coverage,
                    all_assertions_passed=all_assertions_passed,
                    redline_fail=redline_fail,
                    level_achieved=level_achieved,
                ),
                timeout=self._workflow_timeout,
            )
        except asyncio.TimeoutError:
            self._save_timeout(
                run_id,
                skill_bundle_path,
                bundle_state,
                evaluation_mode,
                timeout_phase="judge",
            )

    async def _judge_and_finalize(
        self,
        *,
        run_id: str,
        skill_bundle_path: str,
        bundle: dict,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
        cases: list[dict],
        is_confirmed: bool,
        risk_locked: RiskLevel,
        risk_provenance: RiskLockProvenance,
        sec_result,
        san_result,
        type_coverage: dict[str, int],
        all_assertions_passed: bool,
        redline_fail: bool,
        level_achieved: str,
    ) -> None:
        repo = self.repo

        # ── Phase 5: Model Judging (T7: Semaphore-limited parallel cases) ────
        t_model_judge = time.monotonic()
        repo.update_status(run_id, RunStatus.model_judging.value)
        repo.append_stage(run_id, "model_judging")
        maybe_append_formal_eval_stage_notice(
            repo,
            run_id,
            "model_judging",
            uses_local_execution=self._uses_local_execution(bundle),
        )

        judge_cases = self._judgeable_cases(cases, bundle)
        case_vote_lists = await asyncio.gather(
            *[
                self._judge_case(
                    run_id, case, bundle, bundle_state, evaluation_mode,
                )
                for case in judge_cases
            ]
        )
        all_votes: list[dict] = []
        for votes in case_vote_lists:
            all_votes.extend(votes)
        self._log_stage_timing(run_id, "model_judging", t_model_judge)

        repo.save_votes(run_id, all_votes)

        if all_votes:
            t_div = time.monotonic()
            repo.append_stage(run_id, "divergence_synthesis")
            await self._synthesize_divergences(run_id, all_votes)
            self._log_stage_timing(run_id, "divergence_synthesis", t_div)

        if judge_cases and not all_votes:
            provider_errors = self.repo.get_provider_errors(run_id)
            self._save_provider_failure(
                run_id,
                bundle,
                bundle_state,
                evaluation_mode,
                risk_locked,
                self._compute_level_achieved(),
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

        provider_summary = build_provider_summary(
            all_votes,
            agg,
            provider_a_label=getattr(self.ds, "label", "DeepSeek"),
            provider_b_label=getattr(self.wb, "label", "Gemini"),
            exec_results=self._case_exec_results,
        )

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
            run_id=run_id,
            bundle=bundle,
            all_votes=all_votes,
            completeness_score=completeness_score,
            agg=agg,
            review_status=review_status,
        )

        # ── Save report ───────────────────────────────────────────────────────
        execution_source_used = self._compute_execution_source_used(bundle)
        spot_check_eligible = self._compute_spot_check_eligible(
            review_status, human_required,
        )
        level_achieved = self._compute_level_achieved()
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
            spot_check_eligible=spot_check_eligible,
            execution_source_used=execution_source_used,
            **self._exec_agent_report_fields(bundle),
            usage_summary=self._build_usage_summary(run_id),
            human_review=HumanReview(
                required=human_required,
                trigger_codes=all_reason_codes if human_required else [],
            ),
            rubric_version="v1.2",
            prompt_version="review-agent-v0.5",
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
            level_achieved=level_achieved,
            spot_check_eligible=1 if spot_check_eligible else 0,
            execution_source_used=execution_source_used,
        )

        # Persist report JSON to disk
        self._write_report_file(run_id, report)
        self._maybe_append_rich_report(run_id)

    def _uses_local_execution(self, bundle: dict) -> bool:
        from skillhub_eval.core.execution_source import resolve_execution_source_name

        return resolve_execution_source_name(bundle) == "local"

    def _requires_runtime_preflight(self, bundle: dict) -> bool:
        """Legacy helper retained for tests/diagnostics; formal eval no longer gates on this."""
        from skillhub_eval.core.execution_source import resolve_execution_source_name

        return (
            self._execution_source_override is None
            and resolve_execution_source_name(bundle) == "local"
        )

    async def _ensure_valid_runtime_preflight(
        self,
        run_id: str,
        skill_bundle_path: str,
        *,
        locked_risk_level: str | None = None,
    ) -> dict | None:
        """Legacy auto-preflight path. Formal eval must not call this; use the manual preflight API."""
        from skillhub_eval.execution.preferences import get_exec_agent, get_exec_model
        from skillhub_eval.execution.safe_preflight_case import ensure_safe_preflight_case_with_provider

        runner = self._preflight_runner()
        runtime_id = get_exec_agent()
        model_id = get_exec_model()

        cached = runner.check_cached(
            skill_bundle_path,
            runtime_id=runtime_id,
            model_id=model_id,
            locked_risk_level=locked_risk_level,
        )
        if cached is not None and cached.get("status") == "passed":
            return cached

        await ensure_safe_preflight_case_with_provider(
            skill_bundle_path,
            provider=self.ds,
            locked_risk_level=locked_risk_level,
        )

        maybe_append_local_execution_check_notice(self.repo, run_id)
        result = await asyncio.to_thread(
            runner.run,
            skill_bundle_path,
            runtime_id=runtime_id,
            model_id=model_id,
            locked_risk_level=locked_risk_level,
        )
        if result.status != "passed":
            return None

        return runner.check_cached(
            skill_bundle_path,
            runtime_id=runtime_id,
            model_id=model_id,
            locked_risk_level=locked_risk_level,
        )

    def _valid_runtime_preflight(
        self,
        skill_bundle_path: str,
        *,
        locked_risk_level: str | None = None,
    ) -> dict | None:
        """Cache-only check retained for tests and diagnostics."""
        from skillhub_eval.execution.preferences import get_exec_agent, get_exec_model

        runner = self._preflight_runner()
        return runner.check_cached(
            skill_bundle_path,
            runtime_id=get_exec_agent(),
            model_id=get_exec_model(),
            locked_risk_level=locked_risk_level,
        )

    def _runtime_preflight_required_evidence(
        self,
        skill_bundle_path: str,
        locked_risk_level: str | None,
    ) -> dict:
        """Legacy evidence builder for old hard-gate reports; formal eval no longer emits this reason."""
        from skillhub_eval.execution.failure_taxonomy import runtime_failure_code
        from skillhub_eval.execution.preferences import get_exec_agent, get_exec_model
        from skillhub_eval.execution.preflight_runner import PreflightRunner

        runtime_id = get_exec_agent()
        model_id = get_exec_model()
        evidence = {
            "field": "local_runtime_preflight",
            "detail": "本地执行环境检查未通过或尚未完成（诊断信息；正式评估以真实 case 执行为准）。",
            "runtime_id": runtime_id,
            "model_id": model_id,
            "locked_risk_level": locked_risk_level,
        }
        try:
            context = self._preflight_runner()._context(skill_bundle_path, runtime_id, model_id)
        except Exception as exc:
            evidence["diagnosis"] = "context_error"
            evidence["message"] = str(exc)
            return evidence
        latest = self.repo.get_runtime_preflight(
            runtime_id=context["runtime"].runtime_id,
            model_id=context["model_id"],
            skill_fingerprint=context["skill_fingerprint"],
        )
        if latest is None:
            evidence["diagnosis"] = "missing_cache"
            return evidence
        evidence["diagnosis"] = "cache_invalid"
        evidence["cached_status"] = latest.get("status")
        evidence["cached_failure_reason"] = latest.get("failure_reason")
        evidence["cached_runtime_failure_code"] = runtime_failure_code(latest.get("failure_reason"))
        evidence["cached_expires_at"] = latest.get("expires_at")
        evidence["fingerprint_matches"] = latest.get("fingerprint") == context["fingerprint"]
        return evidence

    def _preflight_runner(self):
        from skillhub_eval.execution.preflight_runner import PreflightRunner

        return PreflightRunner(repo=self.repo)

    def _judgeable_cases(self, cases: list[dict], bundle: dict) -> list[dict]:
        """Local-agent failed cases have no actual output, so they are not
        valid inputs for semantic judging or total-score aggregation."""
        if not self._uses_local_execution(bundle):
            return cases
        result: list[dict] = []
        for case in cases:
            case_id = case.get("id", "")
            exec_result = self._case_exec_results.get(case_id)
            if (
                exec_result
                and exec_result.status == "ok"
                and exec_result.actual_output is not None
            ):
                result.append(case)
        return result

    def _run_case_exec_phase(
        self,
        skill_bundle_path: str,
        cases: list[dict],
        bundle: dict,
    ) -> None:
        if not cases:
            return
        max_workers = max(1, int(getattr(settings, "exec_concurrency", 2) or 2))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(
                    self._resolve_exec_for_case,
                    skill_bundle_path,
                    case.get("id", ""),
                    case=case,
                    bundle=bundle,
                )
                for case in cases
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _maybe_append_rich_report(self, run_id: str) -> None:
        run = self.repo.get_run(run_id)
        if not run or not run.get("conversation_id"):
            return
        if not hasattr(self, "_terminal_run_ids"):
            self._terminal_run_ids = []
        self._terminal_run_ids.append(run_id)

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
            self._log_provider_usage(
                run_id,
                stage="model_judging",
                provider=self.ds,
                provider_name="deepseek",
                case_id=case_id,
            )
            self._log_provider_usage(
                run_id,
                stage="model_judging",
                provider=self.wb,
                provider_name="gemini",
                case_id=case_id,
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
                try:
                    parsed = parse_judge_response(raw)
                except (ValueError, json.JSONDecodeError, TypeError) as exc:
                    self.repo.log_event(run_id, "provider_error", {
                        "provider": provider_name,
                        "case_id": case_id,
                        "error": f"parse_judge_response: {exc}",
                    })
                    continue
                score = self._extract_score(parsed)
                status = "pass" if score >= 70 else "fail"
                sub_scores = parsed.get("sub_scores", {})
                votes.append({
                    "model": provider_name,
                    "model_version": "unknown",
                    "prompt_version": "review-agent-v0.5",
                    "case_id": case_id,
                    "case_type": case.get("type", "happy_path"),
                    "dimension_scores": sub_scores,
                    "sub_scores": sub_scores,
                    "score_total": score,
                    "suggested_review_status": status,
                    "confidence": parsed.get("confidence", "medium"),
                    "evidence_refs": [],
                    "feedback": parsed.get("dimension_notes", ""),
                    "latency_ms": case_ms,
                })
            self.repo.save_judge_trace(run_id, case_id, prompt, None)
            return votes

    async def _synthesize_divergences(self, run_id: str, votes: list[dict]) -> None:
        await synthesize_divergences_for_run(
            run_id,
            votes,
            self.repo,
            self.ds,
        )
        self._log_provider_usage(
            run_id,
            stage="divergence_synthesis",
            provider=self.ds,
            provider_name="deepseek",
        )

    def _log_provider_usage(
        self,
        run_id: str,
        *,
        stage: str,
        provider,
        provider_name: str,
        case_id: str | None = None,
    ) -> None:
        usage = getattr(provider, "last_usage", None)
        if not usage:
            return
        self.repo.log_event(run_id, "token_usage", {
            "stage": stage,
            "provider": provider_name,
            "provider_label": getattr(provider, "label", provider_name),
            "model": getattr(provider, "model", None),
            "case_id": case_id,
            "usage": usage,
        })

    def _log_local_agent_usage(self, run_id: str) -> None:
        for case_id, exec_result in self._case_exec_results.items():
            if not exec_result.usage:
                continue
            self.repo.log_event(run_id, "token_usage", {
                "stage": "local_agent",
                "provider_label": exec_result.agent_label,
                "model": exec_result.model_id,
                "case_id": case_id,
                "usage": exec_result.usage,
            })

    def _build_usage_summary(self, run_id: str):
        from skillhub_eval.core.usage import UsageRecord, build_usage_summary

        records = []
        if not hasattr(self.repo, "list_events"):
            return build_usage_summary(records)
        for event in self.repo.list_events(run_id, event_name="token_usage"):
            payload = event.get("payload") or {}
            records.append(
                UsageRecord(
                    stage=str(payload.get("stage") or "unknown"),
                    provider_label=payload.get("provider_label"),
                    model=payload.get("model"),
                    case_id=payload.get("case_id"),
                    usage=payload.get("usage"),
                )
            )
        return build_usage_summary(records)

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
            usage_summary=self._build_usage_summary(run_id),
            **self._exec_agent_report_fields(bundle),
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
        self._maybe_append_rich_report(run_id)

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
            usage_summary=self._build_usage_summary(run_id),
            **self._exec_agent_report_fields(bundle),
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
        self._maybe_append_rich_report(run_id)

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
            usage_summary=self._build_usage_summary(run_id),
            **self._exec_agent_report_fields(bundle),
            rubric_version="v1.2",
            prompt_version="review-agent-v0.3",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        self.repo.save_report(run_id, report)
        self._write_report_file(run_id, report)
        self._maybe_append_rich_report(run_id)

    def _save_degraded_readiness(
        self,
        *,
        run_id: str,
        skill_bundle_path: str,
        bundle: dict,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
        risk_locked: RiskLevel,
        risk_provenance: RiskLockProvenance,
        l0_gate: dict,
        gaps_json: dict,
        security_status: str,
        security_findings: list[dict],
        type_coverage: dict[str, int],
    ) -> None:
        """W5.2 GQ12 R2: persist lightweight readiness terminal payload."""
        reason_codes = list(l0_gate.get("reason_codes") or [])
        completeness_score = self._calc_completeness(bundle)
        report = EvaluationReport(
            run_id=run_id,
            skill_id=bundle["skill_id"],
            skill_bundle_path=skill_bundle_path,
            bundle_state=bundle_state,
            evaluation_mode=evaluation_mode,
            orchestration_mode=self._infer_mode(bundle_state, evaluation_mode, False),
            status=RunStatus.completed,
            review_status="warn",
            risk_level_locked=risk_locked,
            score_total=None,
            score_total_source="not_applicable",
            completeness_score=completeness_score,
            reason_codes=reason_codes,
            evidence=list(l0_gate.get("evidence") or []),
            required_actions=gaps_json.get("required_actions") or [],
            gaps=gaps_json.get("gaps") or [],
            stage_progress=self.repo.get_stage_progress(run_id),
            risk_lock_provenance=risk_provenance,
            security_status=security_status,
            security_findings=security_findings,
            case_type_coverage=type_coverage,
            usage_summary=self._build_usage_summary(run_id),
            **self._exec_agent_report_fields(bundle),
            rubric_version="v1.2",
            prompt_version="review-agent-v0.4",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        self.repo.save_report(run_id, report)
        self.repo.update_status(
            run_id,
            RunStatus.completed.value,
            review_status="warn",
            score_total=None,
            completeness_score=completeness_score,
            reason_codes=reason_codes,
        )
        self._write_report_file(run_id, report)
        self._maybe_append_rich_report(run_id)

    def _save_timeout(
        self,
        run_id: str,
        skill_bundle_path: str,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
        *,
        timeout_phase: str = "judge",
    ) -> None:
        """Workflow timeout — failed report with stage_progress preserved."""
        if timeout_phase == "local_agent":
            timeout_s = self._local_agent_workflow_timeout
            reason_codes = ["EVAL_LOCAL_AGENT_TIMEOUT"]
            error_detail = (
                f"Local agent case execution exceeded {timeout_s}s timeout"
            )
            event_name = "eval_local_agent_timeout"
        else:
            timeout_s = self._workflow_timeout
            reason_codes = ["EVAL_WORKFLOW_TIMEOUT"]
            error_detail = f"Judge workflow exceeded {timeout_s}s timeout"
            event_name = "eval_workflow_timeout"

        self.repo.log_event(
            run_id,
            event_name,
            {"timeout_s": timeout_s, "phase": timeout_phase},
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
            usage_summary=self._build_usage_summary(run_id),
            **self._exec_agent_report_fields(bundle),
            error_detail=error_detail,
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
        self._maybe_append_rich_report(run_id)

    async def _generate_skill_summary(
        self,
        run_id: str,
        bundle: dict,
        all_votes: list[dict],
        completeness_score: float,
        agg: dict,
        review_status: str,
    ) -> dict | None:
        """Phase 5.5: call ds_provider (DeepSeek) to synthesise a skill-level quality report.

        Non-blocking — any exception returns None silently; the main pipeline is not affected.
        Gemini is reserved for per-case dual-model judging only.
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
            f"为技能 {bundle['skill_id']} 出具一份质量诊断摘要，供作者与专家参考。\n"
            "【重要】本次不是 per-case 打分，禁止输出 sub_scores。"
            "无论评审结论是 pass、warn 还是 fail，都必须写出 overall_verdict、"
            "strengths（至少 2 条亮点）、weaknesses 与 recommendation。\n"
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
            raw = await self.ds.judge(prompt)
            self._log_provider_usage(
                run_id,
                stage="skill_summary",
                provider=self.ds,
                provider_name="deepseek",
            )
            parsed = parse_skill_summary_response(raw)
            if parsed:
                return parsed
        except Exception:
            pass

        return build_fallback_skill_summary(
            review_status=review_status,
            completeness_score=completeness_score,
            agg=agg,
            all_votes=all_votes,
        )

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
        return build_case_judge_prompt(
            case=case,
            bundle=bundle,
            bundle_state=bundle_state,
            evaluation_mode=evaluation_mode,
            exec_results=self._case_exec_results,
            actual_output_loader=self._get_case_actual_output,
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
            write_evaluation_report_file(run_id=run_id, report=report)
        except Exception:
            pass  # file write failure must not abort the run
