"""Adapter-agnostic local-agent diagnosis primitives (Q-29)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiagnosisResult:
    """Result of an optional AgentAdapter.diagnose() call, surfaced at scan time."""

    ok: bool
    reason_code: str | None
    message_zh: str
    manual_hint: str | None = None


def check_writable(dir_path: Path) -> bool:
    """Best-effort probe: can we create and delete a file inside dir_path?"""
    probe = dir_path / ".skillhub_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
    except OSError:
        return False
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
    return True
