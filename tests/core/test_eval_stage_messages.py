"""Tests for formal eval stage chat notices."""

from __future__ import annotations

from skillhub_eval.core.eval_stage_messages import (
    case_executing_message,
    maybe_append_formal_eval_stage_notice,
    model_judging_message,
)
from skillhub_eval.persistence.sqlite import SqliteRepository


def _repo(tmp_path):
    db = tmp_path / "eval_stage.db"
    repo = SqliteRepository(str(db))
    repo.init_db()
    return repo


def test_case_executing_messages_differ_by_execution_mode():
    assert "本地 Agent" in case_executing_message(uses_local_execution=True)
    assert "样例" in case_executing_message(uses_local_execution=False)


def test_model_judging_messages_differ_by_execution_mode():
    assert "本地 Agent" in model_judging_message(uses_local_execution=True)
    assert "双模型" in model_judging_message(uses_local_execution=True)
    assert "样例" in model_judging_message(uses_local_execution=False)


def test_maybe_append_skips_without_conversation(tmp_path):
    repo = _repo(tmp_path)
    run_id = repo.create_run(
        skill_id="demo",
        skill_bundle_path=str(tmp_path / "bundle"),
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    maybe_append_formal_eval_stage_notice(
        repo,
        run_id,
        "case_executing",
        uses_local_execution=True,
    )
    assert repo.get_lui_messages("") == []


def test_maybe_append_writes_two_stage_bubbles(tmp_path):
    repo = _repo(tmp_path)
    conv_id = repo.create_conversation(skill_id="demo", source="upload", source_path=str(tmp_path / "orig"))
    run_id = repo.create_run(
        skill_id="demo",
        skill_bundle_path=str(tmp_path / "bundle"),
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    maybe_append_formal_eval_stage_notice(
        repo,
        run_id,
        "case_executing",
        uses_local_execution=False,
    )
    maybe_append_formal_eval_stage_notice(
        repo,
        run_id,
        "model_judging",
        uses_local_execution=False,
    )
    messages = repo.get_lui_messages(conv_id)
    assert len(messages) == 2
    assert "样例" in messages[0]["content"]
    assert "双模型" in messages[1]["content"]


def test_maybe_append_skips_degraded_run(tmp_path):
    repo = _repo(tmp_path)
    conv_id = repo.create_conversation(skill_id="demo", source="upload", source_path=str(tmp_path / "orig"))
    run_id = repo.create_run(
        skill_id="demo",
        skill_bundle_path=str(tmp_path / "bundle"),
        bundle_state="minimal",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    maybe_append_formal_eval_stage_notice(
        repo,
        run_id,
        "case_executing",
        uses_local_execution=True,
    )
    assert repo.get_lui_messages(conv_id) == []
