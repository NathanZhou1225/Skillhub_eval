"""Wave 5.1 Task 1 — pending_patch_json + schema v4."""

import json
import sqlite3

import pytest

from skillhub_eval.persistence.sqlite import SqliteRepository


def test_init_db_migration_to_v4_adds_pending_patch_json(tmp_path):
    db_path = str(tmp_path / "wave5_1_v4.db")
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
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("PRAGMA user_version = 3")

    repo = SqliteRepository(db_path)
    repo.init_db()
    repo.init_db()

    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info('conversations')").fetchall()
        }
        version = conn.execute("PRAGMA user_version").fetchone()[0]

    assert "pending_patch_json" in columns
    assert "clarifications_json" in columns
    assert version == SqliteRepository.SCHEMA_VERSION


def test_pending_patch_roundtrip(tmp_path):
    repo = SqliteRepository(str(tmp_path / "patch.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")

    assert repo.get_pending_patch(conv_id) is None

    patch = {"skill_md_updates": {"description": "updated"}, "eval_cases": []}
    repo.set_pending_patch(conv_id, patch)
    stored = repo.get_pending_patch(conv_id)
    assert stored == patch

    repo.clear_pending_patch(conv_id)
    assert repo.get_pending_patch(conv_id) is None


def test_set_pending_patch_updates_conversation_status(tmp_path):
    repo = SqliteRepository(str(tmp_path / "status.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill.test", source="upload")

    repo.set_pending_patch(conv_id, {"skill_md_updates": {"description": "x"}})
    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["status"] == "awaiting_draft_confirm"
    assert json.loads(conv["pending_patch_json"]) == {
        "skill_md_updates": {"description": "x"}
    }

    repo.clear_pending_patch(conv_id)
    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["status"] == "active"
    assert conv.get("pending_patch_json") in (None, "")
