"""Build execution parsing results from normalized agent events."""

from __future__ import annotations

from typing import Any

from skillhub_eval.core.schemas.report import ParsedStream
from skillhub_eval.execution.events import AgentEvent, AgentEventType, ToolResultPayload


def parsed_stream_from_events(events: list[AgentEvent]) -> ParsedStream:
    final_text_parts: list[str] = []
    tool_results: list[dict[str, Any]] = []
    usage: dict[str, Any] | None = None
    duration_ms: int | None = None
    is_complete = False
    is_error = False
    error_text: str | None = None

    for event in events:
        payload = _payload_dict(event.payload)

        if event.type == AgentEventType.TEXT_DELTA:
            text = payload.get("text") or payload.get("delta") or ""
            if isinstance(text, str) and text:
                final_text_parts.append(text)
        elif event.type == AgentEventType.TOOL_RESULT:
            tool_results.append(payload)
        elif event.type == AgentEventType.USAGE:
            raw_usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else payload
            usage = dict(raw_usage)
        elif event.type == AgentEventType.DONE:
            if payload.get("duration_ms") is not None:
                duration_ms = int(payload["duration_ms"])
            if payload.get("usage") is not None and isinstance(payload["usage"], dict):
                usage = dict(payload["usage"])
            if payload.get("is_error"):
                is_error = True
                error_text = _extract_error_text(payload) or error_text
            else:
                _append_terminal_text(final_text_parts, payload)
                is_complete = True
        elif event.type == AgentEventType.ERROR:
            is_error = True
            error_text = _extract_error_text(payload) or error_text

    return ParsedStream(
        final_text="".join(final_text_parts),
        tool_results=tool_results,
        usage=usage,
        duration_ms=duration_ms,
        is_complete=is_complete and not is_error,
        is_error=is_error,
        error_text=error_text,
    )


def _payload_dict(payload: dict[str, Any] | ToolResultPayload) -> dict[str, Any]:
    if isinstance(payload, ToolResultPayload):
        return payload.to_dict()
    return dict(payload)


def _extract_error_text(payload: dict[str, Any]) -> str | None:
    raw = payload.get("error_text") or payload.get("error") or payload.get("message")
    return raw if isinstance(raw, str) and raw else None


def _append_terminal_text(final_text_parts: list[str], payload: dict[str, Any]) -> None:
    raw = payload.get("result") or payload.get("text")
    if not isinstance(raw, str) or not raw:
        return
    final_text_parts.append(raw)
