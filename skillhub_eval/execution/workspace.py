"""Per-run workspace: clone bundle into isolated temp cwd."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


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
