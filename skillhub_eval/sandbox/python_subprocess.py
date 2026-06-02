"""
Level 2 sandbox executor — Python subprocess only (MVP, C-6 trust boundary).

Security model:
- Only executes .py entry scripts from internal whitelist bundles.
- Non-Python runtimes (shell, JS, etc.) trigger graceful downgrade to Level 1.
- 180 s hard timeout (SANDBOX_EXEC_TIMEOUT).
- No container isolation in MVP; full isolation deferred to research/K8s.
"""

import subprocess
import sys
from pathlib import Path


# Search order for Python entry script within a bundle
_PYTHON_ENTRY_CANDIDATES = ["scripts/run.py", "scripts/main.py", "run.py", "main.py"]

# File extensions treated as non-Python runtimes
_NON_PYTHON_EXTENSIONS = {".sh", ".js", ".ts", ".rb", ".go", ".java", ".bat", ".cmd"}


def _find_python_entry(root: Path) -> Path | None:
    """Return the first Python entry script found, or None."""
    for relative in _PYTHON_ENTRY_CANDIDATES:
        candidate = root / relative
        if candidate.exists():
            return candidate
    return None


def _has_non_python_scripts(root: Path) -> bool:
    """Return True if scripts/ contains files with non-Python extensions."""
    scripts_dir = root / "scripts"
    if not scripts_dir.exists():
        return False
    return any(
        f.suffix in _NON_PYTHON_EXTENSIONS
        for f in scripts_dir.iterdir()
        if f.is_file()
    )


class PythonSubprocessRunner:
    """
    Runs a Python entry script from a Skill bundle directory.

    Only Python is supported in the MVP.  Non-Python runtimes trigger a
    graceful downgrade to Level 1 (sample_io), with reason_code
    UNSUPPORTED_RUNTIME_ENV and downgrade_to_level1=True.
    """

    def run(self, bundle_path: str, timeout: int = 180) -> dict:
        """
        Locate and execute the Python entry script.

        Returns a result dict:
            success           bool
            reason_code       str | None  (SANDBOX_EXEC_TIMEOUT |
                                           SANDBOX_EXEC_FAIL |
                                           UNSUPPORTED_RUNTIME_ENV | None)
            downgrade_to_level1  bool
            stdout            str
            stderr            str
            exit_code         int | None
        """
        root = Path(bundle_path)
        entry = _find_python_entry(root)

        if entry is None:
            # No Python entry found — check whether non-Python files exist
            non_py = _has_non_python_scripts(root)
            msg = (
                "Non-Python runtime detected; downgrading to Level 1 (sample_io)."
                if non_py
                else "No Python entry script found; downgrading to Level 1 (sample_io)."
            )
            return {
                "success": False,
                "reason_code": "UNSUPPORTED_RUNTIME_ENV",
                "downgrade_to_level1": True,
                "stdout": "",
                "stderr": msg,
                "exit_code": None,
            }

        try:
            proc = subprocess.run(
                [sys.executable, str(entry)],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            success = proc.returncode == 0
            return {
                "success": success,
                "reason_code": None if success else "SANDBOX_EXEC_FAIL",
                "downgrade_to_level1": False,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "exit_code": proc.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "reason_code": "SANDBOX_EXEC_TIMEOUT",
                "downgrade_to_level1": False,
                "stdout": "",
                "stderr": f"Subprocess exceeded {timeout}s timeout.",
                "exit_code": None,
            }
