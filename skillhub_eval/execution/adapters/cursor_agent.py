"""Cursor Agent CLI adapter (open-design compatible args)."""

from __future__ import annotations

import shutil
import json
from dataclasses import dataclass

from skillhub_eval.execution.cli_detect import find_cli_binary
from skillhub_eval.execution.events import AgentEvent, AgentEventType, ToolResultPayload
from skillhub_eval.execution.exec_result_builder import parsed_stream_from_events


def _normalize_tool_call_event(event: dict) -> dict | None:
    """Normalize a real cursor-agent `type: tool_call` event into the flat shape
    verify_entrypoint_evidence() understands (command/stdout/stderr/exit_code).

    Real cursor-agent nests the payload under a tool-specific key (e.g.
    `shellToolCall`), never emits the flat `tool_result` type this adapter used
    to look for exclusively (2026-07-02 real-machine finding).
    """
    if event.get("subtype") != "completed":
        return None
    tool_call = event.get("tool_call")
    if not isinstance(tool_call, dict) or not tool_call:
        return None
    tool_name, payload = next(iter(tool_call.items()))
    if not isinstance(payload, dict):
        return None
    args = payload.get("args") or {}
    result = payload.get("result") or {}
    success = result.get("success") if isinstance(result, dict) else None
    is_error = not isinstance(success, dict)
    return {
        "tool": tool_name,
        "command": args.get("command"),
        "stdout": (success or {}).get("stdout"),
        "stderr": (success or {}).get("stderr"),
        "exit_code": (success or {}).get("exitCode") if success else None,
        "is_error": is_error,
    }


def _emit_cursor_text_delta(text: str, state: dict) -> str:
    """Deduplicate cursor-agent partial text deltas (from open-design)."""
    prev = state.get("cursor_text_so_far", "")
    if not prev:
        state["cursor_text_so_far"] = text
        return text
    if text == prev:
        return ""
    if text.startswith(prev):
        delta = text[len(prev):]
        state["cursor_text_so_far"] = text
        return delta
    state["cursor_text_so_far"] = prev + text
    return text


@dataclass
class CursorAgentAdapter:
    agent_id: str = "cursor-agent"
    bin: str = "cursor-agent"
    model: str | None = None

    def detect(self) -> bool:
        return find_cli_binary(self.bin) is not None

    def resolved_bin(self) -> str:
        return find_cli_binary(self.bin) or self.bin

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        args = [
            "--print",
            "--output-format",
            "stream-json",
            "--stream-partial-output",
            "--force",
            "--trust",
        ]
        if cwd:
            args.extend(["--workspace", cwd])
        if self.model:
            args.extend(["--model", self.model])
        return [self.resolved_bin(), *args]

    def parse_stream(self, lines: list[str]):
        return parsed_stream_from_events(self.normalize_events(lines))

    def normalize_events(self, lines: list[str]) -> list[AgentEvent]:
        state: dict = {}
        events: list[AgentEvent] = []
        text_events: list[AgentEvent] = []
        terminal_event: AgentEvent | None = None
        result_text: str | None = None

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
            if event_type in ("text", "content"):
                chunk = event.get("text") or event.get("delta") or ""
                if isinstance(chunk, str) and chunk:
                    delta = _emit_cursor_text_delta(chunk, state)
                    if delta:
                        text_events.append(AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": delta}))
            elif event_type == "assistant":
                # Real cursor-agent nests per-token text under message.content[],
                # not a top-level `text`/`delta` field.
                content = ((event.get("message") or {}).get("content")) or []
                for block in content:
                    if isinstance(block, dict) and isinstance(block.get("text"), str):
                        delta = _emit_cursor_text_delta(block["text"], state)
                        if delta:
                            text_events.append(AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": delta}))
            elif event_type == "tool_result":
                events.append(AgentEvent(type=AgentEventType.TOOL_RESULT, payload=event))
            elif event_type == "tool_call":
                normalized = _normalize_tool_call_event(event)
                if normalized is not None:
                    events.append(AgentEvent(type=AgentEventType.TOOL_RESULT, payload=_tool_result_payload(normalized)))
            elif event_type == "result":
                if event.get("is_error"):
                    raw_error = event.get("error") or event.get("message")
                    if isinstance(event.get("usage"), dict):
                        events.append(AgentEvent(type=AgentEventType.USAGE, payload=event["usage"]))
                    payload = {"is_error": True, "duration_ms": event.get("duration_ms")}
                    if isinstance(raw_error, str) and raw_error:
                        payload["error_text"] = raw_error
                    terminal_event = AgentEvent(type=AgentEventType.DONE, payload=payload)
                else:
                    raw_result = event.get("result")
                    if isinstance(raw_result, str) and raw_result:
                        result_text = raw_result
                    payload = {"duration_ms": event.get("duration_ms")}
                    if isinstance(event.get("usage"), dict):
                        events.append(AgentEvent(type=AgentEventType.USAGE, payload=event["usage"]))
                    if result_text is not None:
                        payload["result"] = result_text
                    terminal_event = AgentEvent(type=AgentEventType.DONE, payload=payload)

        if result_text is None:
            events.extend(text_events)
        if terminal_event is not None:
            events.append(terminal_event)
        return events


def _tool_result_payload(raw: dict) -> ToolResultPayload:
    return ToolResultPayload(
        tool=str(raw.get("tool") or ""),
        command=raw.get("command") if isinstance(raw.get("command"), str) else None,
        stdout=raw.get("stdout") if isinstance(raw.get("stdout"), str) else "",
        stderr=raw.get("stderr") if isinstance(raw.get("stderr"), str) else "",
        exit_code=raw.get("exit_code") if isinstance(raw.get("exit_code"), int) else None,
        is_error=bool(raw.get("is_error")),
    )
