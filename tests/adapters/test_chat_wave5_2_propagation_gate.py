"""Wave 5.2 Task 4 — propagation gate chat routing + propagation_summary."""

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
from skillhub_eval.core.propagator import PropagatorResult
from skillhub_eval.persistence.sqlite import SqliteRepository


def _make_zip_bytes(*, skill_md: str) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", skill_md)
    return buffer.getvalue(), "bundle.zip"


def _sample_plan(*, plan_version: int = 1, l0_questions: list | None = None) -> dict:
    return {
        "risk_level_declared": "low",
        "existing_counts": {"happy_path": 0},
        "gap_by_type": {"happy_path": 2, "edge": 1},
        "broken_moved": 0,
        "sample_io_gap": True,
        "plan_version": plan_version,
        "rows": [],
        "l0_questions": l0_questions or [],
        "headline_zh": "尚缺评估题",
        "clarifications_applied": {},
    }


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


def _seed_propagation_confirm(
    repo: SqliteRepository,
    tmp_path,
    *,
    status: str = "awaiting_propagation_confirm",
    plan: dict | None = None,
) -> str:
    conv_id = repo.create_conversation(skill_id="grill-me-skill", source="upload")
    staging = tmp_path / "staging" / conv_id
    staging.mkdir(parents=True)
    (staging / "SKILL.md").write_text(
        "---\n"
        "name: grill-me-skill\n"
        "description: 这是一个用于测试 propagation gate 的 Skill，描述足够长以满足 L0 门槛。\n"
        "risk_level: low\n"
        "category: fin-research/quant-signal\n"
        "---\n"
        "# Grill Me Skill\n\n"
        "本 Skill 用于验证补题确认流程：用户在看到 propagation_plan 后可选择确认、"
        "手动补题或对话协作补题。成功输出通常为结构化 Markdown 报告。\n",
        encoding="utf-8",
    )
    repo.update_conversation_status(conv_id, status)
    repo.append_lui_message(
        conv_id,
        role="agent",
        content="补题计划",
        message_type="propagation_plan",
        payload_json=plan or _sample_plan(),
    )
    return conv_id


@pytest.fixture()
def client_with_repo(tmp_path, monkeypatch):
    repo = SqliteRepository(str(tmp_path / "wave5_2_prop_gate.db"))
    repo.init_db()
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: MagicMock()
    app.dependency_overrides[get_gemini_provider] = lambda: MagicMock()

    async def _noop_run_async(self, *args, **kwargs):
        return None

    import skillhub_eval.adapters.api.routes.conversations as conversations_route
    import skillhub_eval.core.engine as engine_module

    with (
        patch.object(conversations_route.EvaluationEngine, "run_async", _noop_run_async),
        patch.object(engine_module.EvaluationEngine, "run_async", _noop_run_async),
    ):
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client, repo


def test_confirm_propagates_then_creates_run(client_with_repo, tmp_path):
    client, repo = client_with_repo
    conv_id = _seed_propagation_confirm(repo, tmp_path)

    case_ids = ["prop_happy_001", "prop_happy_002", "prop_happy_003"]
    prop_result = PropagatorResult(
        cases_written=case_ids,
        cases_failed=[],
        used_fallback=False,
    )

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
        _write_case_files(staging_path, case_ids)
        return prop_result

    with patch(
        "skillhub_eval.adapters.api.routes.chat.CasePropagator.propagate",
        new=_fake_propagate,
    ):
        resp = client.post(
            f"/conversations/{conv_id}/chat",
            json={"message": "确认"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "system_action"
    assert body["new_run_id"]

    conv = repo.get_conversation(conv_id)
    assert conv["status"] == "active"
    assert conv["active_run_id"] == body["new_run_id"]

    messages = repo.get_lui_messages(conv_id)
    summaries = [m for m in messages if m["message_type"] == "propagation_summary"]
    assert len(summaries) == 1
    payload = summaries[0]["payload_json"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload["cases_written"] == case_ids
    assert payload["n_added"] == 3
    assert payload["files"] == case_ids


def test_manual_upload_choice_sets_status(client_with_repo, tmp_path):
    client, repo = client_with_repo
    conv_id = _seed_propagation_confirm(repo, tmp_path)

    with patch(
        "skillhub_eval.adapters.api.routes.chat.CasePropagator.propagate",
        new_callable=AsyncMock,
    ) as mock_propagate:
        resp = client.post(
            f"/conversations/{conv_id}/chat",
            json={"message": "我自己补"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "explain_only"
    assert body["new_run_id"] is None
    mock_propagate.assert_not_called()

    conv = repo.get_conversation(conv_id)
    assert conv["status"] == "awaiting_manual_upload"
    messages = repo.get_lui_messages(conv_id)
    agent_msgs = [m for m in messages if m["role"] == "agent" and m["message_type"] == "text"]
    assert any("eval_cases" in m["content"] or "YAML" in m["content"] for m in agent_msgs)


def test_dialog_draft_choice_sets_awaiting_propagation_dialogue(client_with_repo, tmp_path):
    client, repo = client_with_repo
    conv_id = _seed_propagation_confirm(repo, tmp_path)

    resp = client.post(
        f"/conversations/{conv_id}/chat",
        json={"message": "帮我在对话里补"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "explain_only"
    conv = repo.get_conversation(conv_id)
    assert conv["status"] == "awaiting_propagation_dialogue"
    messages = repo.get_lui_messages(conv_id)
    fork_msgs = [m for m in messages if m["message_type"] == "propagation_fork"]
    assert len(fork_msgs) >= 1


def test_mutation_blocked_in_awaiting_propagation_confirm(client_with_repo, tmp_path, monkeypatch):
    from skillhub_eval.core.lui_agent import LuiResponse

    client, repo = client_with_repo
    conv_id = _seed_propagation_confirm(repo, tmp_path)

    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.chat.LuiAgent.respond",
        AsyncMock(
            return_value=LuiResponse(
                intent="mutation",
                reply="直接改",
                patch={"skill_md_updates": {"description": "hack"}},
            )
        ),
    )

    resp = client.post(
        f"/conversations/{conv_id}/chat",
        json={"message": "帮我直接改一下描述"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "PROPAGATION_GATE_LOCKED"


def test_reupload_zip_in_manual_upload_refreshes_plan(client_with_repo, tmp_path):
    client, repo = client_with_repo
    conv_id = _seed_propagation_confirm(
        repo, tmp_path, status="awaiting_manual_upload", plan=_sample_plan(plan_version=1)
    )

    skill_md = (
        "---\n"
        "name: grill-me-skill\n"
        "description: 这是一个用于测试 propagation gate 的 Skill，描述足够长以满足 L0 门槛。\n"
        "risk_level: low\n"
        "category: fin-research/quant-signal\n"
        "---\n"
        "# Grill Me Skill\n\n"
        "本 Skill 用于验证补题确认流程：用户在看到 propagation_plan 后可选择确认、"
        "手动补题或对话协作补题。成功输出通常为结构化 Markdown 报告。\n"
    )
    payload, filename = _make_zip_bytes(skill_md=skill_md)

    with patch(
        "skillhub_eval.adapters.api.routes.chat.CasePropagator.propagate",
        new_callable=AsyncMock,
    ) as mock_propagate:
        resp = client.post(
            f"/conversations/{conv_id}/chat",
            files={"bundle_zip": (filename, payload, "application/zip")},
            data={"message": ""},
        )

    assert resp.status_code == 200
    mock_propagate.assert_not_called()
    messages = repo.get_lui_messages(conv_id)
    plan_messages = [m for m in messages if m["message_type"] == "propagation_plan"]
    assert len(plan_messages) >= 2
    latest = plan_messages[-1]["payload_json"]
    if isinstance(latest, str):
        latest = json.loads(latest)
    assert latest.get("plan_version", 1) >= 1
    conv = repo.get_conversation(conv_id)
    assert conv["status"] in ("awaiting_propagation_confirm", "awaiting_propagation_clarify")
