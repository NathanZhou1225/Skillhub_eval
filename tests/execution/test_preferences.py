import sqlite3

from skillhub_eval.execution.consent import clear_exec_consent, has_exec_consent
from skillhub_eval.execution.preferences import (
    compute_ready,
    get_exec_agent,
    get_exec_source,
    get_preferences,
    grant_persisted_consent,
    set_preferences,
)
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.settings import settings


def test_migration_to_v10_creates_exec_preferences(tmp_path):
    db_path = str(tmp_path / "v9_to_v10.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA user_version = 9")

    repo = SqliteRepository(db_path)
    repo.init_db()

    with sqlite3.connect(db_path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info('exec_preferences')")
        }

    assert version == 10
    assert {
        "id",
        "exec_source",
        "exec_agent",
        "consent_granted",
        "updated_at",
    }.issubset(columns)


def test_get_preferences_defaults_without_row(monkeypatch, tmp_path):
    db_path = str(tmp_path / "prefs-defaults.db")
    repo = SqliteRepository(db_path)
    repo.init_db()

    monkeypatch.setattr(settings, "exec_source", "sample_io")
    monkeypatch.setattr(settings, "exec_agent", "claude")
    monkeypatch.setattr(settings, "exec_consent_required", True)

    prefs = get_preferences(db_path=db_path)
    assert prefs["exec_source"] == "local"
    assert prefs["exec_agent"] == "claude"
    assert prefs["consent_granted"] is False
    assert prefs["ready"] is False
    assert prefs["ready_reason"] == "agent_unavailable"
    assert repo.get_exec_preferences() is None


def test_set_preferences_persists_singleton_row(tmp_path):
    db_path = str(tmp_path / "prefs-set.db")
    SqliteRepository(db_path).init_db()

    updated = set_preferences(
        db_path=db_path,
        exec_source="sample_io",
        exec_agent="codex",
        consent_granted=True,
    )
    assert updated["exec_source"] == "sample_io"
    assert updated["exec_agent"] == "codex"
    assert updated["consent_granted"] is True
    assert updated["ready"] is True

    repo = SqliteRepository(db_path)
    row = repo.get_exec_preferences()
    assert row is not None
    assert row["id"] == 1
    assert row["exec_source"] == "sample_io"
    assert row["exec_agent"] == "codex"
    assert row["consent_granted"] == 1


def test_get_exec_overrides_from_preferences(monkeypatch, tmp_path):
    db_path = str(tmp_path / "prefs-engine.db")
    SqliteRepository(db_path).init_db()
    monkeypatch.setattr(settings, "exec_source", "sample_io")
    monkeypatch.setattr(settings, "exec_agent", "claude")

    assert get_exec_source(db_path=db_path) == "local"
    assert get_exec_agent(db_path=db_path) == "claude"

    set_preferences(db_path=db_path, exec_source="sample_io", exec_agent="cursor-agent")
    assert get_exec_source(db_path=db_path) == "sample_io"
    assert get_exec_agent(db_path=db_path) == "cursor-agent"


def test_compute_ready_local_requires_detected_agent_and_consent(monkeypatch):
    monkeypatch.setattr(settings, "exec_consent_required", True)
    monkeypatch.setattr(
        "skillhub_eval.execution.preferences._is_agent_detected",
        lambda agent_id: agent_id == "claude",
    )

    ready, reason = compute_ready("local", "claude", True)
    assert ready is True
    assert reason is None

    ready, reason = compute_ready("local", "codex", True)
    assert ready is False
    assert reason == "agent_unavailable"

    ready, reason = compute_ready("local", "claude", False)
    assert ready is False
    assert reason == "consent_required"


def test_compute_ready_skips_consent_when_not_required(monkeypatch):
    monkeypatch.setattr(settings, "exec_consent_required", False)
    monkeypatch.setattr(
        "skillhub_eval.execution.preferences._is_agent_detected",
        lambda agent_id: True,
    )

    ready, reason = compute_ready("local", "claude", False)
    assert ready is True
    assert reason is None


def test_grant_persisted_consent_sets_db_and_wildcard(tmp_path):
    db_path = str(tmp_path / "prefs-consent.db")
    SqliteRepository(db_path).init_db()
    clear_exec_consent()
    try:
        grant_persisted_consent(db_path=db_path)
        prefs = get_preferences(db_path=db_path)
        assert prefs["consent_granted"] is True
        assert has_exec_consent("any-skill-id") is True
    finally:
        clear_exec_consent()
