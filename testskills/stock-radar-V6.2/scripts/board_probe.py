"""Unified benchmark-sector board resolve: memo, cache, fund + overlay probes."""
from __future__ import annotations

import concurrent.futures
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import akshare as ak
import akshare.stock.stock_fund_em as stock_fund_em

from board_cache import (
    BOARD_PROBE_MAX,
    normalize_board_cache_key,
    read_board_cache,
    write_board_cache,
)
from board_name_resolve import sector_board_candidates
from fetch_html_common import FETCH_CACHE_DIR, FUND_FLOW_STALE_LAG_DAYS

BOARD_PROBE_TIMEOUT_SEC = float(os.environ.get("STOCK_RADAR_BOARD_PROBE_TIMEOUT", "12"))
BOARD_FUND_CACHE_TTL_HOURS = float(os.environ.get("STOCK_RADAR_BOARD_FUND_CACHE_TTL_HOURS", "4"))
BOARD_OVERLAY_CACHE_TTL_HOURS = float(os.environ.get("STOCK_RADAR_BOARD_OVERLAY_CACHE_TTL_HOURS", "4"))

_PROBE_MEMO: dict[str, BoardResolveResult] = {}


def reset_probe_memo() -> None:
    _PROBE_MEMO.clear()


def _cache_key(sector_name: str, index_code: str | None = None) -> str:
    name = normalize_board_cache_key(sector_name)
    code = (index_code or "").strip()
    return f"{name}|{code}" if name else code


def _fund_series_cache_path(sector_name: str) -> str:
    key = normalize_board_cache_key(sector_name).replace("/", "_") or "unknown"
    return str(FETCH_CACHE_DIR / "board" / f"{key}.fund.json")


def _overlay_series_cache_path(sector_name: str) -> str:
    key = normalize_board_cache_key(sector_name).replace("/", "_") or "unknown"
    return str(FETCH_CACHE_DIR / "board" / f"{key}.overlay.json")


def _is_connection_error(error: str | None) -> bool:
    text = str(error or "").lower()
    return any(
        token in text
        for token in (
            "connection",
            "timeout",
            "remotedisconnected",
            "refused",
            "reset",
            "aborted",
            "broken pipe",
            "timed out",
            "proxy",
            "403",
            "forbidden",
        )
    )


def _call_with_timeout(fn: Callable[[], Any], timeout_sec: float, retries: int = 1) -> tuple[Any, str | None]:
    last_error: str | None = None
    for _ in range(max(1, retries)):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fn)
            try:
                result = future.result(timeout=timeout_sec)
                return result, None
            except concurrent.futures.TimeoutError:
                last_error = "timeout"
            except Exception as exc:
                last_error = str(exc)
    return None, last_error


@dataclass
class BoardResolveResult:
    requested_name: str
    matched_name: str | None = None
    index_code: str | None = None
    kind: str | None = None
    fund_df: Any = None
    overlay_df: Any = None
    fund_series: list[dict] = field(default_factory=list)
    connection_errors: int = 0
    probes_used: int = 0
    from_disk_cache: bool = False
    fund_from_cache: bool = False
    overlay_from_cache: bool = False
    overlay_closes: dict[str, float] | None = None
    last_error: str | None = None

    @property
    def all_connection_failures(self) -> bool:
        return self.probes_used > 0 and self.connection_errors >= self.probes_used and not self.fund_df

    def placeholder_reason(self, *, for_fund: bool = True) -> str:
        label = self.requested_name
        if self.all_connection_failures or _is_connection_error(self.last_error):
            if self.matched_name and self.matched_name != label:
                return f"东财板块接口连接中断（预期板块：{self.matched_name}），请稍后重试"
            return "东财板块接口连接中断，请稍后重试"
        if for_fund:
            return f"未匹配到「{label}」的概念/行业资金流"
        return f"板块「{label}」指数 overlay 不可用"


def _normalize_date(value: Any) -> str:
    text = str(value).strip()
    if " " in text:
        text = text.split(" ", 1)[0]
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10]


def _rows_from_fund_df(df) -> list[dict]:
    if df is None or df.empty:
        return []
    rows: list[dict] = []
    for _, row in df.tail(5).iterrows():
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
    return rows


def write_board_fund_series_cache(sector_name: str, rows: list[dict], matched_name: str, kind: str) -> None:
    path = Path(_fund_series_cache_path(sector_name))
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "requested_name": sector_name,
        "matched_name": matched_name,
        "kind": kind,
        "fetched_at": datetime.now().isoformat(),
        "series": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_board_fund_series_cache(sector_name: str) -> dict | None:
    path = Path(_fund_series_cache_path(sector_name))
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
            if age > timedelta(hours=BOARD_FUND_CACHE_TTL_HOURS):
                return None
        except ValueError:
            pass
    if not payload.get("series"):
        return None
    return payload


    return payload


def _closes_from_hist_df(df) -> dict[str, float]:
    if df is None or getattr(df, "empty", True):
        return {}
    date_col = "date" if "date" in df.columns else "日期"
    close_col = "close" if "close" in df.columns else "收盘"
    mapping: dict[str, float] = {}
    for _, row in df.iterrows():
        day = _normalize_date(row[date_col])
        mapping[day] = float(row[close_col])
    return mapping


def write_board_overlay_cache(sector_name: str, closes: dict[str, float], matched_name: str) -> None:
    if not closes:
        return
    path = Path(_overlay_series_cache_path(sector_name))
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "requested_name": sector_name,
        "matched_name": matched_name,
        "fetched_at": datetime.now().isoformat(),
        "closes": closes,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_board_overlay_cache(sector_name: str) -> dict | None:
    path = Path(_overlay_series_cache_path(sector_name))
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
            if age > timedelta(hours=BOARD_OVERLAY_CACHE_TTL_HOURS):
                return None
        except ValueError:
            pass
    if not payload.get("closes"):
        return None
    return payload


def _overlay_cache_time_label(cache_payload: dict | None) -> str:
    if not cache_payload or not cache_payload.get("fetched_at"):
        return "未知时间"
    try:
        return datetime.fromisoformat(str(cache_payload["fetched_at"])).strftime("%H:%M")
    except ValueError:
        text = str(cache_payload.get("fetched_at", ""))
        return text[11:16] if len(text) >= 16 else text[:16]


def sector_overlay_pct_for_dates(dates: list[str], closes: dict[str, float]) -> list[float | None] | None:
    if not dates or not closes:
        return None
    import pandas as pd

    from overlay_fetch import _align_closes_to_dates, _pct_from_anchor

    df = pd.DataFrame([{"日期": day, "收盘": closes[day]} for day in sorted(closes.keys())])
    aligned = _align_closes_to_dates(dates, df)
    pct = _pct_from_anchor(aligned)
    if not any(value is not None for value in pct):
        return None
    return pct


def apply_overlay_df_to_result(result: BoardResolveResult, df, sector_name: str) -> None:
    if df is None or getattr(df, "empty", True):
        return
    result.overlay_df = df
    closes = _closes_from_hist_df(df)
    if closes and sector_name:
        write_board_overlay_cache(
            sector_name,
            closes,
            result.matched_name or result.requested_name,
        )


def load_overlay_cache_into_result(result: BoardResolveResult, sector_name: str) -> bool:
    cache = read_board_overlay_cache(sector_name)
    if not cache:
        return False
    closes = cache.get("closes") or {}
    if not closes:
        return False
    result.overlay_closes = {str(k): float(v) for k, v in closes.items()}
    result.overlay_from_cache = True
    result.matched_name = result.matched_name or cache.get("matched_name")
    return True


def sector_overlay_from_resolved(
    dates: list[str],
    resolved: BoardResolveResult,
    sector_name: str,
) -> tuple[list[float | None] | None, str | None, str | None]:
    """Return (pct series, matched_name, overlay_stale_note)."""
    if resolved.overlay_df is not None and not getattr(resolved.overlay_df, "empty", True):
        from overlay_fetch import _align_closes_to_dates, _pct_from_anchor

        aligned = _align_closes_to_dates(dates, resolved.overlay_df)
        pct = _pct_from_anchor(aligned)
        if any(value is not None for value in pct):
            return pct, resolved.matched_name, None

    if resolved.overlay_closes or resolved.overlay_from_cache:
        closes = resolved.overlay_closes or {}
        if not closes and sector_name:
            cache = read_board_overlay_cache(sector_name)
            if cache:
                closes = cache.get("closes") or {}
                resolved.matched_name = resolved.matched_name or cache.get("matched_name")
        pct = sector_overlay_pct_for_dates(dates, closes)
        if pct:
            cache = read_board_overlay_cache(sector_name)
            label = _overlay_cache_time_label(cache)
            note = f"板块指数 overlay 已降级为缓存（缓存于 {label}）"
            return pct, resolved.matched_name, note

    if sector_name and load_overlay_cache_into_result(resolved, sector_name):
        return sector_overlay_from_resolved(dates, resolved, sector_name)

    return None, resolved.matched_name, None


def _fetch_fund_hist(matched_name: str, kind: str, *, retries: int = 1):
    def _load():
        if kind == "sector":
            return ak.stock_sector_fund_flow_hist(symbol=matched_name)
        return ak.stock_concept_fund_flow_hist(symbol=matched_name)

    return _call_with_timeout(_load, BOARD_PROBE_TIMEOUT_SEC, retries=retries)


def _fetch_overlay_concept_hist(name: str, start: str, end: str, *, retries: int = 1):
    start_compact = start.replace("-", "")
    end_compact = end.replace("-", "")

    def _load():
        return ak.stock_board_concept_hist_em(
            symbol=name,
            period="daily",
            start_date=start_compact,
            end_date=end_compact,
            adjust="",
        )

    return _call_with_timeout(_load, BOARD_PROBE_TIMEOUT_SEC, retries=retries)


def _fetch_overlay_industry_hist(code: str, start: str, end: str, *, retries: int = 1):
    start_compact = start.replace("-", "")
    end_compact = end.replace("-", "")

    def _load():
        return ak.stock_board_industry_hist_em(
            symbol=code,
            start_date=start_compact,
            end_date=end_compact,
            period="日k",
            adjust="",
        )

    return _call_with_timeout(_load, BOARD_PROBE_TIMEOUT_SEC, retries=retries)


def _load_name_maps_once() -> tuple[dict, dict, int]:
    connection_errors = 0

    def concept_load():
        return stock_fund_em._get_stock_concept_fund_flow_summary_code()

    concept_map, err = _call_with_timeout(concept_load, BOARD_PROBE_TIMEOUT_SEC, retries=1)
    if err:
        connection_errors += 1
        concept_map = {}

    def sector_load():
        return stock_fund_em._get_stock_sector_fund_flow_summary_code()

    sector_map, err = _call_with_timeout(sector_load, BOARD_PROBE_TIMEOUT_SEC, retries=1)
    if err:
        connection_errors += 1
        sector_map = {}

    return (
        concept_map if isinstance(concept_map, dict) else {},
        sector_map if isinstance(sector_map, dict) else {},
        connection_errors,
    )


def _resolve_from_maps(sector_name: str, concept_map: dict, sector_map: dict) -> tuple[str, str] | None:
    for keyword in sector_board_candidates(sector_name):
        if concept_map:
            if keyword in concept_map:
                return keyword, "concept"
            for name in concept_map:
                if keyword in name or name in keyword:
                    return name, "concept"
        if sector_map:
            if keyword in sector_map:
                return keyword, "sector"
            for name in sector_map:
                if keyword in name or name in keyword:
                    return name, "sector"
    return None


def resolve_board(
    sector_name: str,
    index_code: str | None = None,
    *,
    overlay_start: str | None = None,
    overlay_end: str | None = None,
) -> BoardResolveResult:
    requested = (sector_name or "").strip()
    code = (index_code or "").strip() or None
    memo_key = _cache_key(requested, code)
    if memo_key in _PROBE_MEMO:
        return _PROBE_MEMO[memo_key]

    result = BoardResolveResult(requested_name=requested, index_code=code)
    cached = read_board_cache(requested) if requested else None
    if cached:
        result.from_disk_cache = True
        result.matched_name = cached.get("matched_name") or result.matched_name
        result.kind = cached.get("kind") or result.kind
        if not code and cached.get("index_code"):
            result.index_code = str(cached["index_code"]).strip() or None

    fund_cache = read_board_fund_series_cache(requested) if requested else None
    if fund_cache:
        result.fund_series = fund_cache.get("series") or []
        result.matched_name = result.matched_name or fund_cache.get("matched_name")
        result.kind = result.kind or fund_cache.get("kind")
        result.fund_from_cache = True

    if code and overlay_start and overlay_end:
        df, err = _fetch_overlay_industry_hist(code, overlay_start, overlay_end, retries=2)
        result.probes_used += 1
        if err:
            result.connection_errors += 1
            result.last_error = err
        elif df is not None and not df.empty:
            apply_overlay_df_to_result(result, df, requested)
            result.matched_name = result.matched_name or requested

        fund_df, fund_err = _fetch_fund_hist(requested or code, "sector", retries=1)
        result.probes_used += 1
        if fund_err:
            result.connection_errors += 1
            result.last_error = fund_err
        elif fund_df is not None and not fund_df.empty:
            result.fund_df = fund_df
            rows = _rows_from_fund_df(fund_df)
            if rows:
                result.fund_series = rows
                write_board_fund_series_cache(requested, rows, requested, "sector")
                write_board_cache(requested, matched_name=requested, index_code=code, kind="sector")

        _PROBE_MEMO[memo_key] = result
        return result

    if cached and cached.get("matched_name"):
        matched = cached["matched_name"]
        kind = cached.get("kind") or "concept"
        result.matched_name = matched
        result.kind = kind
        fund_df, err = _fetch_fund_hist(matched, kind, retries=2)
        result.probes_used += 1
        if err:
            result.connection_errors += 1
            result.last_error = err
        elif fund_df is not None and not fund_df.empty:
            result.fund_df = fund_df
            rows = _rows_from_fund_df(fund_df)
            result.fund_series = rows
            write_board_fund_series_cache(requested, rows, matched, kind)

        if overlay_start and overlay_end and kind == "concept":
            odf, oerr = _fetch_overlay_concept_hist(matched, overlay_start, overlay_end, retries=2)
            result.probes_used += 1
            if oerr:
                result.connection_errors += 1
                result.last_error = oerr
            elif odf is not None and not odf.empty:
                apply_overlay_df_to_result(result, odf, requested)

        if result.fund_df is not None or result.overlay_df is not None:
            _PROBE_MEMO[memo_key] = result
            return result

    candidates = sector_board_candidates(requested)
    for idx, candidate in enumerate(candidates):
        if result.probes_used >= BOARD_PROBE_MAX:
            break
        retries = 2 if idx == 0 else 1
        fund_df, err = _fetch_fund_hist(candidate, "concept", retries=retries)
        result.probes_used += 1
        if err:
            result.connection_errors += 1
            result.last_error = err
            continue
        if fund_df is None or fund_df.empty:
            continue

        result.fund_df = fund_df
        result.matched_name = candidate
        result.kind = "concept"
        rows = _rows_from_fund_df(fund_df)
        result.fund_series = rows
        write_board_cache(requested, matched_name=candidate, kind="concept", requested_name=requested)
        write_board_fund_series_cache(requested, rows, candidate, "concept")

        if overlay_start and overlay_end:
            odf, oerr = _fetch_overlay_concept_hist(candidate, overlay_start, overlay_end, retries=1)
            result.probes_used += 1
            if oerr:
                result.connection_errors += 1
                result.last_error = oerr
            elif odf is not None and not odf.empty:
                apply_overlay_df_to_result(result, odf, requested)
        break

    if result.fund_df is None and result.probes_used < BOARD_PROBE_MAX:
        concept_map, sector_map, map_errors = _load_name_maps_once()
        result.connection_errors += map_errors
        result.probes_used += 2
        resolved = _resolve_from_maps(requested, concept_map, sector_map)
        if resolved:
            matched_name, kind = resolved
            result.matched_name = matched_name
            result.kind = kind
            if result.probes_used < BOARD_PROBE_MAX:
                fund_df, err = _fetch_fund_hist(matched_name, kind, retries=1)
                result.probes_used += 1
                if err:
                    result.connection_errors += 1
                    result.last_error = err
                elif fund_df is not None and not fund_df.empty:
                    result.fund_df = fund_df
                    rows = _rows_from_fund_df(fund_df)
                    result.fund_series = rows
                    write_board_cache(requested, matched_name=matched_name, kind=kind, requested_name=requested)
                    write_board_fund_series_cache(requested, rows, matched_name, kind)

    if result.fund_series and result.fund_df is None and result.fund_from_cache:
        pass

    if overlay_start and overlay_end and result.overlay_df is None and requested:
        load_overlay_cache_into_result(result, requested)

    _PROBE_MEMO[memo_key] = result
    return result


def _trading_lag(trading_dates: list[str], as_of: str, reference: str) -> int:
    if not trading_dates or not as_of or not reference:
        return 0
    if as_of >= reference:
        return 0
    return sum(1 for day in trading_dates if as_of < day <= reference)


def _placeholder_benchmark_sector_fund_flow(
    reason: str,
    sector_name: str | None = None,
    requested_name: str | None = None,
) -> dict:
    return {
        "status": "placeholder",
        "reason_code": "UNCONFIGURED" if not sector_name else "FETCH_FAILED",
        "reason": reason,
        "requested_name": requested_name or sector_name,
        "sector_name": sector_name,
        "matched_name": None,
        "as_of_date": None,
        "reference_date": None,
        "lag_trading_days": None,
        "series": [],
    }


def build_benchmark_sector_fund_block(
    benchmark_sector: dict | None,
    reference_date: str | None,
    trading_dates: list[str],
    resolved: BoardResolveResult | None = None,
) -> dict:
    sector_name = (benchmark_sector or {}).get("name")
    index_code = (benchmark_sector or {}).get("index_code")
    requested_name = sector_name
    if not sector_name:
        return _placeholder_benchmark_sector_fund_flow("未配置 benchmark_sector，板块近 5 日资金流暂缺")

    probe = resolved or resolve_board(sector_name, index_code)
    rows = _rows_from_fund_df(probe.fund_df) if probe.fund_df is not None else list(probe.fund_series)
    from_cache = probe.fund_from_cache and probe.fund_df is None

    if not rows:
        return _placeholder_benchmark_sector_fund_flow(
            probe.placeholder_reason(for_fund=True),
            sector_name=sector_name,
            requested_name=requested_name,
        )

    as_of_date = rows[-1]["date"]
    lag = _trading_lag(trading_dates, as_of_date, reference_date or "") if reference_date else None

    if from_cache:
        cache_label = "缓存"
        fund_cache = read_board_fund_series_cache(sector_name)
        if fund_cache and fund_cache.get("fetched_at"):
            try:
                cache_label = datetime.fromisoformat(str(fund_cache["fetched_at"])).strftime("%H:%M")
            except ValueError:
                pass
        return {
            "status": "stale",
            "reason_code": "API_STALE" if (lag or 0) > 30 else "LAG_EXCEEDS_THRESHOLD",
            "reason": f"实时板块接口不可用，已降级为缓存（缓存于 {cache_label}）",
            "requested_name": requested_name,
            "sector_name": sector_name,
            "matched_name": probe.matched_name,
            "as_of_date": as_of_date,
            "reference_date": reference_date,
            "lag_trading_days": lag if lag and lag > 0 else 1,
            "series": rows,
            "source": "board_fund_cache",
        }

    if lag is None:
        return _placeholder_benchmark_sector_fund_flow(
            "无法计算板块资金流滞后",
            sector_name=sector_name,
            requested_name=requested_name,
        )

    kind = probe.kind or "concept"
    if lag > FUND_FLOW_STALE_LAG_DAYS:
        status = "stale"
        if lag > 30:
            reason_code = "API_STALE"
            reason = f"板块资金数据截至 {as_of_date}，与 K 线 {reference_date} 严重不同步"
        else:
            reason_code = "LAG_EXCEEDS_THRESHOLD"
            reason = f"板块资金数据截至 {as_of_date}，落后 K 线 {lag} 个交易日"
    else:
        status = "ok"
        reason_code = None
        reason = None

    source = (
        "akshare_stock_sector_fund_flow_hist"
        if kind == "sector"
        else "akshare_stock_concept_fund_flow_hist"
    )
    return {
        "status": status,
        "reason_code": reason_code,
        "reason": reason,
        "requested_name": requested_name,
        "sector_name": sector_name,
        "matched_name": probe.matched_name,
        "as_of_date": as_of_date,
        "reference_date": reference_date,
        "lag_trading_days": lag,
        "series": rows,
        "source": source,
    }


def enrich_fetch_html_sector_board(
    fetch_html: dict,
    benchmark_sector: dict | None,
    *,
    reference_date: str | None = None,
    trading_dates: list[str] | None = None,
) -> dict:
    """Single memoized probe: refresh sector fund + overlay sector when degraded."""
    if not benchmark_sector or not benchmark_sector.get("name"):
        return fetch_html

    enriched = dict(fetch_html)
    kline = enriched.get("kline") or {}
    series = kline.get("series") or []
    if not series:
        return enriched

    dates = trading_dates or [bar["date"] for bar in series]
    ref = reference_date or dates[-1]
    overlay_start = dates[0]
    overlay_end = dates[-1]

    sector_name = benchmark_sector.get("name")
    index_code = benchmark_sector.get("index_code")
    sector_fund = enriched.get("benchmark_sector_fund_flow") or {}
    overlays = dict(enriched.get("overlays") or {})
    sector = dict(overlays.get("sector") or {})
    fund_ready = sector_fund.get("status") in ("ok", "stale") and bool(sector_fund.get("series"))
    needs_fund = sector_fund.get("status") in ("placeholder", "error", None)
    needs_overlay = sector.get("status") != "ok" or not sector.get("pct")

    if not needs_fund and not needs_overlay:
        return enriched

    resolved = None
    if fund_ready and needs_overlay:
        matched = sector_fund.get("matched_name") or sector_name
        resolved = BoardResolveResult(
            requested_name=sector_name,
            matched_name=matched,
            index_code=index_code,
            kind="concept",
        )
        odf, _ = _fetch_overlay_concept_hist(matched, overlay_start, overlay_end, retries=2)
        if odf is not None and not odf.empty:
            apply_overlay_df_to_result(resolved, odf, sector_name)
    else:
        resolved = resolve_board(
            sector_name,
            index_code,
            overlay_start=overlay_start,
            overlay_end=overlay_end,
        )
        if needs_fund:
            enriched["benchmark_sector_fund_flow"] = build_benchmark_sector_fund_block(
                benchmark_sector,
                ref,
                dates,
                resolved=resolved,
            )

    if needs_overlay and resolved.matched_name and (
        resolved.overlay_df is None or getattr(resolved.overlay_df, "empty", True)
    ):
        odf, _ = _fetch_overlay_concept_hist(
            resolved.matched_name,
            overlay_start,
            overlay_end,
            retries=1,
        )
        if odf is not None and not odf.empty:
            apply_overlay_df_to_result(resolved, odf, sector_name)

    if needs_overlay:
        load_overlay_cache_into_result(resolved, sector_name)
        sector_pct, matched, stale_note = sector_overlay_from_resolved(dates, resolved, sector_name)
        if sector_pct:
            overlays["sector"] = {
                "code": index_code or sector.get("code"),
                "name": matched or sector_name,
                "status": "ok",
                "pct": sector_pct,
            }
            if overlays.get("sh_index", {}).get("status") == "ok":
                overlays["status"] = "ok"
                overlays["reason"] = None
            if stale_note:
                overlays["overlay_stale_note"] = stale_note
            enriched["overlays"] = overlays

    return enriched
