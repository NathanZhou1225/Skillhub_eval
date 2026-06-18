"""OpenAI Codex CLI adapter (open-design compatible args)."""

from __future__ import annotations

from dataclasses import dataclass, field

from skillhub_eval.execution.cli_detect import find_cli_binary


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
        from skillhub_eval.execution.stream_parser import parse_stream_events

        return parse_stream_events(lines)
