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


class RoutingExecutionSource:
    """Primary local execution with sample_io fallback on failure."""

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
            )
        return result
