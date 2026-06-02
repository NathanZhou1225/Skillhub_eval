"""Individual stock 5-day fund flow: retry, disk cache, and fetch_html block builder."""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd

from fetch_html_common import FUND_FLOW_CACHE_TTL_HOURS, FUND_FLOW_STALE_LAG_DAYS, FETCH_CACHE_DIR

FUND_FLOW_TIMEOUT_SEC = float(os.environ.get("STOCK_RADAR_FUND_FLOW_TIMEOUT", "15"))
FUND_FLOW_RETRIES = int(os.environ.get("STOCK_RADAR_FUND_FLOW_RETRIES", "2"))


def _normalize_date(value: Any) -> str:
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    if "T" in text:
        return text.split("T", 1)[0][:10]
    return text[:10]


def classify_fund_flow_error(error: str | None) -> tuple[str, str]:
    """Map raw exception text to (reason_code, human_reason)."""
    text = str(error or "").strip()
    lowered = text.lower()
    if not text or text == "EMPTY":
        return "EMPTY", "资金流返回空数据"
    if any(token in lowered for token in ("proxy", "403", "forbidden", "blocked", "代理")):
        return "PROXY_BLOCKED", "东财个股资金流接口代理阻断"
    if any(
        token in lowered
        for token in (
            "connection",
            "timeout",
            "remotedisconnected",
            "refused",
            "reset",
            "aborted",
            "broken pipe",
            "timed out",
        )
    ):
        return "CONNECTION_ERROR", "数据源连接中断，请稍后重试"
    if len(text) > 80 or text.startswith("("):
        return "FETCH_FAILED", "资金流接口不可用"
    return "FETCH_FAILED", text


def _fund_cache_path(code: str) -> Path:
    return FETCH_CACHE_DIR / "fund_flow" / f"{code}.json"


def _serialize_records(fund: pd.DataFrame) -> list[dict]:
    records: list[dict] = []
    for row in fund.head(5).to_dict(orient="records"):
        normalized: dict[str, Any] = {}
        for key, value in row.items():
            if hasattr(value, "isoformat"):
                normalized[key] = value.isoformat()
            elif isinstance(value, float):
                normalized[key] = round(value, 2)
            else:
                normalized[key] = value
        records.append(normalized)
    return records


def write_fund_flow_cache(code: str, fund: pd.DataFrame) -> None:
    payload = {
        "code": code,
        "fetched_at": datetime.now().isoformat(),
        "records": _serialize_records(fund),
    }
    path = _fund_cache_path(code)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_fund_flow_cache(code: str) -> dict | None:
    path = _fund_cache_path(code)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not payload.get("records"):
        return None
    return payload


def cache_age_hours(cache_payload: dict) -> float | None:
    fetched_at = cache_payload.get("fetched_at")
    if not fetched_at:
        return None
    try:
        ts = datetime.fromisoformat(str(fetched_at))
    except ValueError:
        return None
    return (datetime.now() - ts).total_seconds() / 3600.0


def cache_is_fresh(cache_payload: dict) -> bool:
    age = cache_age_hours(cache_payload)
    return age is not None and age < FUND_FLOW_CACHE_TTL_HOURS


def _records_to_dataframe(records: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(records)


def _fetch_live_once(code: str, market: str) -> tuple[pd.DataFrame | None, str | None]:
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(ak.stock_individual_fund_flow, stock=code, market=market)
            result = future.result(timeout=FUND_FLOW_TIMEOUT_SEC)
    except FuturesTimeoutError:
        return None, "timeout"
    except Exception as exc:
        return None, str(exc)

    if result is None or result.empty:
        return None, "EMPTY"
    return result, None


def fetch_individual_fund_flow(code: str, market: str) -> tuple[pd.DataFrame | None, str | None, dict]:
    """Return (dataframe, live_error, meta). meta keys: source, cache_fetched_at."""
    attempts = max(1, FUND_FLOW_RETRIES + 1)
    last_error: str | None = None

    for attempt in range(attempts):
        if attempt > 0:
            time.sleep(1 if attempt == 1 else 2)
        fund, error = _fetch_live_once(code, market)
        if fund is not None:
            write_fund_flow_cache(code, fund)
            return fund, None, {"source": "live", "attempts": attempt + 1}
        last_error = error

    cached = read_fund_flow_cache(code)
    if cached:
        fund = _records_to_dataframe(cached["records"])
        if not fund.empty:
            return fund, last_error, {
                "source": "cache",
                "cache_fetched_at": cached.get("fetched_at"),
                "cache_fresh": cache_is_fresh(cached),
                "live_error": last_error,
            }

    return None, last_error, {"source": "none", "attempts": attempts}


def _trading_lag(trading_dates: list[str], as_of: str, reference: str) -> int:
    if not as_of or not reference or as_of >= reference:
        return 0
    return sum(1 for day in trading_dates if as_of < day <= reference)


def _cache_time_label(cache_fetched_at: str | None) -> str:
    if not cache_fetched_at:
        return "未知时间"
    try:
        ts = datetime.fromisoformat(str(cache_fetched_at))
        return ts.strftime("%H:%M")
    except ValueError:
        text = str(cache_fetched_at)
        return text[11:16] if len(text) >= 16 else text[:16]


def build_fund_flow_block(
    fund: pd.DataFrame | None,
    fund_error: str | None,
    reference_date: str | None,
    trading_dates: list[str],
    *,
    from_cache: bool = False,
    cache_fetched_at: str | None = None,
) -> dict:
    empty_error = {
        "status": "error",
        "reason_code": "FETCH_FAILED",
        "reason": fund_error or "资金流接口不可用",
        "as_of_date": None,
        "reference_date": reference_date,
        "lag_trading_days": None,
        "series": [],
    }

    if fund_error and (fund is None or fund.empty):
        reason_code, reason = classify_fund_flow_error(fund_error)
        empty_error["reason_code"] = reason_code
        empty_error["reason"] = reason
        return empty_error

    if fund is None or fund.empty:
        reason_code, reason = classify_fund_flow_error(fund_error or "EMPTY")
        return {
            "status": "error",
            "reason_code": reason_code,
            "reason": reason,
            "as_of_date": None,
            "reference_date": reference_date,
            "lag_trading_days": None,
            "series": [],
        }

    rows: list[dict] = []
    for _, row in fund.head(5).iterrows():
        inflow = float(row.get("主力净流入-净额", 0) or 0)
        pct_raw = row.get("主力净流入-净占比")
        pct = round(float(pct_raw), 2) if pct_raw is not None and pct_raw == pct_raw else None
        rows.append(
            {
                "date": _normalize_date(row.get("日期")),
                "main_net_inflow": round(inflow, 2),
                "main_net_pct": pct,
                "is_net_in": inflow > 0,
            }
        )

    rows.sort(key=lambda item: item["date"])
    as_of_date = rows[-1]["date"] if rows else None
    lag = _trading_lag(trading_dates, as_of_date or "", reference_date or "") if reference_date else None

    if lag is None:
        return {
            "status": "error",
            "reason_code": "EMPTY",
            "reason": "无法计算资金流滞后",
            "as_of_date": as_of_date,
            "reference_date": reference_date,
            "lag_trading_days": None,
            "series": [],
        }

    cache_label = _cache_time_label(cache_fetched_at)
    if from_cache:
        reason_code = "API_STALE" if lag > 30 else "LAG_EXCEEDS_THRESHOLD"
        if lag <= FUND_FLOW_STALE_LAG_DAYS:
            reason_code = "LAG_EXCEEDS_THRESHOLD"
        return {
            "status": "stale",
            "reason_code": reason_code,
            "reason": f"实时接口不可用，已降级为缓存（缓存于 {cache_label}）",
            "as_of_date": as_of_date,
            "reference_date": reference_date,
            "lag_trading_days": lag if lag > 0 else 1,
            "series": rows,
        }

    if lag > FUND_FLOW_STALE_LAG_DAYS:
        if lag > 30:
            reason_code = "API_STALE"
            reason = f"资金数据截至 {as_of_date}，与 K 线 {reference_date} 严重不同步"
        else:
            reason_code = "LAG_EXCEEDS_THRESHOLD"
            reason = f"资金数据截至 {as_of_date}，落后 K 线 {lag} 个交易日"
        return {
            "status": "stale",
            "reason_code": reason_code,
            "reason": reason,
            "as_of_date": as_of_date,
            "reference_date": reference_date,
            "lag_trading_days": lag,
            "series": rows,
        }

    return {
        "status": "ok",
        "reason_code": None,
        "reason": None,
        "as_of_date": as_of_date,
        "reference_date": reference_date,
        "lag_trading_days": lag,
        "series": rows,
    }


def snapshot_fund_flow_recent(fund: pd.DataFrame | None) -> list[dict] | None:
    if fund is None or fund.empty:
        return None
    return _serialize_records(fund)
