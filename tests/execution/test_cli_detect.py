"""Tests for CLI binary resolution."""

from pathlib import Path

from skillhub_eval.execution.cli_detect import find_cli_binary


def test_find_cli_binary_uses_shutil_which(monkeypatch):
    monkeypatch.setattr(
        "skillhub_eval.execution.cli_detect.shutil.which",
        lambda name: "/usr/bin/codex" if name == "codex" else None,
    )
    assert find_cli_binary("codex") == "/usr/bin/codex"


def test_find_cli_binary_windows_npm_shim(monkeypatch, tmp_path):
    monkeypatch.setattr("skillhub_eval.execution.cli_detect.os.name", "nt")
    monkeypatch.setattr(
        "skillhub_eval.execution.cli_detect.shutil.which",
        lambda _name: None,
    )
    monkeypatch.setattr(
        "skillhub_eval.execution.cli_detect._find_well_known_windows_cli",
        lambda _name: None,
    )
    npm_dir = tmp_path / "npm"
    npm_dir.mkdir()
    shim = npm_dir / "codex.cmd"
    shim.write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(
        "skillhub_eval.execution.cli_detect._windows_search_dirs",
        lambda: [npm_dir],
    )
    assert find_cli_binary("codex") == str(shim.resolve())


def test_find_cli_binary_openai_codex_desktop_install(monkeypatch, tmp_path):
    monkeypatch.setattr("skillhub_eval.execution.cli_detect.os.name", "nt")
    monkeypatch.setattr(
        "skillhub_eval.execution.cli_detect.shutil.which",
        lambda _name: None,
    )
    version_dir = tmp_path / "OpenAI" / "Codex" / "bin" / "330bd0cba6496126"
    version_dir.mkdir(parents=True)
    exe = version_dir / "codex.exe"
    exe.write_bytes(b"")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(
        "skillhub_eval.execution.cli_detect._windows_search_dirs",
        lambda: [],
    )
    assert find_cli_binary("codex") == str(exe.resolve())
