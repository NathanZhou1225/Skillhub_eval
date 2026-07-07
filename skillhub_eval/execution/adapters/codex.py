"""OpenAI Codex CLI adapter (open-design compatible args)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from skillhub_eval.execution.cli_detect import find_cli_binary
from skillhub_eval.execution.events import AgentEvent, AgentEventType, ToolResultPayload
from skillhub_eval.execution.exec_result_builder import parsed_stream_from_events


def _normalize_command_execution_event(event: dict) -> dict | None:
    """Normalize a real `codex exec --json` `item.completed` /
    `command_execution` event into the flat shape verify_entrypoint_evidence()
    understands (command/stdout/exit_code/is_error).

    Real codex CLI reports every shell command it runs as
    `{"type": "item.completed", "item": {"type": "command_execution",
    "command": ..., "aggregated_output": ..., "exit_code": ..., "status":
    ...}}` — the generic stream parser only lifts `agent_message` items out of
    `item.completed`, so `tool_results` stayed empty and
    `verify_entrypoint_evidence()` always reported missing evidence even when
    the entrypoint genuinely ran (2026-07-02 real-machine finding, same class
    of gap as the Cursor Agent D14 / Trae D19 fixes).
    """
    if event.get("type") != "item.completed":
        return None
    item = event.get("item")
    if not isinstance(item, dict) or item.get("type") != "command_execution":
        return None
    exit_code = item.get("exit_code")
    return {
        "tool": "command_execution",
        "command": item.get("command"),
        "stdout": item.get("aggregated_output"),
        "stderr": None,
        "exit_code": exit_code,
        "is_error": item.get("status") == "failed" or (exit_code is not None and exit_code != 0),
    }


@dataclass
class CodexAdapter:
    agent_id: str = "codex"
    bin: str = "codex"
    model: str | None = None
    extra_allowed_dirs: list[str] = field(default_factory=list)

    def detect(self) -> bool:
        return find_cli_binary(self.bin) is not None

    def resolved_bin(self) -> str:
        return find_cli_binary(self.bin) or self.bin

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        if hardened:
            sandbox_args = [
                "exec",
                "--json",
                "--skip-git-repo-check",
                "--sandbox",
                "workspace-write",
                "-c",
                "sandbox_workspace_write.network_access=false",
            ]
        else:
            sandbox_args = [
                "exec",
                "--json",
                "--skip-git-repo-check",
                "--sandbox",
                "workspace-write",
                "-c",
                "sandbox_workspace_write.network_access=true",
            ]
        args = [*sandbox_args, "-c", 'default_permissions=":workspace"']
        if cwd:
            args.extend(["-C", cwd])
        for d in self.extra_allowed_dirs:
            if d:
                args.extend(["--add-dir", d])
        if self.model:
            args.extend(["--model", self.model])
        return [self.resolved_bin(), *args]

    def parse_stream(self, lines: list[str]):
        return parsed_stream_from_events(self.normalize_events(lines))

    def normalize_events(self, lines: list[str]) -> list[AgentEvent]:
        events: list[AgentEvent] = []
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
                    events.append(AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": delta}))
            elif event_type == "item.completed":
                item = event.get("item")
                if isinstance(item, dict) and item.get("type") == "agent_message":
                    text = item.get("text") or ""
                    if isinstance(text, str) and text:
                        events.append(AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": text}))
            elif event_type == "tool_result":
                events.append(AgentEvent(type=AgentEventType.TOOL_RESULT, payload=event))
            elif event_type in ("result", "turn.completed"):
                payload: dict = {}
                if event.get("is_error") or event.get("subtype") == "error_during_execution":
                    payload["is_error"] = True
                    raw_error = event.get("error") or event.get("message")
                    if isinstance(raw_error, str) and raw_error:
                        payload["error_text"] = raw_error
                elif event_type == "result":
                    result_text = event.get("result") or event.get("text")
                    if isinstance(result_text, str) and result_text:
                        payload["result"] = result_text
                if isinstance(event.get("usage"), dict):
                    events.append(AgentEvent(type=AgentEventType.USAGE, payload=event["usage"]))
                if event.get("duration_ms") is not None:
                    payload["duration_ms"] = event["duration_ms"]
                events.append(AgentEvent(type=AgentEventType.DONE, payload=payload))
            normalized = _normalize_command_execution_event(event)
            if normalized is not None:
                events.append(AgentEvent(type=AgentEventType.TOOL_RESULT, payload=_tool_result_payload(normalized)))
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
