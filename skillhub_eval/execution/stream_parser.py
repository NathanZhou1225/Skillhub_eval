"""Stream-json parsing and artifact collection for local agent runs."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from skillhub_eval.core.schemas.report import ParsedStream


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def parse_stream_events(lines: Iterable[str]) -> ParsedStream:
    """Parse generic stream-json lines into a ParsedStream."""
    final_text_parts: list[str] = []
    tool_results: list[dict] = []
    usage: dict | None = None
    duration_ms: int | None = None
    is_complete = False

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue

        event_type = event.get("type")
        if event_type in ("text", "assistant"):
            delta = event.get("delta") or event.get("text") or ""
            if isinstance(delta, str) and delta:
                final_text_parts.append(delta)
        elif event_type == "tool_result":
            tool_results.append(event)
        elif event_type == "result":
            is_complete = True
            if isinstance(event.get("usage"), dict):
                usage = event["usage"]
            if event.get("duration_ms") is not None:
                duration_ms = int(event["duration_ms"])
            result_text = event.get("result") or event.get("text")
            if isinstance(result_text, str) and result_text:
                final_text_parts.append(result_text)

    return ParsedStream(
        final_text= "".join(final_text_parts),
        tool_results=tool_results,
        usage=usage,
        duration_ms=duration_ms,
        is_complete=is_complete,
    )


def extract_fenced_json(text: str) -> dict | None:
    """Best-effort parse of a trailing fenced JSON block from agent text."""
    match = _FENCED_JSON_RE.search(text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def collect_actual_output(
    parsed: ParsedStream,
    cwd_artifacts: list[dict] | None = None,
) -> dict[str, Any]:
    """Synthesize actual_output dict from stream + optional cwd artifacts."""
    structured = extract_fenced_json(parsed.final_text)
    if structured is not None:
        return structured

    payload: dict[str, Any] = {}
    if parsed.final_text:
        payload["text"] = parsed.final_text
    if parsed.tool_results:
        payload["tool_results"] = parsed.tool_results
    if cwd_artifacts:
        payload["artifacts"] = cwd_artifacts
    return payload
