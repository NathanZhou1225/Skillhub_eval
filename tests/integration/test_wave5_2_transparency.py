"""Wave 5.2 Task 10 — transparency E2E integration tests."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.chat_notifications import (
    append_readiness_result_message,
    append_rich_report_message,
)
from skillhub_eval.core.propagator import PropagatorResult
from skillhub_eval.persistence.sqlite import SqliteRepository


def _skill_md(*, with_category: bool = True) -> str:
    category_line = "category: fin-research/quant-signal\n" if with_category else ""
    return (
        "---\n"
        "id: grill-me\n"
        "name: grill-me\n"
        "risk_level: low\n"
        "description: test bundle for wave5.2 transparency integration.\n"
        f"{category_line}"
        "negative_prompts: np\n"
        "error_handling: eh\n"
        "permission_scope: ps\n"
        "security_notes: sn\n"
        "---\n"
        "# Grill-Me\n"
    )


def _zip_skill_only(*, with_category: bool = True) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", _skill_md(with_category=with_category))
    return buffer.getvalue()


def _run_count(repo: SqliteRepository, conv_id: str) -> int:
    with repo._conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM evaluation_runs WHERE conversation_id=?",
            (conv_id,),
        ).fetchone()
    return int(row["c"]) if row else 0


def _write_case_files(staging_path: Path, case_ids: list[str]) -> None:
    eval_cases = staging_path / "eval_cases"
    sample_io = staging_path / "sample_io"
    eval_cases.mkdir(parents=True, exist_ok=True)
    sample_io.mkdir(parents=True, exist_ok=True)
    for case_id in case_ids:
        payload = {
            "id": case_id,
            "type": "happy_path",
            "user_intent": "intent",
            "input_template": "input",
            "expected_behavior": "behavior",
        }
        (eval_cases / f"{case_id}.yaml").write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        (sample_io / f"{case_id}.json").write_text(
            '{"input":"x","output":"y"}',
            encoding="utf-8",
        )


def _set_report_json(repo: SqliteRepository, run_id: str, payload: dict) -> None:
    with repo._conn() as conn:
        conn.execute(
            "UPDATE evaluation_runs SET report_json=? WHERE run_id=?",
            (json.dumps(payload, ensure_ascii=False), run_id),
        )


@pytest.fixture()
def client_with_repo(tmp_path, monkeypatch):
    repo = SqliteRepository(str(tmp_path / "wave5_2_transparency.db"))
    repo.init_db()
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    async def _fast_run_async(self, run_id, skill_bundle_path, bundle_state, evaluation_mode):
        run = self.repo.get_run(run_id) or {}
        conv_id = run.get("conversation_id")
        mode = (
            evaluation_mode.value
            if hasattr(evaluation_mode, "value")
            else str(evaluation_mode)
        )
        if mode == "degraded":
            self.repo.append_stage(run_id, "level0_checking")
            self.repo.append_stage(run_id, "risk_locking")
            self.repo.append_stage(run_id, "normalizing")
            _set_report_json(
                self.repo,
                run_id,
                {
                    "gaps": [{"field_path": "eval_cases", "severity": "required"}],
                    "required_actions": ["补齐 eval_cases"],
                    "security_status": "passed",
                    "risk_level_locked": "low",
                    "completeness_score": 82.0,
                    "stage_progress": ["level0_checking", "risk_locking", "normalizing"],
                },
            )
            self.repo.update_status(run_id, "completed", review_status="warn", score_total=None)
            if conv_id:
                append_readiness_result_message(str(conv_id), run_id, self.repo)
        else:
            self.repo.append_stage(run_id, "model_judging")
            self.repo.append_stage(run_id, "aggregating")
            _set_report_json(
                self.repo,
                run_id,
                {
                    "gaps": [],
                    "required_actions": [],
                    "security_status": "passed",
                    "skill_summary": {"highlights": "formal ok"},
                    "stage_progress": ["model_judging", "aggregating"],
                },
            )
            self.repo.update_status(run_id, "completed", review_status="pass", score_total=91.2)
            if conv_id:
                append_rich_report_message(str(conv_id), run_id, self.repo)

    import skillhub_eval.adapters.api.routes.conversations as conversations_route
    import skillhub_eval.core.engine as engine_module

    monkeypatch.setattr(conversations_route.EvaluationEngine, "run_async", _fast_run_async)
    monkeypatch.setattr(engine_module.EvaluationEngine, "run_async", _fast_run_async)

    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: MagicMock()
    app.dependency_overrides[get_gemini_provider] = lambda: MagicMock()
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, repo, tmp_path


def _bootstrap_skill_only(client: TestClient, conv_id: str, *, with_category: bool = True):
    return client.post(
        f"/conversations/{conv_id}/bootstrap",
        data={"skill_id": "grill-me", "source": "upload"},
        files={
            "bundle_zip": (
                "grill-me.zip",
                _zip_skill_only(with_category=with_category),
                "application/zip",
            )
        },
    )


def test_skill_only_zip_shows_plan_without_propagation_or_run(client_with_repo):
    client, repo, tmp_path = client_with_repo
    conv_id = client.post("/conversations/new").json()["conversation_id"]

    resp = _bootstrap_skill_only(client, conv_id, with_category=True)
    assert resp.status_code == 202
    body = resp.json()
    assert body["run_id"] is None
    assert body["propagation_deferred"] is True
    assert body["status"] == "awaiting_propagation_confirm"

    messages = repo.get_lui_messages(conv_id)
    assert any(m.get("message_type") == "assessment_gate_result" for m in messages)
    plan_msgs = [m for m in messages if m.get("message_type") == "propagation_plan"]
    assert len(plan_msgs) == 1
    payload = plan_msgs[0]["payload_json"]
    assert payload is not None
    assert payload.get("rows") is not None

    assert _run_count(repo, conv_id) == 0
    staging = tmp_path / "staging" / conv_id
    assert not (staging / "eval_cases").exists()
    assert not (staging / "sample_io").exists()


def test_confirm_generates_files_summary_and_formal_without_degraded_readiness(client_with_repo):
    client, repo, tmp_path = client_with_repo
    conv_id = client.post("/conversations/new").json()["conversation_id"]
    resp = _bootstrap_skill_only(client, conv_id, with_category=True)
    assert resp.status_code == 202

    async def _fake_propagate(
        self,
        *,
        skill_md_text,
        risk_level,
        category_slug,
        staging_path,
        gap_by_type,
        clarifications,
    ):
        case_ids = ["prop_happy_001", "prop_happy_002", "prop_happy_003"]
        _write_case_files(staging_path, case_ids)
        return PropagatorResult(cases_written=case_ids, cases_failed=[], used_fallback=False)

    with patch(
        "skillhub_eval.adapters.api.routes.chat.CasePropagator.propagate",
        new=_fake_propagate,
    ):
        confirm = client.post(f"/conversations/{conv_id}/chat", json={"message": "确认"})

    assert confirm.status_code == 200
    run_id = confirm.json()["new_run_id"]
    assert run_id

    run = repo.get_run(run_id)
    assert run is not None
    assert run["evaluation_mode"] == "capability_full"

    messages = repo.get_lui_messages(conv_id)
    assert any(m.get("message_type") == "propagation_summary" for m in messages)
    assert any(m.get("message_type") == "assessment_gate_result" for m in messages)
    assert not any(m.get("message_type") == "readiness_result" for m in messages)

    staging = Path(tmp_path / "staging" / conv_id)
    assert (staging / "eval_cases" / "prop_happy_001.yaml").exists()
    assert (staging / "sample_io" / "prop_happy_001.json").exists()


def test_dialog_choice_enters_propagation_dialogue_fork(client_with_repo):
    client, repo, _ = client_with_repo
    conv_id = client.post("/conversations/new").json()["conversation_id"]
    resp = _bootstrap_skill_only(client, conv_id, with_category=True)
    assert resp.status_code == 202

    chat = client.post(f"/conversations/{conv_id}/chat", json={"message": "帮我在对话里补"})
    assert chat.status_code == 200
    assert chat.json()["bootstrap_status"] == "awaiting_propagation_dialogue"
    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["status"] == "awaiting_propagation_dialogue"
    messages = repo.get_lui_messages(conv_id)
    assert any(m.get("message_type") == "propagation_fork" for m in messages)


def test_missing_category_enters_clarify_before_propagation(client_with_repo):
    client, repo, _ = client_with_repo
    conv_id = client.post("/conversations/new").json()["conversation_id"]

    resp = _bootstrap_skill_only(client, conv_id, with_category=False)
    assert resp.status_code == 202
    body = resp.json()
    assert body["run_id"] is None
    assert body["status"] == "awaiting_propagation_clarify"

    plan = next(
        m for m in repo.get_lui_messages(conv_id) if m.get("message_type") == "propagation_plan"
    )
    payload = plan["payload_json"] or {}
    assert payload.get("l0_questions")


def test_formal_pass_card_has_verdict_and_history_hides_degraded(client_with_repo):
    client, repo, tmp_path = client_with_repo
    conv_id = client.post("/conversations/new").json()["conversation_id"]
    resp = _bootstrap_skill_only(client, conv_id, with_category=True)
    assert resp.status_code == 202

    async def _fake_propagate(
        self,
        *,
        skill_md_text,
        risk_level,
        category_slug,
        staging_path,
        gap_by_type,
        clarifications,
    ):
        case_ids = ["prop_happy_001", "prop_happy_002", "prop_happy_003"]
        _write_case_files(staging_path, case_ids)
        return PropagatorResult(cases_written=case_ids, cases_failed=[], used_fallback=False)

    with patch(
        "skillhub_eval.adapters.api.routes.chat.CasePropagator.propagate",
        new=_fake_propagate,
    ):
        first = client.post(f"/conversations/{conv_id}/chat", json={"message": "确认"})
    assert first.status_code == 200
    formal_run = first.json()["new_run_id"]
    assert formal_run

    run = repo.get_run(formal_run)
    assert run is not None
    assert run["evaluation_mode"] == "capability_full"

    rich = [
        m
        for m in repo.get_lui_messages(conv_id)
        if m.get("message_type") == "rich_report" and str(m.get("run_id")) == formal_run
    ]
    assert len(rich) == 1
    payload = rich[0]["payload_json"] or {}
    assert payload.get("verdict_zh") == "通过"
    assert payload.get("next_action_zh")
    actions = payload.get("actions") or []
    assert any(a.get("id") == "openRunDetail" for a in actions)

    history_resp = client.get("/eval/history?limit=20")
    assert history_resp.status_code == 200
    runs = history_resp.json()["runs"]
    visible_runs = [r for r in runs if r.get("evaluation_mode") != "degraded"]
    visible_ids = {r["run_id"] for r in visible_runs}
    assert formal_run in visible_ids
