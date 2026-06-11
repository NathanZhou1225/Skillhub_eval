import json
from pathlib import Path

import pytest

from skillhub_eval.core.lui_agent import LuiAgent, _UI_S2_CLARIFY_RULE
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.providers.base import BaseLLMProvider


class _CapturingProvider(BaseLLMProvider):
    def __init__(self, raw: str):
        self.raw = raw
        self.last_prompt: str | None = None

    async def judge(self, prompt: str) -> dict:
        self.last_prompt = prompt
        return self.raw  # type: ignore[return-value]


class _ClarifyProvider(BaseLLMProvider):
    async def judge(self, prompt: str) -> dict:
        return {
            "intent": "clarify",
            "reply": "请说明 Skill 的目标受众是谁？",
            "patch": {"skill_md_updates": {"description": "should be dropped"}},
            "clarification_keys": ["audience", "success_output_shape"],
        }


def _make_repo(tmp_path: Path) -> SqliteRepository:
    repo = SqliteRepository(str(tmp_path / "clarify.db"))
    repo.init_db()
    return repo


@pytest.mark.asyncio
async def test_llm_clarify_intent_strips_patch_and_sets_keys(tmp_path: Path):
    repo = _make_repo(tmp_path)
    conv_id = repo.create_conversation(skill_id="skill-a", source="upload")
    agent = LuiAgent(ds_provider=_ClarifyProvider())

    resp = await agent.respond(
        conversation_id=conv_id,
        user_message="这个 Skill 到底是干什么的？",
        history=[],
        report={"security_status": "passed"},
        conv={"status": "active"},
        repo=repo,
    )

    assert resp.intent == "clarify"
    assert resp.patch is None
    assert resp.clarification_keys == ["audience", "success_output_shape"]


def test_build_prompt_contains_ui_s2_mutation_block_rule():
    agent = LuiAgent(ds_provider=_ClarifyProvider())
    prompt = agent._build_prompt(
        user_message="帮我改描述",
        history=[],
        report={},
        clarifications={"purpose": "量化信号"},
    )

    assert _UI_S2_CLARIFY_RULE in prompt
    assert "intent=clarify" in prompt
    assert "禁止 mutation" in prompt
    assert "purpose" in prompt
    assert "量化信号" in prompt


@pytest.mark.asyncio
async def test_respond_injects_clarifications_json_from_repo(tmp_path: Path):
    repo = _make_repo(tmp_path)
    conv_id = repo.create_conversation(skill_id="skill-a", source="upload")
    repo.merge_clarifications(conv_id, {"category": "fin-research/quant-signal"})
    provider = _CapturingProvider(
        json.dumps({"intent": "explain_only", "reply": "好的", "patch": None})
    )
    agent = LuiAgent(ds_provider=provider)

    await agent.respond(
        conversation_id=conv_id,
        user_message="解释一下",
        history=[],
        report={},
        conv={"status": "active"},
        repo=repo,
    )

    assert provider.last_prompt is not None
    assert "fin-research/quant-signal" in provider.last_prompt
    assert "已有澄清:" in provider.last_prompt


@pytest.mark.asyncio
async def test_clarify_json_from_string_provider(tmp_path: Path):
    repo = _make_repo(tmp_path)
    conv_id = repo.create_conversation(skill_id="skill-a", source="upload")
    payload = {
        "intent": "clarify",
        "reply": "用途与 SKILL.md 不一致，请确认主要场景。",
        "patch": None,
        "clarification_keys": ["intent_source"],
    }
    agent = LuiAgent(
        ds_provider=_CapturingProvider(json.dumps(payload, ensure_ascii=False))
    )

    resp = await agent.respond(
        conversation_id=conv_id,
        user_message="这是客服助手",
        history=[{"role": "user", "content": "帮我做投研分析"}],
        report={"gaps": []},
        conv={"status": "active"},
        repo=repo,
    )

    assert resp.intent == "clarify"
    assert resp.patch is None
    assert resp.clarification_keys == ["intent_source"]
