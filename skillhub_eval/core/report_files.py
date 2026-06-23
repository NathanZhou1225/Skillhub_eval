"""Filesystem helpers for persisted evaluation reports."""

from __future__ import annotations

from pathlib import Path

from skillhub_eval.core.schemas.report import EvaluationReport


def write_evaluation_report_file(
    *,
    run_id: str,
    report: EvaluationReport,
    reports_root: str | Path = "data/reports",
) -> Path:
    out_dir = Path(reports_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "evaluation_report.json"
    out_path.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return out_path
