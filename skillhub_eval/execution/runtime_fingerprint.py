"""Stable fingerprinting for runtime preflight cache entries."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from skillhub_eval.execution.runtime_defs import RuntimeDef

_IGNORED_DIRS = {".git", "__pycache__", ".pytest_cache"}


def runtime_fingerprint(
    runtime: RuntimeDef,
    *,
    model_id: str,
    cli_path: str | None,
    cli_version: str | None,
    skillhub_version: str,
) -> str:
    payload = {
        "runtime": asdict(runtime),
        "model_id": model_id or "default",
        "cli_path": cli_path or "",
        "cli_version": cli_version or "",
        "skillhub_version": skillhub_version or "",
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=True,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def skill_fingerprint(skill_dir: str | Path) -> str:
    root = Path(skill_dir)
    hasher = hashlib.sha256()
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not _has_ignored_part(path.relative_to(root))
    )
    for path in paths:
        rel = path.relative_to(root).as_posix()
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def _has_ignored_part(path: Path) -> bool:
    return any(part in _IGNORED_DIRS for part in path.parts)
