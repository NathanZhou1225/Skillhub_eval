"""Claude Code CLI adapter (open-design compatible args)."""

from __future__ import annotations

from dataclasses import dataclass, field

from skillhub_eval.execution.cli_detect import find_cli_binary


@dataclass
class ClaudeAdapter:
    agent_id: str = "claude"
    bin: str = "claude"
    model: str | None = None
    extra_allowed_dirs: list[str] = field(default_factory=list)

    def detect(self) -> bool:
        return find_cli_binary(self.bin) is not None

    def resolved_bin(self) -> str:
        return find_cli_binary(self.bin) or self.bin

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        # hardened profile not supported on claude (bypassPermissions); caller handles redline fallback
        args = [
            "-p",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            "--permission-mode",
            "bypassPermissions",
        ]
        if self.model:
            args.extend(["--model", self.model])
        dirs = [d for d in self.extra_allowed_dirs if d]
        if dirs:
            args.append("--add-dir")
            args.extend(dirs)
        return [self.resolved_bin(), *args]

    def parse_stream(self, lines: list[str]):
        from skillhub_eval.execution.exec_result_builder import parsed_stream_from_events

        return parsed_stream_from_events(self.normalize_events(lines))

    def normalize_events(self, lines: list[str]):
        import json

        from skillhub_eval.execution.events import AgentEvent, AgentEventType

        events: list[AgentEvent] = []
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                events.append(AgentEvent(type=AgentEventType.RAW_UNSUPPORTED, payload={"raw": raw}))
                continue
            if not isinstance(event, dict):
                events.append(AgentEvent(type=AgentEventType.RAW_UNSUPPORTED, payload={"raw": event}))
                continue

            event_type = event.get("type")
            if event_type in ("text", "assistant"):
                delta = event.get("delta") or event.get("text") or ""
                if isinstance(delta, str) and delta:
                    events.append(AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": delta}))
            elif event_type == "tool_result":
                events.append(AgentEvent(type=AgentEventType.TOOL_RESULT, payload=event))
            elif event_type in ("result", "turn.completed"):
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
        return events
