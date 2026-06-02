"""
Task 10 — CLI command tests.

Strategy: use typer.testing.CliRunner which invokes commands in-process.
Pass --db-path to a tmp SQLite so tests are fully isolated.
All tests avoid real network calls (no LLM providers are invoked because
the bundle fixtures trigger Level 0 fail or we test non-network commands).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from skillhub_eval.adapters.cli.main import app
from skillhub_eval.persistence.sqlite import SqliteRepository

runner = CliRunner()


# ─── helpers ──────────────────────────────────────────────────────────────────

def make_db(tmp_path) -> str:
    db = str(tmp_path / "cli_test.db")
    repo = SqliteRepository(db)
    repo.init_db()
    return db


def make_skill_bundle(tmp_path, risk: str = "low", n_cases: int = 3) -> str:
    bundle = tmp_path / "bundle"
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text(
        f"---\nname: cli-skill\nid: skill.cli\nrisk_level: {risk}\n"
        "description: test\n---\n",
        encoding="utf-8",
    )
    ec = bundle / "eval_cases"
    ec.mkdir()
    for i in range(n_cases):
        (ec / f"c{i:02d}.yaml").write_text(
            f"id: c{i:02d}\ntype: happy_path\nuser_intent: intent {i}\n",
            encoding="utf-8",
        )
    return str(bundle)


# ─── --help / root ────────────────────────────────────────────────────────────

def test_root_shows_help():
    result = runner.invoke(app, [])
    # Typer/Click exits with 2 when no_args_is_help=True (standard Click behavior)
    assert result.exit_code in (0, 2)
    assert "run" in result.output or "SkillHub" in result.output


def test_help_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "status" in result.output
    assert "history" in result.output
    assert "confirm" in result.output
    assert "serve" in result.output


# ─── run ──────────────────────────────────────────────────────────────────────

def test_run_missing_skill_md_exits_with_fail_status(tmp_path):
    """Empty bundle → Level 0 fail → exit 0 but review_status=fail in DB."""
    db = make_db(tmp_path)
    empty_bundle = str(tmp_path / "empty")
    Path(empty_bundle).mkdir()

    result = runner.invoke(app, [
        "run", empty_bundle,
        "--skill-id", "skill.empty",
        "--db-path", db,
    ])
    assert result.exit_code == 0
    assert "fail" in result.output.lower() or "run_id" in result.output


def test_run_json_output(tmp_path):
    """--json flag must produce valid JSON with run_id field."""
    db = make_db(tmp_path)
    bundle = make_skill_bundle(tmp_path)

    result = runner.invoke(app, [
        "run", bundle,
        "--skill-id", "skill.cli",
        "--bundle-state", "draft_enriched",
        "--mode", "capability_full",
        "--db-path", db,
        "--json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "run_id" in data
    assert "status" in data


def test_run_invalid_bundle_state(tmp_path):
    db = make_db(tmp_path)
    bundle = make_skill_bundle(tmp_path)
    result = runner.invoke(app, [
        "run", bundle,
        "--bundle-state", "not_valid",
        "--db-path", db,
    ])
    assert result.exit_code != 0


def test_run_auto_detects_skill_id(tmp_path):
    """No --skill-id → parses id from SKILL.md frontmatter."""
    db = make_db(tmp_path)
    bundle = make_skill_bundle(tmp_path)

    result = runner.invoke(app, [
        "run", bundle,
        "--bundle-state", "draft_enriched",
        "--mode", "capability_full",
        "--db-path", db,
        "--json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    # Should have used id from SKILL.md ("skill.cli")
    assert data["run_id"]  # run was created


# ─── status ───────────────────────────────────────────────────────────────────

def test_status_not_found(tmp_path):
    db = make_db(tmp_path)
    result = runner.invoke(app, ["status", "nonexistent-id", "--db-path", db])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_status_shows_run(tmp_path):
    db = make_db(tmp_path)
    repo = SqliteRepository(db)
    repo.init_db()
    run_id = repo.create_run(
        skill_id="skill.cli",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    result = runner.invoke(app, ["status", run_id, "--db-path", db])
    assert result.exit_code == 0
    assert run_id in result.output


def test_status_json_output(tmp_path):
    db = make_db(tmp_path)
    repo = SqliteRepository(db)
    repo.init_db()
    run_id = repo.create_run(
        skill_id="skill.cli",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    result = runner.invoke(app, ["status", run_id, "--db-path", db, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["run_id"] == run_id
    assert "status" in data


# ─── history ──────────────────────────────────────────────────────────────────

def test_history_empty(tmp_path):
    db = make_db(tmp_path)
    result = runner.invoke(app, ["history", "--db-path", db])
    assert result.exit_code == 0
    assert "No runs found" in result.output


def test_history_lists_runs(tmp_path):
    db = make_db(tmp_path)
    repo = SqliteRepository(db)
    repo.init_db()
    for i in range(3):
        repo.create_run(
            skill_id=f"skill.{i}",
            skill_bundle_path="/tmp/x",
            bundle_state="confirmed",
            evaluation_mode="capability_full",
        )
    result = runner.invoke(app, ["history", "--db-path", db])
    assert result.exit_code == 0
    assert "3 run(s)" in result.output


def test_history_json_output(tmp_path):
    db = make_db(tmp_path)
    repo = SqliteRepository(db)
    repo.init_db()
    repo.create_run(
        skill_id="skill.x",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    result = runner.invoke(app, ["history", "--db-path", db, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total"] == 1
    assert len(data["runs"]) == 1


def test_history_human_review_filter(tmp_path):
    db = make_db(tmp_path)
    repo = SqliteRepository(db)
    repo.init_db()
    run_id = repo.create_run(
        skill_id="skill.flag",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    repo.set_human_review_required(run_id, True, ["MODEL_DISAGREEMENT_R5"])
    # a clean run
    repo.create_run(
        skill_id="skill.ok",
        skill_bundle_path="/tmp/x",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    result = runner.invoke(app, ["history", "--human-review-only", "--db-path", db, "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total"] == 1
    assert data["runs"][0]["skill_id"] == "skill.flag"


# ─── confirm ──────────────────────────────────────────────────────────────────

def test_confirm_saves_fields(tmp_path):
    db = make_db(tmp_path)
    result = runner.invoke(app, [
        "confirm", "skill.abc",
        "--field", "negative_prompts=do not leak PII",
        "--field", "error_handling=return structured error",
        "--operator", "alice",
        "--db-path", db,
    ])
    assert result.exit_code == 0
    assert "2 field(s)" in result.output
    assert "skill.abc" in result.output


def test_confirm_no_fields_errors(tmp_path):
    db = make_db(tmp_path)
    result = runner.invoke(app, ["confirm", "skill.abc", "--db-path", db])
    assert result.exit_code == 1


def test_confirm_invalid_field_format(tmp_path):
    db = make_db(tmp_path)
    result = runner.invoke(app, [
        "confirm", "skill.abc",
        "--field", "no_equals_sign",
        "--db-path", db,
    ])
    assert result.exit_code == 1
