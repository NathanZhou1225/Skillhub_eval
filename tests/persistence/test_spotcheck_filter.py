"""W8: spot_check_eligible + execution_source_used persistence and history filter."""

import sqlite3

from skillhub_eval.persistence.sqlite import SqliteRepository

V8_EVALUATION_RUNS_DDL = """
CREATE TABLE evaluation_runs (
    run_id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    skill_bundle_path TEXT NOT NULL,
    bundle_state TEXT NOT NULL,
    evaluation_mode TEXT NOT NULL,
    orchestration_mode TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    risk_level_locked TEXT,
    level_achieved TEXT,
    review_status TEXT,
    score_total REAL,
    score_total_source TEXT,
    completeness_score REAL,
    reason_codes TEXT DEFAULT '[]',
    report_json TEXT,
    human_review_required INTEGER DEFAULT 0,
    human_review_trigger_codes TEXT DEFAULT '[]',
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    conversation_id TEXT,
    superseded_by_run_id TEXT
);
"""


def _seed_run(repo: SqliteRepository, run_id: str, **kwargs) -> None:
    with repo._conn() as conn:
        conn.execute(
            """
            INSERT INTO evaluation_runs (
                run_id, skill_id, skill_bundle_path, bundle_state,
                evaluation_mode, status, created_at,
                spot_check_eligible, execution_source_used, review_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                kwargs.get("skill_id", "s"),
                "/tmp",
                "confirmed",
                "capability_full",
                kwargs.get("status", "completed"),
                repo._now(),
                kwargs.get("spot_check_eligible", 0),
                kwargs.get("execution_source_used"),
                kwargs.get("review_status", "pass"),
            ),
        )


def test_migration_v9_adds_spotcheck_columns(tmp_path):
    db_path = str(tmp_path / "v8.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(V8_EVALUATION_RUNS_DDL)
    conn.execute("PRAGMA user_version = 8")
    conn.commit()
    conn.close()

    repo = SqliteRepository(db_path)
    repo.init_db()
    with sqlite3.connect(db_path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        cols = {row[1] for row in conn.execute("PRAGMA table_info('evaluation_runs')")}
    assert version == 10
    assert "spot_check_eligible" in cols
    assert "execution_source_used" in cols


def test_list_history_filters_spot_check_and_source(tmp_path):
    repo = SqliteRepository(str(tmp_path / "test.db"))
    repo.init_db()
    _seed_run(
        repo, "run-local-pass",
        spot_check_eligible=1,
        execution_source_used="local_agent",
    )
    _seed_run(
        repo, "run-sample",
        spot_check_eligible=0,
        execution_source_used="sample_io",
    )

    spot_only = repo.list_history(spot_check_eligible=True)
    assert [r["run_id"] for r in spot_only] == ["run-local-pass"]

    local_only = repo.list_history(execution_source_used="local_agent")
    assert [r["run_id"] for r in local_only] == ["run-local-pass"]
