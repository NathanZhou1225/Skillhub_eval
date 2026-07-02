"""Data-driven binary resolution + three-state detection with TTL cache."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from skillhub_eval.execution.agent_registry import AgentDef
from skillhub_eval.execution.cli_detect import detect_hint_zh, find_cli_binary
from skillhub_eval.settings import settings

_AUTH_DEFERRED = frozenset({"cursor-agent"})
_EXE_SUFFIXES = (".exe", ".cmd", ".bat", "")


@dataclass(frozen=True)
class DetectionResult:
    agent_id: str
    detected: bool
    bin_path: str | None
    auth_state: str  # "ok" | "missing" | "unknown"
    detect_hint: str | None = None


_cache: dict[str, tuple[float, DetectionResult]] = {}


def clear_detection_cache() -> None:
    _cache.clear()


def home_dir() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def _install_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("LOCALAPPDATA", "APPDATA"):
        val = os.environ.get(key)
        if val:
            roots.append(Path(val))
    roots.append(home_dir())
    return roots


def _config_dir_present(agent: AgentDef) -> bool:
    home = home_dir()
    return any((home / rel).exists() for rel in agent.config_dirs)


def config_dir_path(agent: AgentDef) -> Path | None:
    """Return the agent's config dir under HOME: first existing, else first declared."""
    if not agent.config_dirs:
        return None
    home = home_dir()
    for rel in agent.config_dirs:
        candidate = home / rel
        if candidate.exists():
            return candidate
    return home / agent.config_dirs[0]


def resolve_agent_binary(agent: AgentDef) -> str | None:
    for name in agent.binary_names:
        path = find_cli_binary(name)
        if path:
            return path
    for pattern in agent.install_dir_globs:
        for root in _install_roots():
            try:
                matches = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            except OSError:
                matches = []
            for d in matches:
                if not d.is_dir():
                    continue
                for name in agent.binary_names:
                    for suffix in _EXE_SUFFIXES:
                        candidate = d / f"{name}{suffix}"
                        if candidate.is_file():
                            return str(candidate.resolve())
    return None


def detect_agent(agent: AgentDef, *, force: bool = False) -> DetectionResult:
    now = time.monotonic()
    ttl = float(settings.agent_detect_cache_ttl_s)
    cached = _cache.get(agent.agent_id)
    if not force and cached and (now - cached[0]) < ttl:
        return cached[1]

    bin_path = resolve_agent_binary(agent)
    if bin_path is None:
        result = DetectionResult(agent.agent_id, False, None, "missing", detect_hint_zh(agent.bin))
    elif agent.agent_id in _AUTH_DEFERRED:
        result = DetectionResult(agent.agent_id, True, bin_path, "unknown")
    elif _config_dir_present(agent):
        result = DetectionResult(agent.agent_id, True, bin_path, "ok")
    else:
        result = DetectionResult(agent.agent_id, True, bin_path, "missing")

    _cache[agent.agent_id] = (now, result)
    return result
