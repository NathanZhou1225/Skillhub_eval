"""Read-only Git inspection entrypoint for local agent evaluation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_REPO = ROOT / "fixtures" / "sample-repo"


def _run_git(args: list[str], repo: Path = FIXTURE_REPO) -> str:
    env = os.environ.copy()
    env["GIT_CEILING_DIRECTORIES"] = str(ROOT / "fixtures")
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        env=env,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return result.stdout.rstrip("\n")


def _status() -> dict:
    lines = [
        line
        for line in _run_git(["status", "--short", "--untracked-files=all"]).splitlines()
        if line
    ]
    modified = [line[3:] for line in lines if len(line) > 1 and line[1] != " " and not line.startswith("??")]
    staged = [line[3:] for line in lines if len(line) > 1 and line[0] != " " and not line.startswith("??")]
    untracked = [line[3:] for line in lines if line.startswith("?? ")]
    return {
        "status": "success",
        "action": "status",
        "repository": "fixtures/sample-repo",
        "modified_count": len(modified),
        "untracked_count": len(untracked),
        "staged_count": len(staged),
        "modified_files": modified,
        "untracked_files": untracked,
        "is_dirty": bool(lines),
    }


def _history() -> dict:
    commits = _run_git(["log", "--oneline", "-3"]).splitlines()
    return {
        "status": "success",
        "action": "history",
        "commit_count": len(commits),
        "latest_subject": commits[0].split(" ", 1)[1] if commits else "",
        "subjects": [line.split(" ", 1)[1] for line in commits],
    }


def _diff() -> dict:
    stat = _run_git(["diff", "--stat"])
    names = _run_git(["diff", "--name-only"]).splitlines()
    return {
        "status": "success",
        "action": "diff",
        "changed_files": names,
        "changed_file_count": len(names),
        "has_stat": bool(stat),
        "summary": stat,
    }


def _not_a_repo() -> dict:
    target = ROOT / "fixtures" / "not-a-repo"
    try:
        _run_git(["status", "--short"], repo=target)
    except RuntimeError:
        return {
            "status": "error",
            "action": "not_a_repo",
            "reason": "not_a_git_repository",
        }
    return {"status": "error", "action": "not_a_repo", "reason": "unexpected_repo"}


def _refuse_destructive() -> dict:
    return {
        "status": "denied",
        "action": "refuse_destructive",
        "reason": "destructive_git_operation_refused",
        "allowed_alternatives": ["status", "history", "diff"],
    }


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    try:
        if action == "status":
            payload = _status()
        elif action == "history":
            payload = _history()
        elif action == "diff":
            payload = _diff()
        elif action == "not_a_repo":
            payload = _not_a_repo()
        elif action == "refuse_destructive":
            payload = _refuse_destructive()
        else:
            payload = {"status": "error", "action": action, "reason": "unsupported_action"}
    except Exception as exc:  # noqa: BLE001 - entrypoint should emit JSON for harnesses.
        payload = {"status": "error", "action": action, "reason": str(exc)}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
