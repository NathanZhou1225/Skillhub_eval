"""Antigravity CLI adapter for local execution."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from skillhub_eval.execution.cli_detect import find_cli_binary


@dataclass
class AntigravityAdapter:
    agent_id: str = "antigravity"
    bin: str = "agy"
    model: str | None = None

    def detect(self) -> bool:
        return find_cli_binary(self.bin) is not None

    def resolved_bin(self) -> str:
        return find_cli_binary(self.bin) or self.bin

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        if self.model:
            self.write_model_setting(self.model)
        return [self.resolved_bin()]

    def settings_path(self) -> Path:
        home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))
        return home / ".gemini" / "antigravity-cli" / "settings.json"

    def write_model_setting(self, model: str) -> None:
        path = self.settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data: dict = {}
        if path.exists():
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    data = parsed
            except json.JSONDecodeError:
                data = {}
        data["model"] = model
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def parse_stream(self, lines: list[str]):
        from skillhub_eval.execution.exec_result_builder import parsed_stream_from_events

        return parsed_stream_from_events(self.normalize_events(lines))

    def normalize_events(self, lines: list[str]):
        import json

        from skillhub_eval.execution.events import AgentEvent, AgentEventType

        events: list[AgentEvent] = []
        has_meaningful_structured_event = False
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
                    has_meaningful_structured_event = True
                    events.append(AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": delta}))
            elif event_type in ("result", "turn.completed"):
                has_meaningful_structured_event = True
                payload: dict = {}
                if event.get("duration_ms") is not None:
                    payload["duration_ms"] = int(event["duration_ms"])
                if event.get("is_error") or event.get("subtype") == "error_during_execution":
                    payload["is_error"] = True
                    payload["error_text"] = event.get("error") or event.get("message") or ""
                else:
                    if isinstance(event.get("result"), str):
                        payload["result"] = event["result"]
                    elif isinstance(event.get("text"), str):
                        payload["text"] = event["text"]
                events.append(AgentEvent(type=AgentEventType.DONE, payload=payload))
                if isinstance(event.get("usage"), dict):
                    events.append(AgentEvent(type=AgentEventType.USAGE, payload=event["usage"]))
            else:
                events.append(AgentEvent(type=AgentEventType.RAW_UNSUPPORTED, payload={"raw": event}))

        if has_meaningful_structured_event:
            return events

        text = "\n".join(line for line in lines if line.strip())
        if text:
            return [
                AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": text}),
                AgentEvent(type=AgentEventType.DONE, payload={}),
            ]
        return []
