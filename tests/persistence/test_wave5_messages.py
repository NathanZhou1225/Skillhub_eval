import json
import sqlite3

import pytest

from skillhub_eval.persistence.sqlite import SqliteRepository


OLD_LUI_MESSAGES_DDL = """
CREATE TABLE lui_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    run_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def test_init_db_migration_to_v3_is_idempotent(tmp_path):
    db_path = str(tmp_path / "wave5_v3.db")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(OLD_LUI_MESSAGES_DDL)
        conn.execute("PRAGMA user_version = 2")

    repo = SqliteRepository(db_path)
    repo.init_db()
    repo.init_db()

    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info('lui_messages')").fetchall()
        }
        version = conn.execute("PRAGMA user_version").fetchone()[0]

    assert "message_type" in columns
    assert "payload_json" in columns
    assert version == SqliteRepository.SCHEMA_VERSION


def test_append_lui_message_stores_type_and_payload(tmp_path):
    repo = SqliteRepository(str(tmp_path / "msg.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill-a", source="upload")

    payload = {"run_id": "run-1", "status": "completed"}
    repo.append_lui_message(
        conv_id,
        role="agent",
        content="评估完成",
        run_id="run-1",
        message_type="rich_report",
        payload_json=payload,
    )

    messages = repo.get_lui_messages(conv_id)
    assert len(messages) == 1
    assert messages[0]["message_type"] == "rich_report"
    assert messages[0]["payload_json"] == payload
    assert messages[0]["run_id"] == "run-1"


def test_has_rich_report_for_run_is_idempotent_check(tmp_path):
    repo = SqliteRepository(str(tmp_path / "rich.db"))
    repo.init_db()
    conv_id = repo.create_conversation(skill_id="skill-a", source="upload")

    assert repo.has_rich_report_for_run(conv_id, "run-1") is False

    repo.append_lui_message(
        conv_id,
        role="agent",
        content="报告",
        run_id="run-1",
        message_type="rich_report",
        payload_json={"run_id": "run-1"},
    )
    assert repo.has_rich_report_for_run(conv_id, "run-1") is True
    assert repo.has_rich_report_for_run(conv_id, "run-2") is False


def test_list_conversations_includes_preview_and_pending_review(tmp_path):
    repo = SqliteRepository(str(tmp_path / "list.db"))
    repo.init_db()
    conv_a = repo.create_conversation(skill_id="skill-a", source="upload")
    conv_b = repo.create_conversation(skill_id="skill-b", source="upload")

    repo.append_lui_message(conv_a, "agent", "hello a")
    repo.append_lui_message(conv_b, "system", "pending review soon")

    run_id = repo.create_run(
        skill_id="skill-b",
        skill_bundle_path="/b",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_b,
    )
    with repo._conn() as conn:
        conn.execute(
            "UPDATE conversations SET active_run_id=? WHERE conversation_id=?",
            (run_id, conv_b),
        )
        conn.execute(
            """
            UPDATE evaluation_runs
            SET status=?, human_review_required=1
            WHERE run_id=?
            """,
            ("awaiting_human_review", run_id),
        )

    all_convs = repo.list_conversations(limit=10)
    assert len(all_convs) == 2
    by_id = {c["conversation_id"]: c for c in all_convs}
    assert by_id[conv_a]["lui_message_count"] == 1
    assert by_id[conv_a]["last_message_preview"] == "hello a"
    assert by_id[conv_a]["human_review_pending"] is False
    assert by_id[conv_b]["human_review_pending"] is True

    pending = repo.list_conversations(limit=10, pending_review=True)
    assert len(pending) == 1
    assert pending[0]["conversation_id"] == conv_b
