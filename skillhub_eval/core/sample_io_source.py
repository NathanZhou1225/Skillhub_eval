"""Sample I/O execution source — wraps ingest.load_sample_io."""

from __future__ import annotations

from .ingest import load_sample_io
from .schemas.report import ExecResult


class SampleIoSource:
    """Read author-provided sample_io/{case_id}.json as actual_output."""

    def get_actual_output(
        self,
        bundle_path: str,
        case_id: str,
        *,
        case: dict | None = None,
        bundle: dict | None = None,
        ctx: dict | None = None,
    ) -> ExecResult:
        actual = load_sample_io(bundle_path, case_id)
        return ExecResult(
            actual_output=actual,
            source="sample_io",
            confidence="high",
            status="ok",
            level="level_1",
        )
