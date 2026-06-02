"""Benchmark sector 5-day main-force fund flow for fetch_html v1.4.0."""
from __future__ import annotations

from board_probe import build_benchmark_sector_fund_block, resolve_board


def placeholder_benchmark_sector_fund_flow(
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


def build_benchmark_sector_fund_flow(
    benchmark_sector: dict | None,
    reference_date: str | None,
    trading_dates: list[str],
    resolved=None,
) -> dict:
    sector_name = (benchmark_sector or {}).get("name")
    index_code = (benchmark_sector or {}).get("index_code")
    if resolved is None and sector_name:
        overlay_start = trading_dates[0] if trading_dates else None
        overlay_end = trading_dates[-1] if trading_dates else None
        resolved = resolve_board(
            sector_name,
            index_code,
            overlay_start=overlay_start,
            overlay_end=overlay_end,
        )
    return build_benchmark_sector_fund_block(
        benchmark_sector,
        reference_date,
        trading_dates,
        resolved=resolved,
    )


def enrich_benchmark_sector_fund_if_missing(
    fetch_html: dict,
    benchmark_sector: dict | None,
    reference_date: str | None = None,
    trading_dates: list[str] | None = None,
) -> dict:
    existing = fetch_html.get("benchmark_sector_fund_flow")
    if existing and existing.get("status") not in ("placeholder",):
        return fetch_html

    enriched = dict(fetch_html)
    ref = reference_date
    dates = trading_dates or []
    if not ref:
        kline = fetch_html.get("kline") or {}
        series = kline.get("series") or []
        if series:
            ref = series[-1]["date"]
            dates = [bar["date"] for bar in series]
    enriched["benchmark_sector_fund_flow"] = build_benchmark_sector_fund_flow(
        benchmark_sector,
        ref,
        dates,
    )
    if enriched.get("schema_version") in ("1.3.0", "1.2.0", "1.1.0", "1.0.0"):
        enriched["schema_version"] = "1.4.0"
    enriched.pop("concept_fund_flow", None)
    return enriched
