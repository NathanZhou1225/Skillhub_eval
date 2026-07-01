"""Per-run workspace: clone bundle into isolated temp cwd."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

MAX_ARTIFACTS = 20
MAX_ARTIFACT_BYTES = 64 * 1024
_SKIP_DIRS = {".git", "__pycache__", ".pytest_cache"}
_SKIP_SUFFIXES = {".pyc", ".pyo", ".exe", ".dll", ".zip"}


def snapshot_workspace(path: Path) -> dict[str, tuple[int, int]]:
    """Capture size/mtime fingerprints so only agent-created changes are collected."""
    root = Path(path)
    snapshot: dict[str, tuple[int, int]] = {}
    if not root.exists():
        return snapshot
    for item in _iter_files(root):
        try:
            stat = item.stat()
        except OSError:
            continue
        snapshot[_rel(item, root)] = (int(stat.st_mtime_ns), int(stat.st_size))
    return snapshot


def collect_workspace_artifacts(
    path: Path,
    before: dict[str, tuple[int, int]] | None = None,
) -> list[dict]:
    """Collect small text files created or modified by the local agent."""
    root = Path(path)
    before = before or {}
    artifacts: list[dict] = []
    if not root.exists():
        return artifacts

    for item in _iter_files(root):
        rel = _rel(item, root)
        try:
            stat = item.stat()
        except OSError:
            continue
        fingerprint = (int(stat.st_mtime_ns), int(stat.st_size))
        if before.get(rel) == fingerprint:
            continue
        if stat.st_size > MAX_ARTIFACT_BYTES:
            continue
        content = _read_text(item)
        if content is None:
            continue
        artifacts.append({
            "path": rel,
            "size_bytes": int(stat.st_size),
            "content": content,
        })
        if len(artifacts) >= MAX_ARTIFACTS:
            break
    return artifacts


def _iter_files(root: Path):
    for item in sorted(root.rglob("*")):
        if not item.is_file():
            continue
        rel_parts = item.relative_to(root).parts
        if any(part in _SKIP_DIRS for part in rel_parts):
            continue
        if item.suffix.lower() in _SKIP_SUFFIXES:
            continue
        yield item


def _rel(item: Path, root: Path) -> str:
    return item.relative_to(root).as_posix()


def _read_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


class PerRunWorkspace:
    """Clone a skill bundle directory for one case execution."""

    def __init__(self, *, retain: bool = False):
        self._retain = retain
        self._roots: list[Path] = []

    def acquire(self, bundle_path: str, case_id: str) -> Path:
        src = Path(bundle_path)
        if not src.exists():
            raise FileNotFoundError(bundle_path)
        dest = Path(tempfile.mkdtemp(prefix=f"skillhub-exec-{case_id}-"))
        shutil.copytree(src, dest, dirs_exist_ok=True)
        self._roots.append(dest)
        return dest

    def release(self, run_dir: Path) -> None:
        path = Path(run_dir)
        if self._retain:
            return
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
        if path in self._roots:
            self._roots.remove(path)
