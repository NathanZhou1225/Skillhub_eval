"""Disk cache for benchmark sector board resolution (matched name, BK code, kind)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from fetch_html_common import FETCH_CACHE_DIR

BOARD_CACHE_TTL_HOURS = float(os.environ.get("STOCK_RADAR_BOARD_CACHE_TTL_HOURS", "24"))
BOARD_PROBE_MAX = int(os.environ.get("STOCK_RADAR_BOARD_PROBE_MAX", "4"))


def normalize_board_cache_key(name: str) -> str:
    return (name or "").strip()


def board_cache_path(name: str) -> Path:
    key = normalize_board_cache_key(name)
    safe = key.replace("/", "_").replace("\\", "_") or "unknown"
    return FETCH_CACHE_DIR / "board" / f"{safe}.json"


def read_board_cache(sector_name: str) -> dict | None:
    path = board_cache_path(sector_name)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    fetched_at = payload.get("fetched_at")
    if fetched_at:
        try:
            age = datetime.now() - datetime.fromisoformat(str(fetched_at))
            if age > timedelta(hours=BOARD_CACHE_TTL_HOURS):
                return None
        except ValueError:
            pass

    if not payload.get("matched_name") and not payload.get("index_code"):
        return None
    return payload


def write_board_cache(
    sector_name: str,
    *,
    matched_name: str | None = None,
    index_code: str | None = None,
    kind: str | None = None,
    requested_name: str | None = None,
) -> None:
    path = board_cache_path(sector_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "requested_name": requested_name or sector_name,
        "normalized_key": normalize_board_cache_key(sector_name),
        "matched_name": matched_name,
        "index_code": index_code,
        "kind": kind,
        "fetched_at": datetime.now().isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
