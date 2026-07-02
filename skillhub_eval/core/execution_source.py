"""Route per-skill execution_source to LocalAgent or SampleIo sources."""

from __future__ import annotations

from skillhub_eval.core.sample_io_source import SampleIoSource
from skillhub_eval.core.schemas.report import ExecResult
from skillhub_eval.execution.preferences import get_exec_source
from skillhub_eval.execution.local_agent_source import LocalAgentSource
from skillhub_eval.settings import settings


def resolve_execution_source_name(bundle: dict) -> str:
    """Per-skill field overrides env default."""
    return str(
        bundle.get("execution_source")
        or get_exec_source()
        or settings.exec_source
        or "sample_io"
    )


#: The only ExecResult.degrade_reason that still triggers a sample_io
#: substitution. This is a spec'd, deliberate degrade (redline case on an
#: agent without a hardened execution profile) — not an execution failure —
#: so it keeps producing a scored report instead of blocking the run.
_DELIBERATE_DEGRADE_REASONS = frozenset({"redline_no_hardened_profile"})


class RoutingExecutionSource:
    """Primary local execution; sample_io only for non-local mode or spec'd degrades."""

    def __init__(self, bundle: dict | None = None):
        self._bundle = bundle or {}
        self._sample = SampleIoSource()
        self._local = LocalAgentSource()

    def set_local_timeout(self, timeout_s: float | None) -> None:
        self._local.set_timeout_s(timeout_s)

    def get_actual_output(
        self,
        bundle_path: str,
        case_id: str,
        *,
        case: dict | None = None,
        bundle: dict | None = None,
        ctx: dict | None = None,
    ) -> ExecResult:
        bundle = bundle or self._bundle
        mode = resolve_execution_source_name(bundle)
        if mode != "local":
            return self._sample.get_actual_output(
                bundle_path, case_id, case=case, bundle=bundle, ctx=ctx,
            )

        result = self._local.get_actual_output(
            bundle_path, case_id, case=case, bundle=bundle, ctx=ctx,
        )
        if result.status == "ok" and result.actual_output is not None:
            return result
        if result.degrade_reason not in _DELIBERATE_DEGRADE_REASONS:
            # Genuine execution failure (timeout, crash, missing evidence, leak,
            # no consent/agent, ...) — surface it as-is instead of silently
            # laundering it into a "successful" sample_io result.
            return result

        fb = self._sample.get_actual_output(
            bundle_path, case_id, case=case, bundle=bundle, ctx=ctx,
        )
        if fb.actual_output is not None:
            return ExecResult(
                actual_output=fb.actual_output,
                source="sample_io",
                confidence="low",
                status="ok",
                level="level_1",
                degrade_reason=result.degrade_reason,
            )
        return result
