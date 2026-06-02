"""Index/sector overlay fetch and 60-day normalized % series for fetch_html v1.2.0."""
from __future__ import annotations

import concurrent.futures
import os
from datetime import datetime, timedelta
from typing import Any, Callable

import akshare as ak

from board_name_resolve import sector_board_candidates
from board_cache import read_board_cache, write_board_cache
from board_probe import (
    load_overlay_cache_into_result,
    resolve_board,
    sector_overlay_from_resolved,
)
from fetch_html_common import (
    BARS_REQUESTED,
    SH_INDEX_CODE,
    SH_INDEX_NAME,
    SH_INDEX_SYMBOL,
    OVERLAY_FETCH_TIMEOUT_SEC,
)

OVERLAY_ANCHOR = "first_bar_close"


def _normalize_date(value: Any) -> str:
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10]


def _call_with_timeout(fn: Callable[[], Any], timeout_sec: float, retries: int = 2) -> Any:
    for _ in range(max(1, retries)):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fn)
            try:
                result = future.result(timeout=timeout_sec)
                if result is not None:
                    return result
            except (concurrent.futures.TimeoutError, Exception):
                continue
    return None


def _pct_from_anchor(closes: list[float | None]) -> list[float | None]:
    if not closes:
        return []
    anchor_idx = next((i for i, c in enumerate(closes) if c is not None and c > 0), None)
    if anchor_idx is None:
        return [None] * len(closes)
    anchor = closes[anchor_idx]
    result: list[float | None] = []
    for close in closes:
        if close is None or anchor <= 0:
            result.append(None)
        else:
            result.append(round((close / anchor - 1) * 100, 2))
    if result and result[anchor_idx] is not None:
        result[anchor_idx] = 0.0
    return result


def _forward_fill(closes: list[float | None]) -> list[float | None]:
    filled: list[float | None] = []
    last: float | None = None
    for value in closes:
        if value is not None:
            last = value
        filled.append(last)
    return filled


def _align_closes_to_dates(dates: list[str], df) -> list[float | None]:
    if df is None or df.empty:
        return [None] * len(dates)

    date_col = "date" if "date" in df.columns else "日期"
    close_col = "close" if "close" in df.columns else "收盘"
    mapping: dict[str, float] = {}
    for _, row in df.iterrows():
        day = _normalize_date(row[date_col])
        mapping[day] = float(row[close_col])

    raw = [mapping.get(day) for day in dates]
    return _forward_fill(raw)


def _fetch_sh_index_df(start: str, end: str):
    def _load():
        df = ak.stock_zh_index_daily(symbol=SH_INDEX_SYMBOL)
        if df is None or df.empty:
            return None
        out = df.copy()
        out["date"] = out["date"].astype(str).map(_normalize_date)
        mask = (out["date"] >= _normalize_date(start)) & (out["date"] <= _normalize_date(end))
        return out.loc[mask]

    return _call_with_timeout(_load, OVERLAY_FETCH_TIMEOUT_SEC)


def _fetch_sector_df(sector_symbol: str, start: str, end: str):
    def _load():
        return ak.stock_board_industry_hist_em(
            symbol=sector_symbol,
            start_date=start.replace("-", ""),
            end_date=end.replace("-", ""),
            period="日k",
            adjust="",
        )

    return _call_with_timeout(_load, OVERLAY_FETCH_TIMEOUT_SEC)


def _fetch_concept_board_df(sector_name: str, start: str, end: str) -> tuple[Any, str | None]:
    start_compact = start.replace("-", "")
    end_compact = end.replace("-", "")

    cached = read_board_cache(sector_name)
    if cached and cached.get("matched_name"):
        matched = cached["matched_name"]

        def _load_cached(name=matched):
            return ak.stock_board_concept_hist_em(
                symbol=name,
                period="daily",
                start_date=start_compact,
                end_date=end_compact,
                adjust="",
            )

        df = _call_with_timeout(_load_cached, OVERLAY_FETCH_TIMEOUT_SEC, retries=2)
        if df is not None and not df.empty:
            return df, matched

    candidates = sector_board_candidates(sector_name)
    for idx, candidate in enumerate(candidates):
        retries = 2 if idx == 0 else 1

        def _load(name=candidate):
            return ak.stock_board_concept_hist_em(
                symbol=name,
                period="daily",
                start_date=start_compact,
                end_date=end_compact,
                adjust="",
            )

        df = _call_with_timeout(_load, OVERLAY_FETCH_TIMEOUT_SEC, retries=retries)
        if df is not None and not df.empty:
            write_board_cache(
                sector_name,
                matched_name=candidate,
                kind="concept",
                requested_name=sector_name,
            )
            return df, candidate
    return None, None


def _sh_index_last_close(sh_df) -> float | None:
    if sh_df is None or sh_df.empty:
        return None
    close_col = "close" if "close" in sh_df.columns else "收盘"
    try:
        return round(float(sh_df.iloc[-1][close_col]), 2)
    except (TypeError, ValueError, KeyError):
        return None


def _sh_index_block(*, status: str, pct: list, last_close: float | None = None) -> dict:
    block = {
        "code": SH_INDEX_CODE,
        "name": SH_INDEX_NAME,
        "status": status,
        "pct": pct,
    }
    if last_close is not None:
        block["last_close"] = last_close
    return block


def unavailable_overlays(reason: str = "K 线不可用") -> dict:
    return {
        "status": "unavailable",
        "reason": reason,
        "anchor": OVERLAY_ANCHOR,
        "dates": [],
        "stock_pct": [],
        "sh_index": _sh_index_block(status="error", pct=[]),
        "sector": {
            "code": None,
            "name": None,
            "status": "skipped",
            "pct": None,
        },
    }


def build_overlays(
    kline_series: list[dict],
    *,
    sector_index_code: str | None = None,
    sector_name: str | None = None,
    resolved=None,
) -> dict:
    if not kline_series:
        return unavailable_overlays()

    dates = [bar["date"] for bar in kline_series]
    stock_closes = [float(bar["close"]) for bar in kline_series]
    stock_pct = _pct_from_anchor(stock_closes)

    start = dates[0]
    end = dates[-1]
    start_compact = start.replace("-", "")
    end_compact = end.replace("-", "")

    sh_df = _fetch_sh_index_df(start, end)
    sh_closes = _align_closes_to_dates(dates, sh_df)
    sh_pct = _pct_from_anchor(sh_closes)
    sh_ok = any(v is not None for v in sh_pct)
    sh_last_close = _sh_index_last_close(sh_df)

    sector_code = (sector_index_code or "").strip() or None
    sector_label = (sector_name or "").strip() or sector_code
    if resolved is None and sector_label:
        resolved = resolve_board(
            sector_name or sector_label,
            sector_code,
            overlay_start=start,
            overlay_end=end,
        )
    if resolved and not sector_code and resolved.index_code:
        sector_code = resolved.index_code
    if resolved and resolved.matched_name:
        sector_label = resolved.matched_name
    elif not sector_code and sector_name:
        cached = read_board_cache(sector_name)
        if cached and cached.get("index_code"):
            sector_code = str(cached["index_code"]).strip() or None
            if not sector_label and cached.get("matched_name"):
                sector_label = cached["matched_name"]
    sector_pct: list[float | None] | None = None
    sector_status = "skipped"
    overlay_stale_note: str | None = None
    matched_concept_name: str | None = None
    cache_sector_name = sector_name or sector_label
    if resolved:
        load_overlay_cache_into_result(resolved, cache_sector_name)
        pct, matched, stale = sector_overlay_from_resolved(dates, resolved, cache_sector_name)
        if pct:
            sector_pct = pct
            sector_status = "ok"
            sector_label = matched or sector_label
            overlay_stale_note = stale
    elif sector_code:
        sector_df = _fetch_sector_df(sector_code, start_compact, end_compact)
        if sector_df is None or sector_df.empty:
            sector_status = "error"
        else:
            sector_closes = _align_closes_to_dates(dates, sector_df)
            sector_pct = _pct_from_anchor(sector_closes)
            sector_status = "ok" if any(v is not None for v in sector_pct) else "error"
    elif sector_label:
        sector_df, matched_concept_name = _fetch_concept_board_df(sector_label, start, end)
        if sector_df is not None and not sector_df.empty:
            sector_closes = _align_closes_to_dates(dates, sector_df)
            sector_pct = _pct_from_anchor(sector_closes)
            if any(v is not None for v in sector_pct):
                sector_status = "ok"
                sector_label = matched_concept_name or sector_label
            else:
                sector_status = "error"
        else:
            sector_status = "error"

    if not sh_ok:
        return {
            "status": "unavailable",
            "reason": "上证指数数据不可用",
            "anchor": OVERLAY_ANCHOR,
            "dates": dates,
            "stock_pct": stock_pct,
            "sh_index": _sh_index_block(status="error", pct=[]),
            "sector": {
                "code": sector_code,
                "name": sector_label,
                "status": sector_status,
                "pct": None,
            },
        }

    status = "ok"
    reason = None
    if sector_label and sector_status != "ok":
        status = "partial"
        reason = "板块指数不可用，仅展示上证指数对照"
    elif sector_code and sector_status != "ok":
        status = "partial"
        reason = "板块指数不可用，仅展示上证指数对照"

    overlay_payload: dict = {
        "status": status,
        "reason": reason,
        "anchor": OVERLAY_ANCHOR,
        "dates": dates,
        "stock_pct": stock_pct,
        "sh_index": _sh_index_block(status="ok", pct=sh_pct, last_close=sh_last_close),
        "sector": {
            "code": sector_code,
            "name": sector_label,
            "status": sector_status,
            "pct": sector_pct if sector_status == "ok" else None,
        },
    }
    if overlay_stale_note:
        overlay_payload["overlay_stale_note"] = overlay_stale_note
    return overlay_payload


def build_overlays_from_stock_only(kline_series: list[dict]) -> dict:
    """Fixture/offline helper: stock_pct + synthetic sh/sector curves aligned to dates."""
    if not kline_series:
        return unavailable_overlays()

    dates = [bar["date"] for bar in kline_series]
    stock_closes = [float(bar["close"]) for bar in kline_series]
    stock_pct = _pct_from_anchor(stock_closes)
    sh_pct = [round(v * 0.35, 2) if v is not None else None for v in stock_pct]
    sector_pct = [round(v * 0.55, 2) if v is not None else None for v in stock_pct]
    if sh_pct and sh_pct[0] is not None:
        sh_pct[0] = 0.0
    if sector_pct and sector_pct[0] is not None:
        sector_pct[0] = 0.0

    return {
        "status": "ok",
        "reason": None,
        "anchor": OVERLAY_ANCHOR,
        "dates": dates,
        "stock_pct": stock_pct,
        "sh_index": _sh_index_block(status="ok", pct=sh_pct, last_close=3200.0),
        "sector": {
            "code": "BK1277",
            "name": "白酒Ⅱ",
            "status": "ok",
            "pct": sector_pct,
        },
    }


def enrich_overlays_if_missing(fetch_html: dict, benchmark_sector: dict | None) -> dict:
    """Soft enrich during assemble when html-data predates v1.2.0 overlays."""
    if fetch_html.get("overlays"):
        return fetch_html

    kline = fetch_html.get("kline", {})
    series = kline.get("series") or []
    if kline.get("status") == "unavailable" or not series:
        enriched = dict(fetch_html)
        enriched["overlays"] = unavailable_overlays()
        enriched["schema_version"] = "1.2.0"
        return enriched

    sector_code = None
    sector_name = None
    if benchmark_sector:
        sector_code = benchmark_sector.get("index_code")
        sector_name = benchmark_sector.get("name")

    if os.environ.get("STOCK_RADAR_OVERLAY_OFFLINE") == "1":
        overlays = build_overlays_from_stock_only(series)
        if benchmark_sector:
            overlays["sector"]["code"] = sector_code
            overlays["sector"]["name"] = sector_name
            if not sector_code:
                overlays["sector"]["status"] = "skipped"
                overlays["sector"]["pct"] = None
                overlays["status"] = "ok"
                overlays["reason"] = None
    else:
        overlays = build_overlays(
            series,
            sector_index_code=sector_code,
            sector_name=sector_name,
        )

    enriched = dict(fetch_html)
    enriched["schema_version"] = "1.2.0"
    enriched["overlays"] = overlays
    return enriched


def enrich_overlays_sector_if_skipped(fetch_html: dict, benchmark_sector: dict | None) -> dict:
    """Re-fetch concept board overlay when sector was skipped but benchmark name exists."""
    if not benchmark_sector or not benchmark_sector.get("name"):
        return fetch_html
    overlays = fetch_html.get("overlays")
    if not overlays:
        return fetch_html

    sector = overlays.get("sector") or {}
    if sector.get("status") == "ok" and sector.get("pct"):
        return fetch_html

    kline = fetch_html.get("kline") or {}
    series = kline.get("series") or []
    if kline.get("status") == "unavailable" or not series:
        return fetch_html

    fresh = build_overlays(
        series,
        sector_index_code=benchmark_sector.get("index_code"),
        sector_name=benchmark_sector.get("name"),
    )
    enriched = dict(fetch_html)
    merged = dict(overlays)
    merged["sector"] = fresh["sector"]
    if fresh["sector"].get("status") == "ok":
        merged["status"] = "ok" if merged.get("sh_index", {}).get("status") == "ok" else merged.get("status", "ok")
        merged["reason"] = None
    elif fresh.get("status") == "partial":
        merged["status"] = "partial"
        merged["reason"] = fresh.get("reason")
    enriched["overlays"] = merged
    return enriched
