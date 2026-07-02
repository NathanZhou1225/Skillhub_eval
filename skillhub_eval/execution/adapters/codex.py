"""OpenAI Codex CLI adapter (open-design compatible args)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from skillhub_eval.execution.cli_detect import find_cli_binary


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
        from skillhub_eval.execution.stream_parser import parse_stream_events

        parsed = parse_stream_events(lines)
        extra_tool_results: list[dict] = []
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
            normalized = _normalize_command_execution_event(event)
            if normalized is not None:
                extra_tool_results.append(normalized)
        if extra_tool_results:
            parsed = parsed.model_copy(
                update={"tool_results": [*parsed.tool_results, *extra_tool_results]}
            )
        return parsed
