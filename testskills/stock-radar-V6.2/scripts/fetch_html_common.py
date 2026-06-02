"""Constants and helpers for fetch_html pipeline."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os

FETCH_HTML_SCHEMA_VERSION = "1.4.2"
MIN_KLINE_BARS = 5
BARS_REQUESTED = 60
FUND_FLOW_STALE_LAG_DAYS = 1
FUND_FLOW_CACHE_TTL_HOURS = float(os.environ.get("STOCK_RADAR_FUND_FLOW_CACHE_TTL_HOURS", "4"))
FETCH_CACHE_DIR = Path(os.environ.get("STOCK_RADAR_FETCH_CACHE_DIR", "/tmp/stock-radar/cache"))

SH_INDEX_CODE = "000001"
SH_INDEX_NAME = "上证指数"
SH_INDEX_SYMBOL = "sh000001"
OVERLAY_FETCH_TIMEOUT_SEC = float(os.environ.get("STOCK_RADAR_OVERLAY_TIMEOUT", "12"))

SKILL_ROOT = Path(__file__).resolve().parents[1]
FETCH_HTML_SCHEMA_PATH = SKILL_ROOT / "schemas" / "fetch_html.schema.json"

ANNOTATION_KEYS = (
    "ma_alignment",
    "trend_strength",
    "breakout_60d_high",
    "broke_60d_low",
    "near_60d_high_pct",
    "near_60d_low_pct",
    "volume_vs_20d",
    "change_20d_pct",
    "change_60d_pct",
)


def unavailable_fetch_html(code: str, reason_code: str, reason: str, fetched_at: str | None = None) -> dict:
    from overlay_fetch import unavailable_overlays

    ts = fetched_at or datetime.now().isoformat()
    return {
        "schema_version": FETCH_HTML_SCHEMA_VERSION,
        "code": code,
        "fetched_at": ts,
        "source": "unavailable",
        "kline": {
            "status": "unavailable",
            "reason_code": reason_code,
            "reason": reason,
            "bars_available": 0,
            "bars_requested": BARS_REQUESTED,
            "series": [],
        },
        "ma_overlay": {"ma5": [], "ma20": [], "ma60": []},
        "fund_flow": {
            "status": "error",
            "reason_code": "FETCH_FAILED",
            "reason": reason,
            "as_of_date": None,
            "reference_date": None,
            "lag_trading_days": None,
            "series": [],
        },
        "annotations": None,
        "overlays": unavailable_overlays(reason),
        "benchmark_sector_fund_flow": {
            "status": "placeholder",
            "reason_code": "FETCH_FAILED",
            "reason": reason,
            "requested_name": None,
            "sector_name": None,
            "matched_name": None,
            "as_of_date": None,
            "reference_date": None,
            "lag_trading_days": None,
            "series": [],
        },
    }
