"""Shared benchmark sector / concept board name candidates for fetch layers."""
from __future__ import annotations

from board_cache import BOARD_PROBE_MAX

ROBOT_SECTOR_ALIASES = ("人形机器人", "机器人概念", "机器人执行器", "减速器")


def sector_board_candidates(sector_name: str) -> list[str]:
    """Ordered unique probe names for concept/industry board APIs."""
    raw = (sector_name or "").strip()
    if not raw:
        return []

    names: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        text = name.strip()
        if text and text not in seen:
            seen.add(text)
            names.append(text)

    robot_context = raw == "机器人" or any(token in raw for token in ("机器人", "人形", "具身"))

    if raw == "机器人" or (len(raw) <= 3 and robot_context):
        for alias in ROBOT_SECTOR_ALIASES:
            add(alias)

    add(raw)
    stripped = raw
    for suffix in ("Ⅱ", "Ⅲ", "概念", "板块"):
        stripped = stripped.replace(suffix, "")
    stripped = stripped.strip()
    if stripped and stripped != raw:
        add(stripped)

    if robot_context and raw != "机器人":
        for alias in ROBOT_SECTOR_ALIASES:
            add(alias)

    return names[:BOARD_PROBE_MAX]
