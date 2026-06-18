"""Wave 5.4 — judge_traces schema v7."""

import json
import sqlite3

from skillhub_eval.persistence.sqlite import SqliteRepository


def test_init_db_migration_to_v7_creates_judge_traces(tmp_path):
    db_path = str(tmp_path / "v7.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE conversations (
                conversation_id TEXT PRIMARY KEY,
                skill_id TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                active_run_id TEXT,
                auto_run_count INTEGER NOT NULL DEFAULT 0,
                auto_confirmed INTEGER NOT NULL DEFAULT 0,
                max_auto_runs INTEGER NOT NULL DEFAULT 5,
                source_path TEXT,
                pending_patch_json TEXT,
                clarifications_json TEXT,
                plan_enrichment_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("PRAGMA user_version = 6")

    repo = SqliteRepository(db_path)
    repo.init_db()
    repo.init_db()

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        table_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='judge_traces'"
        ).fetchone()[0]

    assert "judge_traces" in tables
    assert version == 10
    assert "UNIQUE" in table_sql


def test_judge_trace_roundtrip_and_has_flag(tmp_path):
    repo = SqliteRepository(str(tmp_path / "trace.db"))
    repo.init_db()
    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path="/tmp/bundle",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    assert repo.has_judge_traces(run_id) is False

    repo.save_judge_trace(run_id, "case-1", "prompt text", None)
    assert repo.has_judge_traces(run_id) is True

    rows = repo.get_judge_traces(run_id)
    assert len(rows) == 1
    assert rows[0]["case_id"] == "case-1"
    assert rows[0]["prompt_text"] == "prompt text"
    assert rows[0]["divergence_json"] is None

    div = {"gap": 20.0, "synthesis_zh": "test", "degraded": False}
    repo.update_judge_trace_divergence(run_id, "case-1", div)
    rows = repo.get_judge_traces(run_id)
    assert rows[0]["divergence_json"] == div


def test_judge_trace_upsert_unique_run_case(tmp_path):
    repo = SqliteRepository(str(tmp_path / "upsert.db"))
    repo.init_db()
    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path="/tmp/bundle",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    repo.save_judge_trace(run_id, "case-1", "prompt v1", None)
    repo.save_judge_trace(run_id, "case-1", "prompt v2", None)
    rows = repo.get_judge_traces(run_id)
    assert len(rows) == 1
    assert rows[0]["prompt_text"] == "prompt v2"
