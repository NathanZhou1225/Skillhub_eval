import sqlite3

from skillhub_eval.execution.consent import clear_exec_consent, has_exec_consent
from skillhub_eval.execution.agent_registry import DEFAULT_MODEL_ID
from skillhub_eval.execution.preferences import (
    compute_ready,
    get_exec_agent,
    get_exec_model,
    get_exec_source,
    get_preferences,
    grant_persisted_consent,
    set_preferences,
)
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.settings import Settings, settings


def test_migration_through_v11_creates_exec_preferences(tmp_path):
    db_path = str(tmp_path / "v9_to_v11.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA user_version = 9")

    repo = SqliteRepository(db_path)
    repo.init_db()

    with sqlite3.connect(db_path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info('exec_preferences')")
        }

    assert version == SqliteRepository.SCHEMA_VERSION
    assert {
        "id",
        "exec_source",
        "exec_agent",
        "exec_model",
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
    assert prefs["exec_model"] == "default"
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
        exec_model="gpt-5-codex",
        consent_granted=True,
    )
    assert updated["exec_source"] == "sample_io"
    assert updated["exec_agent"] == "codex"
    assert updated["exec_model"] == "gpt-5-codex"
    assert updated["consent_granted"] is True
    assert updated["ready"] is True

    repo = SqliteRepository(db_path)
    row = repo.get_exec_preferences()
    assert row is not None
    assert row["id"] == 1
    assert row["exec_source"] == "sample_io"
    assert row["exec_agent"] == "codex"
    assert row["exec_model"] == "gpt-5-codex"
    assert row["consent_granted"] == 1


def test_get_exec_overrides_from_preferences(monkeypatch, tmp_path):
    db_path = str(tmp_path / "prefs-engine.db")
    SqliteRepository(db_path).init_db()
    monkeypatch.setattr(settings, "exec_source", "sample_io")
    monkeypatch.setattr(settings, "exec_agent", "claude")
    monkeypatch.setattr(settings, "exec_model", "default")

    assert get_exec_source(db_path=db_path) == "local"
    assert get_exec_agent(db_path=db_path) == "claude"
    assert get_exec_model(db_path=db_path) == "default"

    set_preferences(
        db_path=db_path,
        exec_source="sample_io",
        exec_agent="cursor-agent",
        exec_model="gpt-5",
    )
    assert get_exec_source(db_path=db_path) == "sample_io"
    assert get_exec_agent(db_path=db_path) == "cursor-agent"
    assert get_exec_model(db_path=db_path) == "gpt-5"


def test_exec_model_default_uses_env_override_until_non_default_stored(
    monkeypatch,
    tmp_path,
):
    db_path = str(tmp_path / "prefs-env-model.db")
    SqliteRepository(db_path).init_db()
    monkeypatch.setattr(settings, "exec_model", "gpt-5-codex")

    assert get_exec_model(db_path=db_path) == "gpt-5-codex"
    assert get_preferences(db_path=db_path)["exec_model"] == "gpt-5-codex"

    set_preferences(db_path=db_path, exec_model=DEFAULT_MODEL_ID)
    assert get_exec_model(db_path=db_path) == "gpt-5-codex"
    assert get_preferences(db_path=db_path)["exec_model"] == "gpt-5-codex"

    set_preferences(db_path=db_path, exec_model="gpt-5")
    assert get_exec_model(db_path=db_path) == "gpt-5"
    assert get_preferences(db_path=db_path)["exec_model"] == "gpt-5"


def test_set_preferences_persists_exec_model_and_ready(monkeypatch, tmp_path):
    db_path = str(tmp_path / "prefs-model.db")
    SqliteRepository(db_path).init_db()
    monkeypatch.setattr(settings, "exec_consent_required", True)
    monkeypatch.setattr(
        "skillhub_eval.execution.preferences._is_agent_detected",
        lambda agent_id: agent_id == "cursor-agent",
    )

    prefs = set_preferences(
        db_path=db_path,
        exec_source="local",
        exec_agent="cursor-agent",
        exec_model="gpt-5",
        consent_granted=True,
    )

    assert prefs["exec_model"] == "gpt-5"
    assert prefs["ready"] is True
    assert prefs["ready_reason"] is None
    assert get_exec_model(db_path=db_path) == "gpt-5"

    updated = set_preferences(db_path=db_path, consent_granted=False)
    assert updated["exec_model"] == "gpt-5"
    assert SqliteRepository(db_path).get_exec_preferences()["exec_model"] == "gpt-5"


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


def test_local_agent_case_timeout_env_aliases(monkeypatch):
    aliases = {
        "LOCAL_AGENT_CASE_TIMEOUT_LOW": 601,
        "LOCAL_AGENT_CASE_TIMEOUT_LOW_S": 602,
        "SKILLHUB_LOCAL_AGENT_CASE_TIMEOUT_LOW": 603,
        "SKILLHUB_LOCAL_AGENT_CASE_TIMEOUT_LOW_S": 604,
        "LOCAL_AGENT_CASE_TIMEOUT_MEDIUM": 901,
        "LOCAL_AGENT_CASE_TIMEOUT_MEDIUM_S": 902,
        "SKILLHUB_LOCAL_AGENT_CASE_TIMEOUT_MEDIUM": 903,
        "SKILLHUB_LOCAL_AGENT_CASE_TIMEOUT_MEDIUM_S": 904,
        "LOCAL_AGENT_CASE_TIMEOUT_HIGH": 1801,
        "LOCAL_AGENT_CASE_TIMEOUT_HIGH_S": 1802,
        "SKILLHUB_LOCAL_AGENT_CASE_TIMEOUT_HIGH": 1803,
        "SKILLHUB_LOCAL_AGENT_CASE_TIMEOUT_HIGH_S": 1804,
    }
    for name in aliases:
        monkeypatch.delenv(name, raising=False)

    for name, value in aliases.items():
        for other_name in aliases:
            monkeypatch.delenv(other_name, raising=False)
        monkeypatch.setenv(name, str(value))

        configured = Settings()
        if "LOW" in name:
            assert configured.local_agent_case_timeout_low_s == value
        elif "MEDIUM" in name:
            assert configured.local_agent_case_timeout_medium_s == value
        else:
            assert configured.local_agent_case_timeout_high_s == value

    for name in aliases:
        monkeypatch.delenv(name, raising=False)

    defaults = Settings()
    assert defaults.local_agent_case_timeout_low_s == 600
    assert defaults.local_agent_case_timeout_medium_s == 900
    assert defaults.local_agent_case_timeout_high_s == 1800
