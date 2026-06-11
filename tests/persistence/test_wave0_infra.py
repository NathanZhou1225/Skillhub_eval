import sqlite3
from pathlib import Path

import pytest

from skillhub_eval.core.bundle_resolver import (
    BundleNotReadyError,
    BundleRef,
    BundleResolver,
)
from skillhub_eval.core.schemas.enums import RunStatus
from skillhub_eval.persistence.sqlite import SqliteRepository


def _bundle_resolver(
    tmp_path: Path,
    *,
    source: str = "local_ref",
    conversation_id: str = "conv-1",
    source_dir: Path | None = None,
) -> BundleResolver:
    ref = BundleRef(
        conversation_id=conversation_id,
        source=source,
        source_path=source_dir,
        staging_path=tmp_path / "staging" / conversation_id,
    )
    return BundleResolver(ref)

OLD_EVALUATION_RUNS_DDL = """
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
    created_at TEXT NOT NULL
);
"""


def test_init_db_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    repo = SqliteRepository(db_path)
    repo.init_db()
    repo.init_db()


def test_migration_adds_lineage_columns(tmp_path):
    db_path = str(tmp_path / "old.db")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(OLD_EVALUATION_RUNS_DDL)
        conn.execute("PRAGMA user_version = 0")

    repo = SqliteRepository(db_path)
    repo.init_db()

    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info('evaluation_runs')").fetchall()
        }
        version = conn.execute("PRAGMA user_version").fetchone()[0]

    assert "conversation_id" in columns
    assert "parent_run_id" in columns
    assert "superseded_by_run_id" in columns
    assert version == 6


def test_update_status_superseded(tmp_path):
    db_path = str(tmp_path / "test.db")
    repo = SqliteRepository(db_path)
    repo.init_db()

    run_id = repo.create_run(
        skill_id="skill-a",
        skill_bundle_path="/bundles/skill-a",
        bundle_state="eval_ready",
        evaluation_mode="capability_full",
    )
    replacement_run_id = "replacement-run-001"
    repo.update_status(
        run_id,
        RunStatus.superseded.value,
        superseded_by_run_id=replacement_run_id,
    )

    row = repo.get_run(run_id)
    assert row is not None
    assert row["status"] == RunStatus.superseded.value
    assert row["superseded_by_run_id"] == replacement_run_id


def test_list_history_excludes_superseded(tmp_path):
    db_path = str(tmp_path / "test.db")
    repo = SqliteRepository(db_path)
    repo.init_db()

    normal_run_id = repo.create_run(
        skill_id="skill-normal",
        skill_bundle_path="/bundles/skill-normal",
        bundle_state="eval_ready",
        evaluation_mode="capability_full",
    )
    superseded_run_id = repo.create_run(
        skill_id="skill-old",
        skill_bundle_path="/bundles/skill-old",
        bundle_state="eval_ready",
        evaluation_mode="capability_full",
    )
    repo.update_status(
        superseded_run_id,
        RunStatus.superseded.value,
        superseded_by_run_id=normal_run_id,
    )

    history = repo.list_history()
    run_ids = {row["run_id"] for row in history}

    assert normal_run_id in run_ids
    assert superseded_run_id not in run_ids


def test_create_conversation(tmp_path):
    db_path = str(tmp_path / "test.db")
    repo = SqliteRepository(db_path)
    repo.init_db()

    conv_id = repo.create_conversation(
        skill_id="skill-a",
        source="local_ref",
        max_auto_runs=3,
    )

    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["conversation_id"] == conv_id
    assert conv["skill_id"] == "skill-a"
    assert conv["source"] == "local_ref"
    assert conv["status"] == "active"
    assert conv["active_run_id"] is None
    assert conv["auto_run_count"] == 0
    assert conv["max_auto_runs"] == 3
    assert conv["created_at"] is not None


def test_append_lui_message(tmp_path):
    db_path = str(tmp_path / "test.db")
    repo = SqliteRepository(db_path)
    repo.init_db()

    conv_id = repo.create_conversation(
        skill_id="skill-a",
        source="upload",
    )
    repo.append_lui_message(conv_id, role="user", content="Hello")
    run_id = repo.create_run(
        skill_id="skill-a",
        skill_bundle_path="/bundles/skill-a",
        bundle_state="eval_ready",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    repo.append_lui_message(
        conv_id,
        role="assistant",
        content="Hi there",
        run_id=run_id,
    )

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT conversation_id, run_id, role, content
            FROM lui_messages
            WHERE conversation_id=?
            ORDER BY id ASC
            """,
            (conv_id,),
        ).fetchall()

    assert len(rows) == 2
    assert rows[0]["role"] == "user"
    assert rows[0]["content"] == "Hello"
    assert rows[0]["run_id"] is None
    assert rows[1]["role"] == "assistant"
    assert rows[1]["content"] == "Hi there"
    assert rows[1]["run_id"] == run_id


def test_create_run_with_conversation_id(tmp_path):
    db_path = str(tmp_path / "test.db")
    repo = SqliteRepository(db_path)
    repo.init_db()

    conv_id = repo.create_conversation(
        skill_id="skill-a",
        source="local_ref",
    )
    parent_run_id = repo.create_run(
        skill_id="skill-a",
        skill_bundle_path="/bundles/skill-a",
        bundle_state="eval_ready",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    run_id = repo.create_run(
        skill_id="skill-a",
        skill_bundle_path="/bundles/skill-a",
        bundle_state="eval_ready",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
        parent_run_id=parent_run_id,
    )

    run = repo.get_run(run_id)
    assert run is not None
    assert run["conversation_id"] == conv_id
    assert run["parent_run_id"] == parent_run_id

    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["active_run_id"] == run_id


def test_bundle_resolver_local_ref_ensure_staging(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    skill_md = source_dir / "SKILL.md"
    skill_md.write_text("# Skill\n", encoding="utf-8")

    resolver = _bundle_resolver(tmp_path, source_dir=source_dir)
    resolver.ensure_staging()

    staged_skill = resolver.ref.staging_path / "SKILL.md"
    assert staged_skill.exists()
    assert staged_skill.read_text(encoding="utf-8") == "# Skill\n"
    assert skill_md.read_text(encoding="utf-8") == "# Skill\n"


def test_bundle_resolver_ensure_staging_idempotent(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("content", encoding="utf-8")

    resolver = _bundle_resolver(tmp_path, source_dir=source_dir)
    resolver.ensure_staging()
    first_mtime = (resolver.ref.staging_path / "SKILL.md").stat().st_mtime_ns

    resolver.ensure_staging()
    second_mtime = (resolver.ref.staging_path / "SKILL.md").stat().st_mtime_ns

    assert first_mtime == second_mtime
    assert resolver.get_file_content("SKILL.md") == "content"


def test_bundle_resolver_get_file_content(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("hello skill", encoding="utf-8")

    resolver = _bundle_resolver(tmp_path, source_dir=source_dir)
    resolver.ensure_staging()

    assert resolver.get_file_content("SKILL.md") == "hello skill"


def test_bundle_resolver_write_file_content(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("base", encoding="utf-8")

    resolver = _bundle_resolver(tmp_path, source_dir=source_dir)
    resolver.write_file_content("eval_cases/c1.yaml", "case: one\n")

    written = resolver.ref.staging_path / "eval_cases" / "c1.yaml"
    assert written.exists()
    assert written.read_text(encoding="utf-8") == "case: one\n"


def test_bundle_resolver_list_files(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("base", encoding="utf-8")

    resolver = _bundle_resolver(tmp_path, source_dir=source_dir)
    resolver.write_file_content("eval_cases/c1.yaml", "case: one\n")
    resolver.write_file_content("eval_cases/c2.yaml", "case: two\n")

    files = resolver.list_files("eval_cases")
    assert sorted(files) == ["eval_cases/c1.yaml", "eval_cases/c2.yaml"]


def test_bundle_resolver_source_readonly(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_skill = source_dir / "SKILL.md"
    source_skill.write_text("original", encoding="utf-8")

    resolver = _bundle_resolver(tmp_path, source_dir=source_dir)
    resolver.write_file_content("SKILL.md", "modified in staging")

    assert source_skill.read_text(encoding="utf-8") == "original"
    assert resolver.get_file_content("SKILL.md") == "modified in staging"


def test_bundle_resolver_upload_unready_raises(tmp_path):
    resolver = _bundle_resolver(tmp_path, source="upload", source_dir=None)

    with pytest.raises(BundleNotReadyError):
        resolver.get_file_content("SKILL.md")


def test_bundle_resolver_local_ref_fallback_before_staging(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("from source", encoding="utf-8")

    resolver = _bundle_resolver(tmp_path, source_dir=source_dir)

    assert resolver.get_file_content("SKILL.md") == "from source"
    assert not resolver.ref.staging_path.exists()
