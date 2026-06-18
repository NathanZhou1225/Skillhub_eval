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
        from skillhub_eval.execution.stream_parser import parse_stream_events

        return parse_stream_events(lines)
