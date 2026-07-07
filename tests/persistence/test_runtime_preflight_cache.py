import sqlite3

from skillhub_eval.execution.preflight_cache import get_valid_runtime_preflight
from skillhub_eval.persistence.sqlite import SqliteRepository


def test_init_db_migration_to_v12_creates_runtime_preflight_cache(tmp_path):
    db_path = str(tmp_path / "v12.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA user_version = 11")

    repo = SqliteRepository(db_path)
    repo.init_db()

    with sqlite3.connect(db_path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        table = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='runtime_preflight_cache'"
        ).fetchone()
        index = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_runtime_preflight_cache_key'"
        ).fetchone()

    assert version == 12
    assert table is not None
    assert index is not None


def test_upsert_and_get_runtime_preflight_cache_survives_new_repo(tmp_path):
    db_path = str(tmp_path / "preflight.db")
    repo = SqliteRepository(db_path)
    repo.init_db()

    repo.upsert_runtime_preflight(
        runtime_id="cursor-agent",
        model_id="gpt-5",
        skill_fingerprint="skill-123",
        fingerprint="abc",
        status="passed",
        cli_path="C:/cursor-agent.exe",
        cli_version="cursor-agent 1.0",
        checked_at="2026-07-02T00:00:00+00:00",
        expires_at="2026-07-03T00:00:00+00:00",
        failure_reason=None,
        message_zh="preflight passed",
        manual_hint=None,
        evidence={"command_observed": True},
    )

    loaded = SqliteRepository(db_path).get_runtime_preflight(
        runtime_id="cursor-agent",
        model_id="gpt-5",
        skill_fingerprint="skill-123",
    )

    assert loaded["fingerprint"] == "abc"
    assert loaded["status"] == "passed"
    assert loaded["evidence"]["command_observed"] is True


def test_runtime_preflight_upsert_replaces_same_cache_key(tmp_path):
    repo = SqliteRepository(str(tmp_path / "preflight.db"))
    repo.init_db()

    for fingerprint, status in (("old", "failed"), ("new", "passed")):
        repo.upsert_runtime_preflight(
            runtime_id="trae",
            model_id="default",
            skill_fingerprint="skill-123",
            fingerprint=fingerprint,
            status=status,
            cli_path=None,
            cli_version=None,
            checked_at="2026-07-02T00:00:00+00:00",
            expires_at="2026-07-03T00:00:00+00:00",
            failure_reason=None,
            message_zh=None,
            manual_hint=None,
            evidence={"fingerprint": fingerprint},
        )

    loaded = repo.get_runtime_preflight(
        runtime_id="trae",
        model_id="default",
        skill_fingerprint="skill-123",
    )

    assert loaded["fingerprint"] == "new"
    assert loaded["status"] == "passed"
    assert loaded["evidence"] == {"fingerprint": "new"}


def test_get_valid_runtime_preflight_checks_status_fingerprint_and_expiry(tmp_path):
    repo = SqliteRepository(str(tmp_path / "preflight.db"))
    repo.init_db()
    repo.upsert_runtime_preflight(
        runtime_id="codex",
        model_id="default",
        skill_fingerprint="skill-123",
        fingerprint="runtime-abc",
        status="passed",
        cli_path="codex",
        cli_version="codex 1.0",
        checked_at="2026-07-02T00:00:00+00:00",
        expires_at="2026-07-03T00:00:00+00:00",
        failure_reason=None,
        message_zh=None,
        manual_hint=None,
        evidence={},
    )

    assert get_valid_runtime_preflight(
        repo,
        runtime_id="codex",
        model_id="default",
        skill_fingerprint="skill-123",
        fingerprint="runtime-abc",
        now="2026-07-02T12:00:00+00:00",
    )
    assert get_valid_runtime_preflight(
        repo,
        runtime_id="codex",
        model_id="default",
        skill_fingerprint="skill-123",
        fingerprint="other",
        now="2026-07-02T12:00:00+00:00",
    ) is None
    assert get_valid_runtime_preflight(
        repo,
        runtime_id="codex",
        model_id="default",
        skill_fingerprint="skill-123",
        fingerprint="runtime-abc",
        now="2026-07-04T00:00:00+00:00",
    ) is None


def test_get_valid_runtime_preflight_accepts_z_and_naive_timestamps(tmp_path):
    repo = SqliteRepository(str(tmp_path / "preflight.db"))
    repo.init_db()
    repo.upsert_runtime_preflight(
        runtime_id="cursor-agent",
        model_id="default",
        skill_fingerprint="skill-123",
        fingerprint="runtime-abc",
        status="passed",
        cli_path=None,
        cli_version=None,
        checked_at="2026-07-02T00:00:00Z",
        expires_at="2026-07-03T00:00:00Z",
        failure_reason=None,
        message_zh=None,
        manual_hint=None,
        evidence={},
    )

    assert get_valid_runtime_preflight(
        repo,
        runtime_id="cursor-agent",
        model_id="default",
        skill_fingerprint="skill-123",
        fingerprint="runtime-abc",
        now="2026-07-02T12:00:00",
    )


def test_get_valid_runtime_preflight_rejects_malformed_expiry(tmp_path):
    repo = SqliteRepository(str(tmp_path / "preflight.db"))
    repo.init_db()
    repo.upsert_runtime_preflight(
        runtime_id="trae",
        model_id="default",
        skill_fingerprint="skill-123",
        fingerprint="runtime-abc",
        status="passed",
        cli_path=None,
        cli_version=None,
        checked_at="2026-07-02T00:00:00+00:00",
        expires_at="not-a-date",
        failure_reason=None,
        message_zh=None,
        manual_hint=None,
        evidence={},
    )

    assert get_valid_runtime_preflight(
        repo,
        runtime_id="trae",
        model_id="default",
        skill_fingerprint="skill-123",
        fingerprint="runtime-abc",
        now="2026-07-02T12:00:00+00:00",
    ) is None
