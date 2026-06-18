"""Resolve local CLI agent binaries (PATH + common install locations)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def find_cli_binary(name: str) -> str | None:
    """Return absolute path to CLI if found, else None."""
    clean = (name or "").strip()
    if not clean:
        return None

    path = shutil.which(clean)
    if path:
        return path

    if os.name != "nt":
        return None

    well_known = _find_well_known_windows_cli(clean)
    if well_known:
        return well_known

    for base in _windows_search_dirs():
        for suffix in (".cmd", ".exe", ".bat", ""):
            candidate = base / f"{clean}{suffix}"
            if candidate.is_file():
                return str(candidate.resolve())

    try:
        proc = subprocess.run(
            ["where.exe", clean],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        hit = line.strip().strip('"')
        if hit and Path(hit).exists():
            return hit
    return None


def _find_well_known_windows_cli(name: str) -> str | None:
    """Resolve CLIs installed outside npm/PATH (OpenAI Codex desktop app, etc.)."""
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return None

    if name == "codex":
        base = Path(local) / "OpenAI" / "Codex" / "bin"
        if not base.is_dir():
            return None
        direct = base / "codex.exe"
        if direct.is_file():
            return str(direct.resolve())
        versioned = sorted(
            base.glob("*/codex.exe"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if versioned:
            return str(versioned[0].resolve())

    return None


def detect_hint_zh(bin_name: str) -> str:
    """Human-readable hint when *bin_name* was not found."""
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    npm = Path(os.environ.get("APPDATA", "")) / "npm"
    codex_hint = ""
    if bin_name == "codex":
        codex_hint = (
            f" 亦已搜索 {local / 'OpenAI' / 'Codex' / 'bin'}（OpenAI Codex 桌面安装）。"
        )
    return (
        f"PATH、{npm}{codex_hint} 中未找到 {bin_name}。"
        "若终端 `where {name}` 可用，请从同一终端重启 skillhub-eval serve。".format(
            name=bin_name,
        )
    )


def _windows_search_dirs() -> list[Path]:
    dirs: list[Path] = []
    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if appdata:
        dirs.append(Path(appdata) / "npm")
    if localappdata:
        dirs.append(Path(localappdata) / "npm")
    path_env = os.environ.get("PATH", "")
    for part in path_env.split(os.pathsep):
        part = part.strip().strip('"')
        if part:
            dirs.append(Path(part))
    return dirs
