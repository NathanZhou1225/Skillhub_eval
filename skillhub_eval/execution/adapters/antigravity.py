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
        from skillhub_eval.core.schemas.report import ParsedStream
        from skillhub_eval.execution.stream_parser import parse_stream_events

        parsed = parse_stream_events(lines)
        if parsed.final_text or parsed.is_complete:
            return parsed
        text = "\n".join(line for line in lines if line.strip())
        return ParsedStream(final_text=text, is_complete=bool(text))
