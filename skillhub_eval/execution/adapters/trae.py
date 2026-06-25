"""Trae CLI adapter for local execution."""

from __future__ import annotations

from dataclasses import dataclass

from skillhub_eval.execution.cli_detect import find_cli_binary


@dataclass
class TraeAdapter:
    agent_id: str = "trae"
    bin: str = "traecli"
    model: str | None = None

    def detect(self) -> bool:
        return find_cli_binary(self.bin) is not None or find_cli_binary("trae") is not None

    def resolved_bin(self) -> str:
        return find_cli_binary(self.bin) or find_cli_binary("trae") or self.bin

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        args = ["acp", "serve", "--yolo"]
        if self.model:
            args.extend(["--model", self.model])
        return [self.resolved_bin(), *args]

    def parse_stream(self, lines: list[str]):
        from skillhub_eval.execution.stream_parser import parse_stream_events

        return parse_stream_events(lines)
