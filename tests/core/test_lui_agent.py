import json
from pathlib import Path

import pytest

from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.providers.base import BaseLLMProvider


class _NoCallProvider(BaseLLMProvider):
    async def judge(self, prompt: str) -> dict:
        raise AssertionError("provider should not be called")


class _RawProvider(BaseLLMProvider):
    def __init__(self, raw: str):
        self.raw = raw

    async def judge(self, prompt: str) -> dict:
        return self.raw  # type: ignore[return-value]


def _make_repo(tmp_path: Path) -> SqliteRepository:
    repo = SqliteRepository(str(tmp_path / "lui_agent.db"))
    repo.init_db()
    return repo


def _make_staging_bundle(tmp_path: Path) -> Path:
    staging = tmp_path / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "SKILL.md").write_text(
        "---\nname: sample\nid: sample.skill\nrisk_level: low\ndescription: desc\n---\n# body\n",
        encoding="utf-8",
    )
    (staging / "eval_cases").mkdir(exist_ok=True)
    for i in range(3):
        (staging / "eval_cases" / f"case_{i:02d}.yaml").write_text(
            f"id: case_{i:02d}\ntype: happy_path\nuser_intent: intent {i}\n",
            encoding="utf-8",
        )
    return staging


@pytest.mark.asyncio
async def test_frozen_conversation_returns_explain_only(tmp_path: Path):
    from skillhub_eval.core.lui_agent import LuiAgent

    agent = LuiAgent(ds_provider=_NoCallProvider())
    resp = await agent.respond(
        conversation_id="conv-1",
        user_message="帮我改一下",
        history=[],
        report={"security_status": "passed"},
        conv={"status": "frozen"},
        repo=_make_repo(tmp_path),
    )
    assert resp.intent == "explain_only"
    assert resp.patch is None


@pytest.mark.asyncio
async def test_trigger_agent_opening_is_idempotent(tmp_path: Path):
    from skillhub_eval.core.lui_agent import LuiAgent

    repo = _make_repo(tmp_path)
    conv_id = repo.create_conversation(skill_id="skill-a", source="upload")
    report = {
        "skill_summary": {"highlights": "覆盖面好", "weaknesses": "缺少边界"},
        "security_status": "warning",
        "gaps": [{"severity": "required"}, {"severity": "warn"}],
    }
    agent = LuiAgent(ds_provider=_NoCallProvider())

    first = await agent.respond(
        conversation_id=conv_id,
        user_message="__TRIGGER_AGENT_OPENING__",
        history=[],
        report=report,
        conv={"status": "active"},
        repo=repo,
    )
    second = await agent.respond(
        conversation_id=conv_id,
        user_message="__TRIGGER_AGENT_OPENING__",
        history=[],
        report=report,
        conv={"status": "active"},
        repo=repo,
    )

    msgs = repo.get_lui_messages(conv_id)
    agent_msgs = [m for m in msgs if m["role"] == "agent"]
    assert first.intent == "system_action"
    assert first.reply != ""
    assert "覆盖面好" in first.reply
    assert len(agent_msgs) == 1
    assert second.intent == "system_action"
    assert second.reply == ""


@pytest.mark.asyncio
async def test_confirm_all_with_required_gaps_refuses_and_keeps_unconfirmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from skillhub_eval.core import lui_agent as lui_agent_module
    from skillhub_eval.core.lui_agent import LuiAgent

    repo = _make_repo(tmp_path)
    conv_id = repo.create_conversation(skill_id="skill-a", source="upload")
    staging = _make_staging_bundle(tmp_path)

    def _fake_scan_gaps(bundle: dict, bundle_state):  # noqa: ANN001
        return {"gaps": [{"severity": "required", "field_path": "x"}]}

    monkeypatch.setattr(lui_agent_module, "scan_gaps", _fake_scan_gaps)
    agent = LuiAgent(ds_provider=_NoCallProvider())
    resp = await agent.respond(
        conversation_id=conv_id,
        user_message="__SYSTEM_ACTION_CONFIRM_ALL__",
        history=[],
        report={},
        conv={"status": "active"},
        repo=repo,
        staging_path=staging,
    )

    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert resp.intent == "explain_only"
    assert conv["auto_confirmed"] == 0


@pytest.mark.asyncio
async def test_confirm_all_gap_zero_sets_auto_confirmed(tmp_path: Path):
    from skillhub_eval.core.lui_agent import LuiAgent

    repo = _make_repo(tmp_path)
    conv_id = repo.create_conversation(skill_id="skill-a", source="upload")
    staging = _make_staging_bundle(tmp_path)
    agent = LuiAgent(ds_provider=_NoCallProvider())

    resp = await agent.respond(
        conversation_id=conv_id,
        user_message="__SYSTEM_ACTION_CONFIRM_ALL__",
        history=[],
        report={},
        conv={"status": "active"},
        repo=repo,
        staging_path=staging,
    )

    conv = repo.get_conversation(conv_id)
    assert conv is not None
    assert resp.intent == "system_action"
    assert conv["auto_confirmed"] == 1


@pytest.mark.asyncio
async def test_llm_bad_json_falls_back_to_explain_only(tmp_path: Path):
    from skillhub_eval.core.lui_agent import LuiAgent

    repo = _make_repo(tmp_path)
    conv_id = repo.create_conversation(skill_id="skill-a", source="upload")
    agent = LuiAgent(ds_provider=_RawProvider("not-json"))

    resp = await agent.respond(
        conversation_id=conv_id,
        user_message="解释一下这个分数",
        history=[],
        report={"security_status": "passed"},
        conv={"status": "active"},
        repo=repo,
    )
    assert resp.intent == "explain_only"
    assert resp.patch is None


@pytest.mark.asyncio
async def test_mutation_intent_patch_has_eval_cases_without_sample_io(tmp_path: Path):
    from skillhub_eval.core.lui_agent import LuiAgent

    repo = _make_repo(tmp_path)
    conv_id = repo.create_conversation(skill_id="skill-a", source="upload")
    payload = {
        "intent": "mutation",
        "reply": "我帮你补一条 edge case。",
        "patch": {
            "skill_md_updates": {"category": "fin-research/quant-signal"},
            "eval_cases": [
                {
                    "type": "edge",
                    "user_intent": "边界输入",
                    "input_template": "输入为空",
                    "expected_behavior": "提示参数缺失",
                }
            ],
            "sample_io": [{"case_id": "x", "input": "a", "output": "b"}],
        },
    }
    agent = LuiAgent(ds_provider=_RawProvider(json.dumps(payload, ensure_ascii=False)))

    resp = await agent.respond(
        conversation_id=conv_id,
        user_message="帮我补一条 edge case",
        history=[],
        report={},
        conv={"status": "active"},
        repo=repo,
    )
    assert resp.intent == "mutation"
    assert resp.patch is not None
    assert "eval_cases" in resp.patch
    assert "sample_io" not in resp.patch


@pytest.mark.asyncio
async def test_awaiting_draft_confirm_returns_stored_patch_on_confirm(tmp_path: Path):
    from skillhub_eval.core.lui_agent import LuiAgent

    repo = _make_repo(tmp_path)
    conv_id = repo.create_conversation(skill_id="skill-a", source="upload")
    pending = {"skill_md_updates": {"description": "from-pending"}}
    repo.set_pending_patch(conv_id, pending)

    agent = LuiAgent(ds_provider=_NoCallProvider())
    resp = await agent.respond(
        conversation_id=conv_id,
        user_message="确认",
        history=[],
        report={"gaps": []},
        conv={"status": "awaiting_draft_confirm"},
        repo=repo,
        staging_path=_make_staging_bundle(tmp_path),
    )
    assert resp.intent == "mutation"
    assert resp.patch == pending
