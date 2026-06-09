#!/usr/bin/env python3
"""Auto review vs human_review bias table (2.4)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "t8_validation.db"


def main() -> None:
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not db_path.exists():
        print(f"DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT r.run_id, r.skill_id, r.review_status, h.action AS human_action
        FROM human_reviews h
        JOIN evaluation_runs r ON r.run_id = h.run_id
        ORDER BY h.created_at DESC
        """
    ).fetchall()

    print("| run_id | skill | auto_review | human_action |")
    print("|---|---|---|---|")
    for row in rows:
        print(
            f"| {row['run_id'][:8]} | {row['skill_id']} | "
            f"{row['review_status']} | {row['human_action']} |"
        )


if __name__ == "__main__":
    main()
