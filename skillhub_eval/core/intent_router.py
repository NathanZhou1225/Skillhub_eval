"""Intent routing for chat actions — Wave 5.3."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from skillhub_eval.providers.base import BaseLLMProvider

_MD_FENCE_RE = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.IGNORECASE)

ACTION_PROPAGATE = "propagate"
ACTION_MANUAL_UPLOAD = "manual_upload"
ACTION_DRAFT_MODE = "draft_mode"
ACTION_DRAFT_CONFIRM = "draft_confirm"
ACTION_CONFIRM_SKILL = "confirm_skill"
ACTION_DRAFT_REGENERATE = "draft_regenerate"
ACTION_DRAFT_WRITE_FILE = "draft_write_file"
ACTION_CLARIFY_SCENES = "clarify_scenes_then_propagate"

WHITELIST_ACTIONS = frozenset(
    {
        ACTION_PROPAGATE,
        ACTION_MANUAL_UPLOAD,
        ACTION_DRAFT_MODE,
        ACTION_DRAFT_CONFIRM,
        ACTION_CONFIRM_SKILL,
        ACTION_DRAFT_REGENERATE,
        ACTION_DRAFT_WRITE_FILE,
        ACTION_CLARIFY_SCENES,
    }
)

CONFIDENCE_THRESHOLD = 0.85


@dataclass
class IntentResult:
    action: str | None
    confidence: float
    reply: str


def _parse_payload(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ValueError("unsupported response")
    text = raw.strip()
    fenced = _MD_FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("not object")
    return parsed


class IntentRouter:
    def __init__(self, ds_provider: BaseLLMProvider):
        self.ds_provider = ds_provider

    async def classify(
        self,
        message: str,
        *,
        conversation_status: str,
        history_snippet: list[dict] | None = None,
    ) -> IntentResult:
        history_json = json.dumps((history_snippet or [])[-6:], ensure_ascii=False, default=str)
        prompt = (
            "你是 SkillHub 对话路由助手。根据用户消息和会话状态，判断用户是否想执行某个操作。\n"
            "输出必须是单个 JSON 对象，不允许 markdown 代码块。\n"
            '格式: {"action":null|"propagate"|"manual_upload"|"draft_mode"|"draft_confirm"|'
            '"confirm_skill"|"draft_regenerate"|"draft_write_file"|"clarify_scenes_then_propagate",'
            '"confidence":0.0-1.0,"reply":"给用户的简短中文回复"}\n'
            "规则:\n"
            "1) 不确定时 action=null，confidence<0.85，reply 引导用户点对应按钮。\n"
            "2) 「帮我自动出题/按表出题」→ propagate；「我自己补」→ manual_upload。\n"
            "3) 「对话里补/描述场景」→ draft_mode 或 clarify_scenes_then_propagate。\n"
            "4) reply 不超过120字，使用「评估条件」而非「题型」，且 reply 必须为简体中文。\n"
            f"conversation_status: {conversation_status}\n"
            f"history: {history_json}\n"
            f"user_message: {message}\n"
        )
        try:
            raw = await self.ds_provider.judge(prompt)
            payload = _parse_payload(raw)
            action = payload.get("action")
            if action is not None:
                action = str(action).strip() or None
            if action not in WHITELIST_ACTIONS:
                action = None
            confidence = float(payload.get("confidence", 0.0))
            reply = str(payload.get("reply", "")).strip() or "我先确认一下你的意图。"
            return IntentResult(action=action, confidence=confidence, reply=reply)
        except Exception:
            return IntentResult(
                action=None,
                confidence=0.0,
                reply="我没完全理解你的意思。请点下方按钮，或直接说「确认」「自动出题」。",
            )
