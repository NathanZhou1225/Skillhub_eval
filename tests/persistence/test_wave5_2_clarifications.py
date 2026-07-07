"""Wave 5.2 Task 1 — clarifications_json + schema v5."""

import sqlite3

from skillhub_eval.persistence.sqlite import SqliteRepository


def test_init_db_migration_to_v5_adds_clarifications_json(tmp_path):
    db_path = str(tmp_path / "wave5_2_v5.db")
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
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("PRAGMA user_version = 4")

    repo = SqliteRepository(db_path)
    repo.init_db()
    repo.init_db()

    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info('conversations')").fetchall()
        }
        version = conn.execute("PRAGMA user_version").fetchone()[0]

    assert "clarifications_json" in columns
    assert version == SqliteRepository.SCHEMA_VERSION


def test_get_clarifications_returns_none_when_unset(tmp_path):
    repo = SqliteRepository(str(tmp_path / "unset.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")

    assert repo.get_clarifications(conv_id) is None


def test_merge_clarifications_roundtrip(tmp_path):
    repo = SqliteRepository(str(tmp_path / "merge.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")

    assert repo.get_clarifications(conv_id) is None

    repo.merge_clarifications(conv_id, {"field_a": "value_a"})
    assert repo.get_clarifications(conv_id) == {"field_a": "value_a"}

    repo.merge_clarifications(conv_id, {"field_b": "value_b", "field_a": "overridden"})
    assert repo.get_clarifications(conv_id) == {
        "field_a": "overridden",
        "field_b": "value_b",
    }
