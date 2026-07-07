import sqlite3

import pytest
from fastapi import HTTPException

from skillhub_eval.adapters.api._session import check_session_gate
from skillhub_eval.core.schemas.enums import RunStatus
from skillhub_eval.persistence.sqlite import SqliteRepository


OLD_CONVERSATIONS_DDL = """
CREATE TABLE conversations (
    conversation_id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    active_run_id TEXT,
    auto_run_count INTEGER NOT NULL DEFAULT 0,
    max_auto_runs INTEGER NOT NULL DEFAULT 5,
    created_at TEXT NOT NULL
);
"""


def test_init_db_migration_to_v2_is_idempotent(tmp_path):
    db_path = str(tmp_path / "wave4_v2.db")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(OLD_CONVERSATIONS_DDL)
        conn.execute("PRAGMA user_version = 1")

    repo = SqliteRepository(db_path)
    repo.init_db()
    repo.init_db()

    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info('conversations')").fetchall()
        }
        version = conn.execute("PRAGMA user_version").fetchone()[0]

    assert "auto_confirmed" in columns
    assert "source_path" in columns
    assert version == SqliteRepository.SCHEMA_VERSION


def test_increment_auto_run_count_returns_incremented_value(tmp_path):
    repo = SqliteRepository(str(tmp_path / "wave4_counter.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill-a", source="local_ref")

    assert repo.increment_auto_run_count(conv_id) == 1
    assert repo.increment_auto_run_count(conv_id) == 2

    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["auto_run_count"] == 2


def test_supersede_run_does_not_change_conversation_active_run(tmp_path):
    repo = SqliteRepository(str(tmp_path / "wave4_supersede.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill-a", source="local_ref")

    old_run_id = repo.create_run(
        skill_id="skill-a",
        skill_bundle_path="/bundles/skill-a",
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    new_run_id = repo.create_run(
        skill_id="skill-a",
        skill_bundle_path="/bundles/skill-a",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
        parent_run_id=old_run_id,
    )

    repo.supersede_run(old_run_id, new_run_id)

    old_run = repo.get_run(old_run_id)
    assert old_run is not None
    assert old_run["status"] == RunStatus.superseded.value
    assert old_run["superseded_by_run_id"] == new_run_id

    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["active_run_id"] == new_run_id


def test_create_conversation_stores_source_path(tmp_path):
    repo = SqliteRepository(str(tmp_path / "wave4_source_path.db"))
    repo.init_db()

    source_path = "data/originals/conv-1"
    conv_id = repo.create_conversation(
        skill_id="skill-a",
        source="upload",
        source_path=source_path,
    )

    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["source_path"] == source_path


def test_update_conversation_source_fields(tmp_path):
    repo = SqliteRepository(str(tmp_path / "wave4_update_source.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill-a", source="upload")

    repo.set_conversation_source(conv_id, "local_ref")
    repo.set_conversation_source_path(conv_id, "data/originals/conv-1")

    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["source"] == "local_ref"
    assert conv["source_path"] == "data/originals/conv-1"
    assert conv["auto_confirmed"] == 0


def test_check_session_gate_frozen_returns_403(tmp_path):
    repo = SqliteRepository(str(tmp_path / "wave4_gate_frozen.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill-a", source="local_ref")
    repo.update_conversation_status(conv_id, "frozen")

    with pytest.raises(HTTPException) as exc_info:
        check_session_gate(conv_id, repo)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["error"] == "CONVERSATION_FROZEN"


def test_check_session_gate_running_returns_409(tmp_path):
    repo = SqliteRepository(str(tmp_path / "wave4_gate_running.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill-a", source="local_ref")
    run_id = repo.create_run(
        skill_id="skill-a",
        skill_bundle_path="/bundles/skill-a",
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )

    with pytest.raises(HTTPException) as exc_info:
        check_session_gate(conv_id, repo)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"] == "SESSION_LOCKED"
    assert exc_info.value.detail["active_run_id"] == run_id


def test_check_session_gate_completed_passes(tmp_path):
    repo = SqliteRepository(str(tmp_path / "wave4_gate_completed.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill-a", source="local_ref")
    run_id = repo.create_run(
        skill_id="skill-a",
        skill_bundle_path="/bundles/skill-a",
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, RunStatus.completed.value)

    check_session_gate(conv_id, repo)
