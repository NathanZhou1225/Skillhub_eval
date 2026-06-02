"""
Tests for PythonSubprocessRunner (Task 6).
Covers: happy path, timeout, UNSUPPORTED_RUNTIME downgrade.
"""

import pytest

from skillhub_eval.sandbox.python_subprocess import PythonSubprocessRunner


@pytest.fixture
def runner():
    return PythonSubprocessRunner()


# ─── fixtures: tiny Skill bundles ────────────────────────────────────────────

@pytest.fixture
def happy_bundle(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run.py").write_text(
        'import json, sys\nprint(json.dumps({"result": "ok"}))\n',
        encoding="utf-8",
    )
    return str(tmp_path)


@pytest.fixture
def timeout_bundle(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run.py").write_text(
        "import time\ntime.sleep(999)\n",
        encoding="utf-8",
    )
    return str(tmp_path)


@pytest.fixture
def shell_script_bundle(tmp_path):
    """Non-Python runtime → should trigger UNSUPPORTED_RUNTIME_ENV."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run.sh").write_text("#!/bin/bash\necho hello\n", encoding="utf-8")
    return str(tmp_path)


@pytest.fixture
def no_scripts_bundle(tmp_path):
    """No scripts/ dir at all → UNSUPPORTED_RUNTIME_ENV + downgrade."""
    return str(tmp_path)


@pytest.fixture
def exit_nonzero_bundle(tmp_path):
    """Script exits with non-zero → success=False, SANDBOX_EXEC_FAIL."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    return str(tmp_path)


# ─── happy path ──────────────────────────────────────────────────────────────

def test_run_happy_script_success(runner, happy_bundle):
    result = runner.run(happy_bundle, timeout=15)
    assert result["success"] is True
    assert "ok" in result["stdout"]
    assert result["reason_code"] is None
    assert result["downgrade_to_level1"] is False
    assert result["exit_code"] == 0


# ─── timeout ─────────────────────────────────────────────────────────────────

def test_run_timeout(runner, timeout_bundle):
    result = runner.run(timeout_bundle, timeout=1)
    assert result["success"] is False
    assert result["reason_code"] == "SANDBOX_EXEC_TIMEOUT"
    assert result["downgrade_to_level1"] is False
    assert "timeout" in result["stderr"].lower() or result["exit_code"] is None


# ─── non-zero exit ────────────────────────────────────────────────────────────

def test_run_nonzero_exit(runner, exit_nonzero_bundle):
    result = runner.run(exit_nonzero_bundle, timeout=10)
    assert result["success"] is False
    assert result["reason_code"] == "SANDBOX_EXEC_FAIL"
    assert result["exit_code"] == 1
    assert result["downgrade_to_level1"] is False


# ─── UNSUPPORTED_RUNTIME_ENV ─────────────────────────────────────────────────

def test_unsupported_runtime_shell_script(runner, shell_script_bundle):
    result = runner.run(shell_script_bundle, timeout=10)
    assert result["success"] is False
    assert result["reason_code"] == "UNSUPPORTED_RUNTIME_ENV"
    assert result["downgrade_to_level1"] is True


def test_no_scripts_dir_triggers_downgrade(runner, no_scripts_bundle):
    result = runner.run(no_scripts_bundle, timeout=10)
    assert result["success"] is False
    assert result["reason_code"] == "UNSUPPORTED_RUNTIME_ENV"
    assert result["downgrade_to_level1"] is True


# ─── bundle root fallback (run.py at root, no scripts/) ──────────────────────

def test_run_py_at_root(runner, tmp_path):
    """run.py placed at bundle root (no scripts/ dir) should also execute."""
    (tmp_path / "run.py").write_text(
        'import json\nprint(json.dumps({"msg": "root"}))\n',
        encoding="utf-8",
    )
    result = runner.run(str(tmp_path), timeout=10)
    assert result["success"] is True
    assert "root" in result["stdout"]
