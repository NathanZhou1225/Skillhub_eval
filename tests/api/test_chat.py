from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.schemas.enums import RunStatus
from skillhub_eval.persistence.sqlite import SqliteRepository


class _FakeProvider:
    async def judge(self, prompt: str) -> dict:
        return {"intent": "explain_only", "reply": "ok", "patch": None}


def _write_case(path: Path, case_id: str, case_type: str = "happy_path") -> None:
    payload = {
        "id": case_id,
        "type": case_type,
        "user_intent": "intent",
        "input_template": "input",
        "expected_behavior": "behavior",
    }
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _build_bundle(root: Path, *, n_cases: int = 3) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        "---\n"
        "id: demo.skill\n"
        "name: demo.skill\n"
        "risk_level: low\n"
        "description: demo\n"
        "category: document.docx\n"
        "negative_prompts: np\n"
        "error_handling: eh\n"
        "permission_scope: ps\n"
        "security_notes: sn\n"
        "---\n"
        "# Demo\n",
        encoding="utf-8",
    )
    eval_cases = root / "eval_cases"
    eval_cases.mkdir(parents=True, exist_ok=True)
    (root / "sample_io").mkdir(parents=True, exist_ok=True)
    for i in range(n_cases):
        case_id = f"case_{i:02d}"
        _write_case(eval_cases / f"{case_id}.yaml", case_id)
        (root / "sample_io" / f"{case_id}.json").write_text(
            '{"input": "x", "output": "y"}',
            encoding="utf-8",
        )
    return root


@pytest.fixture()
def client_with_repo(tmp_path):
    db_path = str(tmp_path / "chat.db")
    repo = SqliteRepository(db_path)
    repo.init_db()
    provider = _FakeProvider()

    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: provider
    app.dependency_overrides[get_gemini_provider] = lambda: provider
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, repo, tmp_path


def test_chat_returns_403_when_conversation_frozen(client_with_repo):
    client, repo, tmp_path = client_with_repo
    staging = _build_bundle(tmp_path / "bundle")
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    repo.update_conversation_status(conv_id, "frozen")
    repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )

    resp = client.post(f"/conversations/{conv_id}/chat", json={"message": "hello"})

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "CONVERSATION_FROZEN"


def test_chat_returns_409_when_active_run_is_running(client_with_repo):
    client, repo, tmp_path = client_with_repo
    staging = _build_bundle(tmp_path / "bundle")
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )

    resp = client.post(f"/conversations/{conv_id}/chat", json={"message": "hello"})

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "SESSION_LOCKED"


def test_chat_normal_message_persists_messages_and_reply(client_with_repo):
    client, repo, tmp_path = client_with_repo
    staging = _build_bundle(tmp_path / "bundle")
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, RunStatus.completed.value)

    fake_lui = MagicMock()
    fake_lui.respond = AsyncMock(
        return_value=SimpleNamespace(intent="explain_only", reply="assistant reply", patch=None)
    )

    with patch("skillhub_eval.adapters.api.routes.chat.LuiAgent", return_value=fake_lui):
        resp = client.post(f"/conversations/{conv_id}/chat", json={"message": "help me"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "assistant reply"
    assert body["intent"] == "explain_only"
    msgs = repo.get_lui_messages(conv_id)
    assert [m["role"] for m in msgs] == ["user", "agent"]
    assert msgs[0]["content"] == "help me"
    assert msgs[1]["content"] == "assistant reply"


def test_chat_confirm_all_triggers_next_run_and_sets_auto_confirmed(client_with_repo):
    client, repo, tmp_path = client_with_repo
    staging = _build_bundle(tmp_path / "bundle")
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, RunStatus.completed.value)

    fake_lui = MagicMock()
    fake_lui.respond = AsyncMock(
        return_value=SimpleNamespace(
            intent="system_action",
            reply="confirmed",
            patch=None,
        )
    )
    fake_writer = MagicMock()
    fake_writer.trigger_next_run = AsyncMock(return_value="run-next-1")
    fake_writer.apply_patch.return_value = SimpleNamespace(hash_changed=False)

    with (
        patch("skillhub_eval.adapters.api.routes.chat.LuiAgent", return_value=fake_lui),
        patch("skillhub_eval.adapters.api.routes.chat.StagingWriter", return_value=fake_writer),
    ):
        resp = client.post(
            f"/conversations/{conv_id}/chat",
            json={"message": "__SYSTEM_ACTION_CONFIRM_ALL__"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["new_run_id"] == "run-next-1"
    assert body["auto_confirmed"] is True
    assert body["gap_zero"] is True
    conv = repo.get_conversation(conv_id)
    assert conv is not None and conv["auto_confirmed"] == 1
    fake_writer.trigger_next_run.assert_called_once()


def test_confirm_cases_writes_yaml_without_triggering_new_run(client_with_repo):
    client, repo, tmp_path = client_with_repo
    staging = _build_bundle(tmp_path / "bundle")
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(staging),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, RunStatus.completed.value)

    resp = client.post(
        f"/conversations/{conv_id}/confirm-cases",
        json={"case_ids": ["case_00", "case_01"]},
    )

    assert resp.status_code == 200
    assert resp.json()["updated"] == ["case_00", "case_01"]
    raw0 = yaml.safe_load((staging / "eval_cases" / "case_00.yaml").read_text(encoding="utf-8"))
    raw1 = yaml.safe_load((staging / "eval_cases" / "case_01.yaml").read_text(encoding="utf-8"))
    assert raw0["confirmed"] is True
    assert raw1["confirmed"] is True
    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert conv["active_run_id"] == run_id


def test_get_messages_returns_ordered_messages(client_with_repo):
    client, repo, _ = client_with_repo
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    repo.append_lui_message(conv_id, role="user", content="u1")
    repo.append_lui_message(conv_id, role="agent", content="a1")
    repo.append_lui_message(conv_id, role="user", content="u2")

    resp = client.get(f"/conversations/{conv_id}/messages")

    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation_id"] == conv_id
    assert [m["content"] for m in body["messages"]] == ["u1", "a1", "u2"]


def test_get_status_reports_gap_zero_correctly(client_with_repo):
    client, repo, tmp_path = client_with_repo
    bundle = _build_bundle(tmp_path / "bundle", n_cases=3)
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(bundle),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, RunStatus.completed.value)
    repo.append_lui_message(conv_id, role="user", content="hello")

    resp_ok = client.get(f"/conversations/{conv_id}/status")
    assert resp_ok.status_code == 200
    body_ok = resp_ok.json()
    assert body_ok["gap_zero"] is True
    assert body_ok["case_gate_passed"] is True
    assert body_ok["lui_messages_count"] == 1

    # Make gaps non-zero: remove one case (low risk needs >=3)
    (bundle / "eval_cases" / "case_02.yaml").unlink()
    resp_gap = client.get(f"/conversations/{conv_id}/status")
    assert resp_gap.status_code == 200
    body_gap = resp_gap.json()
    assert body_gap["gap_zero"] is False
    assert body_gap["case_gate_passed"] is False


def test_get_status_skips_bundle_scan_while_run_is_active(client_with_repo, monkeypatch):
    client, repo, tmp_path = client_with_repo
    bundle = _build_bundle(tmp_path / "bundle", n_cases=3)
    conv_id = repo.create_conversation("demo.skill", "local_ref")
    run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path=str(bundle),
        bundle_state="draft_enriched",
        evaluation_mode="degraded",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, RunStatus.case_executing.value)
    repo.append_lui_message(conv_id, role="user", content="hello")

    def fail_ingest(_path: str):
        raise AssertionError("status polling must not rescan bundles while a run is active")

    monkeypatch.setattr("skillhub_eval.adapters.api.routes.chat.ingest_bundle", fail_ingest)

    resp = client.get(f"/conversations/{conv_id}/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["run_status"] == RunStatus.case_executing.value
    assert body["lui_messages_count"] == 1
    assert body["gap_zero"] is False
    assert body["case_gate_passed"] is False
