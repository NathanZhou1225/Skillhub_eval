from pathlib import Path
import tomllib


def test_pytest_uses_workspace_tmp_and_disables_cacheprovider():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    addopts = data["tool"]["pytest"]["ini_options"].get("addopts", "")

    assert "--basetemp=.tmp/pytest-basetemp" in addopts
    assert "-p no:cacheprovider" in addopts
