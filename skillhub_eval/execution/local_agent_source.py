"""Drive local CLI agents and return ExecResult for the evaluation engine."""

from __future__ import annotations

import threading
import time
from typing import Any

from skillhub_eval.core.output_sanitizer import sanitize_output
from skillhub_eval.core.schemas.report import ExecResult, RunOutcome
from skillhub_eval.core.sample_io_source import SampleIoSource
from skillhub_eval.execution.consent import has_exec_consent
from skillhub_eval.execution.evidence import verify_entrypoint_evidence
from skillhub_eval.execution.harness_prompt import build_harness_prompt
from skillhub_eval.execution.profile import HardenedProfile, is_redline_case
from skillhub_eval.execution.runner import AgentAdapter, LocalAgentRunner
from skillhub_eval.execution.stream_parser import collect_actual_output
from skillhub_eval.execution.workspace import PerRunWorkspace
from skillhub_eval.settings import settings

_RATE_LIMIT_MARKERS = ("rate limit", "429", "too many requests")


class LocalAgentSource:
    """Run a local CLI agent per case; parse stream-json for actual_output."""

    _sem_lock = threading.Lock()
    _sem: threading.Semaphore | None = None
    _sem_size: int = 0

    def __init__(
        self,
        *,
        runner: LocalAgentRunner | None = None,
        workspace: PerRunWorkspace | None = None,
        adapter: AgentAdapter | None = None,
        concurrency: int | None = None,
        timeout_s: float = 300.0,
    ):
        self._runner = runner or LocalAgentRunner()
        self._workspace = workspace or PerRunWorkspace()
        self._adapter = adapter
        self._concurrency = concurrency if concurrency is not None else _default_concurrency()
        self._timeout_s = timeout_s
        self._fallback = SampleIoSource()

    def get_actual_output(
        self,
        bundle_path: str,
        case_id: str,
        *,
        case: dict | None = None,
        bundle: dict | None = None,
        ctx: dict | None = None,
    ) -> ExecResult:
        case = case or {}
        bundle = bundle or {}
        skill_id = str(bundle.get("skill_id") or "")
        if not has_exec_consent(skill_id):
            return self._incomplete("consent_required")

        from skillhub_eval.execution.preferences import get_exec_agent

        adapter = self._adapter or _resolve_adapter(get_exec_agent())
        if adapter is None or not adapter.detect():
            return self._incomplete("agent_unavailable")

        if is_redline_case(case):
            degrade = HardenedProfile.redline_degrade_reason(adapter)
            if degrade:
                return self._incomplete(degrade)

        sem = self._get_semaphore()
        with sem:
            return self._run_with_retry(bundle_path, case_id, case, bundle, adapter)

    def _run_with_retry(
        self,
        bundle_path: str,
        case_id: str,
        case: dict,
        bundle: dict,
        adapter: AgentAdapter,
    ) -> ExecResult:
        outcome = self._execute_once(bundle_path, case_id, case, bundle, adapter)
        if self._is_rate_limited(outcome):
            time.sleep(1.0)
            outcome = self._execute_once(bundle_path, case_id, case, bundle, adapter)
        return self._outcome_to_exec_result(outcome, case, bundle, case_id)

    def _execute_once(
        self,
        bundle_path: str,
        case_id: str,
        case: dict,
        bundle: dict,
        adapter: AgentAdapter,
    ) -> RunOutcome:
        run_dir = self._workspace.acquire(bundle_path, case_id)
        try:
            prompt = build_harness_prompt(case, bundle)
            hardened = HardenedProfile.use_hardened(adapter, case)
            return self._runner.run(
                adapter,
                prompt,
                cwd=str(run_dir),
                timeout_s=self._timeout_s,
                hardened=hardened,
            )
        finally:
            self._workspace.release(run_dir)

    def _outcome_to_exec_result(
        self,
        outcome: RunOutcome,
        case: dict,
        bundle: dict,
        case_id: str,
    ) -> ExecResult:
        if not self._runner.is_run_complete(outcome):
            return self._incomplete("run_incomplete")

        parsed = outcome.parsed_stream
        assert parsed is not None
        actual = collect_actual_output(parsed)

        if bundle.get("has_scripts") and bundle.get("entrypoint"):
            if not verify_entrypoint_evidence(parsed.tool_results, bundle["entrypoint"]):
                return self._incomplete("missing_entrypoint_evidence")

        if actual and sanitize_output(actual, case_id):
            return self._incomplete("output_leak")

        return ExecResult(
            actual_output=actual or None,
            source="local_agent",
            confidence="high",
            transcript_ref=None,
            usage=parsed.usage,
            status="ok",
            level="level_2" if bundle.get("has_scripts") else "level_1",
        )

    def _incomplete(self, reason: str) -> ExecResult:
        return ExecResult(
            actual_output=None,
            source="local_agent",
            confidence="low",
            status="incomplete",
            level="level_1",
            degrade_reason=reason,
        )

    def _is_rate_limited(self, outcome: RunOutcome) -> bool:
        parsed = outcome.parsed_stream
        text = (parsed.final_text if parsed else "") or ""
        blob = text.lower()
        return any(m in blob for m in _RATE_LIMIT_MARKERS)

    def _get_semaphore(self) -> threading.Semaphore:
        with self._sem_lock:
            if self._sem is None or self._sem_size != self._concurrency:
                self._sem = threading.Semaphore(self._concurrency)
                self._sem_size = self._concurrency
            return self._sem


def _default_concurrency() -> int:
    return max(1, int(getattr(settings, "exec_concurrency", 2) or 2))


def _resolve_adapter(agent_id: str) -> AgentAdapter | None:
    from skillhub_eval.execution.adapters.claude import ClaudeAdapter
    from skillhub_eval.execution.adapters.codex import CodexAdapter
    from skillhub_eval.execution.adapters.cursor_agent import CursorAgentAdapter

    registry: dict[str, Any] = {
        "claude": ClaudeAdapter,
        "codex": CodexAdapter,
        "cursor-agent": CursorAgentAdapter,
        "cursor_agent": CursorAgentAdapter,
    }
    cls = registry.get(agent_id)
    return cls() if cls else None
