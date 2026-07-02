"""Trae CLI adapter — stream-json print mode (G1/G6)."""

from __future__ import annotations

from dataclasses import dataclass


def _resolved_bin() -> str:
    from skillhub_eval.execution.agent_registry import get_agent_def
    from skillhub_eval.execution.detection import resolve_agent_binary

    agent = get_agent_def("trae")
    return (resolve_agent_binary(agent) if agent else None) or "trae-cli"


@dataclass
class TraeAdapter:
    agent_id: str = "trae"
    model: str | None = None
    prompt_via_stdin: bool = False

    def detect(self) -> bool:
        from skillhub_eval.execution.agent_registry import get_agent_def
        from skillhub_eval.execution.detection import resolve_agent_binary

        agent = get_agent_def("trae")
        return bool(agent and resolve_agent_binary(agent))

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        args = [
            _resolved_bin(),
            "-p",
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--permission-mode", "bypass_permissions",
            "--yolo",
        ]
        if self.model:
            args.extend(["-c", f"model.name={self.model}"])
        return args

    def parse_stream(self, lines: list[str]):
        from skillhub_eval.execution.stream_parser import parse_stream_events

        return parse_stream_events(lines)
