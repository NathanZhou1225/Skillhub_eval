"""Verify local agent tool_result evidence for declared entrypoint."""

from __future__ import annotations

from pathlib import PurePosixPath


def _normalize_entrypoint(entrypoint: str) -> str:
    return entrypoint.replace("\\", "/")


def verify_entrypoint_evidence(tool_results: list[dict], entrypoint: str) -> bool:
    """Return True if any tool_result indicates the entrypoint was executed."""
    if not entrypoint or not tool_results:
        return False

    target = _normalize_entrypoint(entrypoint)
    target_name = PurePosixPath(target).name

    for item in tool_results:
        if not isinstance(item, dict):
            continue
        haystacks: list[str] = []
        for key in ("stdout", "stderr", "command", "tool", "name"):
            val = item.get(key)
            if isinstance(val, str) and val:
                haystacks.append(_normalize_entrypoint(val))
        combined = " ".join(haystacks)
        if target in combined or target_name in combined:
            if item.get("isError") or item.get("is_error"):
                continue
            exit_code = item.get("exit_code", item.get("exitCode"))
            if exit_code is not None and int(exit_code) != 0:
                continue
            return True
    return False
