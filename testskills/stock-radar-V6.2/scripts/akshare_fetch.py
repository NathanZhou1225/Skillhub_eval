"""演示用最小行情/基本面拉取。结论要可追溯，所以拉回来的数据都落盘。

数据源切换说明：东财接口（stock_zh_a_hist）2026-05 期间频繁拒绝连接，
统一改用腾讯源（stock_zh_a_hist_tx）+ 个股资金流东财源（容错跳过）。

V5 脱敏：不向 LLM 暴露 kline OHLC 序列与 MA/60 日高低点绝对价；仅输出
technical_snapshot 枚举 + 标题行可用的 last_close / 涨跌幅等。

Phase 2b：额外输出 <code>.html-data.json（fetch_html 契约），供 HTML 渲染层消费。

注意：summary 里的 last_amount_wan 字段名是历史遗留，腾讯源 amount 字段实际单位是"手"而非"成交额万元"，下游若有引用请按手数解读。
"""
from __future__ import annotations

import json
import os
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import akshare as ak

from fetch_html_common import (
    BARS_REQUESTED,
    FETCH_HTML_SCHEMA_VERSION,
    MIN_KLINE_BARS,
    unavailable_fetch_html,
)
from benchmark_sector_fund_fetch import build_benchmark_sector_fund_flow
from board_probe import reset_probe_memo, resolve_board
from fund_flow_fetch import build_fund_flow_block, fetch_individual_fund_flow, snapshot_fund_flow_recent
from overlay_fetch import build_overlays

warnings.filterwarnings("ignore")

OUT_DIR = Path(os.environ.get("STOCK_RADAR_OUT_DIR", "/tmp/stock-radar"))
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _market_prefix(code: str) -> str:
    if code.startswith(("0", "3")):
        return "sz"
    if code.startswith(("6", "9", "688")):
        return "sh"
    return "sz"


def _normalize_date(value: Any) -> str:
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10]


def _technical_snapshot(kline) -> dict:
    """Derive qualitative technical fields only — no MA prices or absolute 60d high/low."""
    if kline is None or kline.empty or len(kline) < MIN_KLINE_BARS:
        return {}

    tail60 = kline.tail(BARS_REQUESTED)
    last_close = float(tail60.iloc[-1]["close"])
    ma5 = float(tail60.tail(5)["close"].mean())
    ma20 = float(tail60.tail(20)["close"].mean()) if len(tail60) >= 20 else ma5
    ma60 = float(tail60["close"].mean())

    if ma5 > ma20 > ma60:
        ma_alignment = "bullish_stack"
    elif ma5 < ma20 < ma60:
        ma_alignment = "bearish_stack"
    else:
        ma_alignment = "mixed"

    first_20 = tail60.iloc[-20] if len(tail60) >= 20 else tail60.iloc[0]
    first_60 = tail60.iloc[0]
    change_20d = (last_close / float(first_20["close"]) - 1) * 100
    change_60d = (last_close / float(first_60["close"]) - 1) * 100

    if change_20d > 5 and change_60d > 10:
        trend_strength = "upward"
    elif change_20d < -5 and change_60d < -10:
        trend_strength = "downward"
    else:
        trend_strength = "sideways"

    high_60 = float(tail60["high"].max())
    low_60 = float(tail60["low"].min())
    breakout_60d_high = last_close >= high_60 * 0.998
    broke_60d_low = last_close <= low_60 * 1.002
    near_60d_high_pct = round((last_close / high_60 - 1) * 100, 2) if high_60 else None
    near_60d_low_pct = round((last_close / low_60 - 1) * 100, 2) if low_60 else None

    last_amount = float(tail60.iloc[-1]["amount"]) if "amount" in tail60.columns else 0.0
    avg_amount_20 = float(tail60.tail(20)["amount"].mean()) if len(tail60) >= 20 else last_amount
    ratio = last_amount / avg_amount_20 if avg_amount_20 else 1.0
    if ratio >= 1.5:
        volume_vs_20d = "elevated"
    elif ratio <= 0.7:
        volume_vs_20d = "subdued"
    else:
        volume_vs_20d = "normal"

    return {
        "ma_alignment": ma_alignment,
        "trend_strength": trend_strength,
        "breakout_60d_high": breakout_60d_high,
        "broke_60d_low": broke_60d_low,
        "near_60d_high_pct": near_60d_high_pct,
        "near_60d_low_pct": near_60d_low_pct,
        "volume_vs_20d": volume_vs_20d,
        "change_20d_pct": round(change_20d, 2),
        "change_60d_pct": round(change_60d, 2),
    }


def _rolling_ma(closes: list[float], window: int) -> list[float | None]:
    result: list[float | None] = []
    for i in range(len(closes)):
        if i + 1 < window:
            result.append(None)
        else:
            chunk = closes[i + 1 - window : i + 1]
            result.append(round(sum(chunk) / window, 4))
    return result


def _kline_series_from_df(kline) -> list[dict]:
    rows: list[dict] = []
    for _, row in kline.iterrows():
        rows.append(
            {
                "date": _normalize_date(row["date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "amount_lots": float(row["amount"]),
            }
        )
    return rows


def _build_kline_block(kline) -> tuple[dict, list[dict], dict | None]:
    if kline is None or kline.empty or len(kline) < MIN_KLINE_BARS:
        reason = "FETCH_FAILED" if kline is None or (hasattr(kline, "empty") and kline.empty) else "INSUFFICIENT_BARS"
        human = "行情数据不可用" if reason == "FETCH_FAILED" else f"可用 K 线不足 {MIN_KLINE_BARS} 根"
        block = {
            "status": "unavailable",
            "reason_code": reason,
            "reason": human,
            "bars_available": 0,
            "bars_requested": BARS_REQUESTED,
            "series": [],
        }
        return block, [], None

    tail = kline.tail(BARS_REQUESTED)
    series = _kline_series_from_df(tail)
    n = len(series)
    if n >= BARS_REQUESTED:
        status = "ok"
        block = {
            "status": "ok",
            "reason_code": None,
            "reason": None,
            "bars_available": BARS_REQUESTED,
            "bars_requested": BARS_REQUESTED,
            "series": series,
        }
    else:
        block = {
            "status": "partial",
            "reason_code": "IPO_SHORT_HISTORY",
            "reason": f"仅 {n} 日 K 线，不足 {BARS_REQUESTED} 日",
            "bars_available": n,
            "bars_requested": BARS_REQUESTED,
            "series": series,
        }

    annotations = _technical_snapshot(kline)
    return block, series, annotations or None


def _build_ma_overlay(series: list[dict]) -> dict:
    closes = [bar["close"] for bar in series]
    return {
        "ma5": _rolling_ma(closes, 5),
        "ma20": _rolling_ma(closes, 20),
        "ma60": _rolling_ma(closes, 60),
    }


def build_fetch_html(
    code: str,
    kline,
    fund,
    fund_error: str | None,
    fetched_at: str,
    sector_index_code: str | None = None,
    sector_name: str | None = None,
    fund_meta: dict | None = None,
) -> dict:
    kline_block, series, annotations = _build_kline_block(kline)
    ma_overlay = _build_ma_overlay(series) if series else {"ma5": [], "ma20": [], "ma60": []}

    trading_dates = [_normalize_date(d) for d in kline["date"].tolist()] if kline is not None and not kline.empty else []
    reference_date = series[-1]["date"] if series else (trading_dates[-1] if trading_dates else None)

    if series:
        resolved = None
        if sector_name or sector_index_code:
            resolved = resolve_board(
                sector_name or "",
                sector_index_code,
                overlay_start=series[0]["date"],
                overlay_end=series[-1]["date"],
            )
        overlays = build_overlays(
            series,
            sector_index_code=sector_index_code,
            sector_name=sector_name,
            resolved=resolved,
        )
    else:
        from overlay_fetch import unavailable_overlays

        overlays = unavailable_overlays()
        resolved = None

    benchmark = {"name": sector_name, "index_code": sector_index_code} if sector_name else None
    benchmark_sector_fund_flow = build_benchmark_sector_fund_flow(
        benchmark,
        reference_date,
        trading_dates,
        resolved=resolved,
    )

    return {
        "schema_version": FETCH_HTML_SCHEMA_VERSION,
        "code": code,
        "fetched_at": fetched_at,
        "source": "akshare_tx+fund_flow",
        "kline": kline_block,
        "ma_overlay": ma_overlay,
        "fund_flow": build_fund_flow_block(
            fund,
            fund_error,
            reference_date,
            trading_dates,
            from_cache=(fund_meta or {}).get("source") == "cache",
            cache_fetched_at=(fund_meta or {}).get("cache_fetched_at"),
        ),
        "annotations": annotations if kline_block["status"] != "unavailable" else None,
        "overlays": overlays,
        "benchmark_sector_fund_flow": benchmark_sector_fund_flow,
    }


def fetch(
    code: str,
    name: str,
    sector_index_code: str | None = None,
    sector_name: str | None = None,
) -> dict:
    reset_probe_memo()
    fetched_at = datetime.now().isoformat()
    snapshot = {"code": code, "name": name, "fetched_at": fetched_at}
    market = _market_prefix(code)
    tx_symbol = f"{market}{code}"

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")

    kline = None
    try:
        kline = ak.stock_zh_a_hist_tx(symbol=tx_symbol, start_date=start, end_date=end, adjust="qfq")
    except Exception:
        kline = None

    if kline is not None and not kline.empty:
        kline = kline.copy()
        kline["date"] = kline["date"].astype(str)
        for col in ("open", "close", "high", "low", "amount"):
            if col in kline.columns:
                kline[col] = kline[col].astype(float)

        last = kline.iloc[-1]
        first_60 = kline.iloc[-60] if len(kline) >= 60 else kline.iloc[0]
        first_20 = kline.iloc[-20] if len(kline) >= 20 else kline.iloc[0]
        first_5 = kline.iloc[-5] if len(kline) >= 5 else kline.iloc[0]
        tech = _technical_snapshot(kline)

        snapshot["summary"] = {
            "last_date": str(last["date"]),
            "last_close": float(last["close"]),
            "last_open": float(last["open"]),
            "last_high": float(last["high"]),
            "last_low": float(last["low"]),
            "last_amount_wan": float(last["amount"]),
            "change_today_pct": round((float(last["close"]) / float(kline.iloc[-2]["close"]) - 1) * 100, 2) if len(kline) >= 2 else None,
            "change_5d_pct": round((float(last["close"]) / float(first_5["close"]) - 1) * 100, 2),
            "change_20d_pct": tech.get("change_20d_pct") or round((float(last["close"]) / float(first_20["close"]) - 1) * 100, 2),
            "change_60d_pct": tech.get("change_60d_pct") or round((float(last["close"]) / float(first_60["close"]) - 1) * 100, 2),
            "avg_amount_20d_wan": round(float(kline.tail(20)["amount"].mean()), 0),
            "amount_ratio_vs_20d": round(float(last["amount"]) / float(kline.tail(20)["amount"].mean()), 2) if len(kline) >= 20 else None,
            "technical_snapshot": tech,
        }

    fund, fund_error, fund_meta = fetch_individual_fund_flow(code, market)
    recent_fund = snapshot_fund_flow_recent(fund)
    if recent_fund:
        snapshot["fund_flow_recent_5"] = recent_fund
    if fund_error and (fund is None or fund.empty):
        snapshot["fund_flow_error"] = fund_error
    elif fund_meta.get("source") == "cache":
        snapshot["fund_flow_cache_at"] = fund_meta.get("cache_fetched_at")
        snapshot["fund_flow_error"] = fund_meta.get("live_error")

    try:
        info = ak.stock_individual_info_em(symbol=code)
        snapshot["info"] = dict(zip(info["item"], info["value"].astype(str)))
    except Exception as e:
        snapshot["info_error"] = str(e)

    html_data = build_fetch_html(
        code,
        kline,
        fund,
        fund_error if fund is None or fund.empty else None,
        fetched_at,
        sector_index_code=sector_index_code,
        sector_name=sector_name,
        fund_meta=fund_meta,
    )

    out_path = OUT_DIR / f"{code}.json"
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    html_path = OUT_DIR / f"{code}.html-data.json"
    html_path.write_text(json.dumps(html_data, ensure_ascii=False, indent=2), encoding="utf-8")

    snapshot["_html_data_path"] = str(html_path)
    return snapshot


if __name__ == "__main__":
    default_targets = [
        ("300308", "中际旭创"),
        ("300276", "三丰智能"),
        ("600519", "贵州茅台"),
        ("002407", "多氟多"),
        ("688017", "绿的谐波"),
    ]
    sector_index_code = os.environ.get("STOCK_RADAR_SECTOR_INDEX_CODE")
    sector_name = os.environ.get("STOCK_RADAR_SECTOR_NAME")
    if len(sys.argv) > 1:
        code_arg = sys.argv[1]
        name_arg = sys.argv[2] if len(sys.argv) > 2 else ""
        if len(sys.argv) > 3:
            sector_index_code = sys.argv[3]
        if len(sys.argv) > 4:
            sector_name = sys.argv[4]
        if not name_arg:
            try:
                info = ak.stock_individual_info_em(symbol=code_arg)
                info_map = dict(zip(info["item"], info["value"].astype(str)))
                name_arg = info_map.get("股票简称", code_arg)
            except Exception:
                name_arg = code_arg
        targets = [(code_arg, name_arg)]
    else:
        targets = default_targets
    for code, name in targets:
        try:
            s = fetch(code, name, sector_index_code=sector_index_code, sector_name=sector_name)
            print(f"[OK] {code} {name}")
            print(f"  summary: {s.get('summary', {})}")
            print(f"  html-data: {s.get('_html_data_path')}")
            if "kline_recent_60" in s:
                print("  WARN: kline_recent_60 should not be present in V5 output")
            if "fund_flow_error" in s:
                print(f"  fund_flow_error: {s['fund_flow_error']}")
            if "info_error" in s:
                print(f"  info_error: {s['info_error']}")
        except Exception as e:
            print(f"[FAIL] {code} {name}: {e}")
