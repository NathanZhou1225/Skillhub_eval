"""Parse multi-key clarification answers — Wave 5.3."""

from __future__ import annotations

import json
import re
from typing import Any

from skillhub_eval.providers.base import BaseLLMProvider

_MD_FENCE_RE = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$", re.IGNORECASE)


def parse_clarification_heuristic(message: str, keys: list[str]) -> dict[str, str]:
    text = message.strip()
    if not text:
        return {}
    for sep in ("：", ":"):
        if sep in text:
            key, _, value = text.partition(sep)
            key = key.strip()
            value = value.strip()
            if key and value:
                return {key: value}
    if len(keys) == 1:
        return {keys[0]: text}
    return {}


def _parse_llm_payload(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ValueError("unsupported")
    text = raw.strip()
    fenced = _MD_FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("not object")
    return parsed


async def parse_clarification_message(
    message: str,
    pending_keys: list[str],
    ds_provider: BaseLLMProvider | None,
) -> dict[str, str]:
    if not message.strip() or not pending_keys:
        return {}
    heuristic = parse_clarification_heuristic(message, pending_keys)
    if heuristic and (len(pending_keys) == 1 or len(heuristic) > 1):
        return heuristic
    if ds_provider is None:
        return heuristic

    keys_json = json.dumps(pending_keys, ensure_ascii=False)
    prompt = (
        "从用户回复中提取澄清字段。输出单个 JSON 对象："
        '{"answers":{"key":"value"}}\n'
        f"待填字段 keys: {keys_json}\n"
        f"用户回复: {message.strip()}\n"
        "只输出 JSON。"
    )
    try:
        raw = await ds_provider.judge(prompt)
        payload = _parse_llm_payload(raw)
        answers = payload.get("answers")
        if not isinstance(answers, dict):
            return heuristic
        cleaned = {
            str(k).strip(): str(v).strip()
            for k, v in answers.items()
            if str(k).strip() in pending_keys and str(v).strip()
        }
        return cleaned or heuristic
    except Exception:
        return heuristic
