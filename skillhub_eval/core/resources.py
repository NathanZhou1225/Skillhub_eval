"""Resolve packaged runtime data files with local-development fallback."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FALLBACK_DATA_DIR = _REPO_ROOT / "data"


def data_path(filename: str) -> Path:
    """Return a filesystem path for a packaged data file.

    The package copy is authoritative for installed/release builds.  The
    repository-level ``data/`` directory remains a development fallback for
    older worktrees and local run artifacts.
    """
    packaged = resources.files("skillhub_eval.data").joinpath(filename)
    if packaged.is_file():
        return Path(str(packaged))

    fallback = _FALLBACK_DATA_DIR / filename
    if fallback.is_file():
        return fallback

    raise FileNotFoundError(f"SkillHub data file not found: {filename}")
