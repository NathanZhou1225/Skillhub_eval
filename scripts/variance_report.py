#!/usr/bin/env python3
"""Export per-case dual-model variance from SQLite (2.3)."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "t8_validation.db"
OUT_DIR = ROOT / "docs" / "runbooks"


def main() -> None:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT r.run_id, r.skill_id, v.case_id, v.model, v.score_total,
               v.dimension_scores_json, v.feedback
        FROM model_votes v
        JOIN evaluation_runs r ON r.run_id = v.run_id
        ORDER BY r.started_at DESC, v.case_id, v.model
        """
    ).fetchall()

    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    out = OUT_DIR / f"variance-{stamp}.md"
    lines = [f"# 方差报告 {stamp}", "", f"数据源：`{db_path}`", "", "| run_id | skill | case | model | score |", "|---|---|---|---|---:|"]
    for row in rows:
        lines.append(
            f"| {row['run_id'][:8]} | {row['skill_id']} | {row['case_id']} | {row['model']} | {row['score_total']} |"
        )
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(rows)} vote rows)")


if __name__ == "__main__":
    main()
