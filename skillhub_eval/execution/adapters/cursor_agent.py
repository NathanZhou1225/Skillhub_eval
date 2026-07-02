"""Cursor Agent CLI adapter (open-design compatible args)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from skillhub_eval.execution.cli_detect import find_cli_binary


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
        from skillhub_eval.core.schemas.report import ParsedStream

        state: dict = {}
        text_parts: list[str] = []
        tool_results: list[dict] = []
        usage = None
        duration_ms = None
        is_complete = False
        is_error = False
        error_text: str | None = None
        result_text: str | None = None

        import json

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
                        text_parts.append(delta)
            elif event_type == "assistant":
                # Real cursor-agent nests per-token text under message.content[],
                # not a top-level `text`/`delta` field.
                content = ((event.get("message") or {}).get("content")) or []
                for block in content:
                    if isinstance(block, dict) and isinstance(block.get("text"), str):
                        delta = _emit_cursor_text_delta(block["text"], state)
                        if delta:
                            text_parts.append(delta)
            elif event_type == "tool_result":
                tool_results.append(event)
            elif event_type == "tool_call":
                normalized = _normalize_tool_call_event(event)
                if normalized is not None:
                    tool_results.append(normalized)
            elif event_type == "result":
                if event.get("is_error"):
                    is_error = True
                    raw_error = event.get("error") or event.get("message")
                    if isinstance(raw_error, str) and raw_error:
                        error_text = raw_error
                else:
                    is_complete = True
                    raw_result = event.get("result")
                    if isinstance(raw_result, str) and raw_result:
                        result_text = raw_result
                if isinstance(event.get("usage"), dict):
                    usage = event["usage"]
                if event.get("duration_ms") is not None:
                    duration_ms = int(event["duration_ms"])

        final_text = result_text if result_text is not None else "".join(text_parts)
        return ParsedStream(
            final_text=final_text,
            tool_results=tool_results,
            usage=usage,
            duration_ms=duration_ms,
            is_complete=is_complete,
            is_error=is_error,
            error_text=error_text,
        )
