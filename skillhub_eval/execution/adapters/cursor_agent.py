"""Cursor Agent CLI adapter (open-design compatible args)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from skillhub_eval.execution.cli_detect import find_cli_binary


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
            if event_type in ("text", "assistant", "content"):
                chunk = event.get("text") or event.get("delta") or ""
                if isinstance(chunk, str) and chunk:
                    delta = _emit_cursor_text_delta(chunk, state)
                    if delta:
                        text_parts.append(delta)
            elif event_type == "tool_result":
                tool_results.append(event)
            elif event_type == "result":
                is_complete = True
                if isinstance(event.get("usage"), dict):
                    usage = event["usage"]
                if event.get("duration_ms") is not None:
                    duration_ms = int(event["duration_ms"])

        return ParsedStream(
            final_text="".join(text_parts),
            tool_results=tool_results,
            usage=usage,
            duration_ms=duration_ms,
            is_complete=is_complete,
        )
