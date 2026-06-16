"""Wave 5.3 Task 4 — plan_enrichment_json schema v6."""

import sqlite3

from skillhub_eval.persistence.sqlite import SqliteRepository


def test_init_db_migration_to_v6_adds_plan_enrichment_json(tmp_path):
    db_path = str(tmp_path / "wave5_3_v6.db")
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
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("PRAGMA user_version = 5")

    repo = SqliteRepository(db_path)
    repo.init_db()
    repo.init_db()

    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info('conversations')").fetchall()
        }
        version = conn.execute("PRAGMA user_version").fetchone()[0]

    assert "plan_enrichment_json" in columns
    assert version == 8


def test_plan_enrichment_roundtrip(tmp_path):
    repo = SqliteRepository(str(tmp_path / "enrich.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")

    assert repo.get_plan_enrichment(conv_id) is None

    snapshot = {"skill_id": "skill.test", "rows": [{"type": "happy_path"}]}
    repo.set_plan_enrichment(conv_id, snapshot)
    assert repo.get_plan_enrichment(conv_id) == snapshot
