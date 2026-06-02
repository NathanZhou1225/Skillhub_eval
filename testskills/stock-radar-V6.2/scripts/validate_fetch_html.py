#!/usr/bin/env python3
"""Validate fetch_html JSON: Schema + three-state logic + MA length alignment."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

from fetch_html_common import BARS_REQUESTED, FETCH_HTML_SCHEMA_PATH, MIN_KLINE_BARS


def validate_logic(doc: dict) -> list[str]:
    errors: list[str] = []
    kline = doc["kline"]
    ma = doc["ma_overlay"]
    status = kline["status"]
    series = kline["series"]
    n = len(series)

    if kline["bars_available"] != n:
        errors.append(f"logic: kline.bars_available={kline['bars_available']} != len(series)={n}")

    if status == "ok" and n != BARS_REQUESTED:
        errors.append(f"logic: kline.status=ok requires {BARS_REQUESTED} bars, got {n}")
    if status == "partial" and not (MIN_KLINE_BARS <= n < BARS_REQUESTED):
        errors.append(
            f"logic: kline.status=partial requires {MIN_KLINE_BARS}..{BARS_REQUESTED - 1} bars, got {n}"
        )
    if status == "unavailable" and n != 0:
        errors.append(f"logic: kline.status=unavailable requires empty series, got {n}")

    for key in ("ma5", "ma20", "ma60"):
        arr = ma[key]
        if status == "unavailable":
            if arr:
                errors.append(f"logic: ma_overlay.{key} must be empty when kline unavailable")
        elif len(arr) != n:
            errors.append(f"logic: ma_overlay.{key} length {len(arr)} != kline series {n}")

    ann = doc.get("annotations")
    if status == "unavailable":
        if ann is not None:
            errors.append("logic: annotations must be null when kline unavailable")
    elif ann is None:
        errors.append("logic: annotations required when kline ok/partial")

    fund = doc["fund_flow"]
    if fund["status"] == "error" and fund["series"]:
        errors.append("logic: fund_flow.status=error requires empty series")
    if fund["status"] in ("ok", "stale") and not fund["series"]:
        errors.append(f"logic: fund_flow.status={fund['status']} requires non-empty series")

    if fund["status"] == "stale":
        lag = fund.get("lag_trading_days")
        if lag is None or lag <= 1:
            errors.append("logic: fund_flow stale requires lag_trading_days > 1")

    for row in fund.get("series") or []:
        inflow = row["main_net_inflow"]
        expected = inflow > 0
        if row["is_net_in"] != expected:
            errors.append(
                f"logic: fund_flow row {row['date']} is_net_in={row['is_net_in']} "
                f"!= (main_net_inflow>0)={expected}"
            )

    overlays = doc.get("overlays")
    if overlays is not None:
        errors.extend(_validate_overlays(kline, overlays))

    sector_fund = doc.get("benchmark_sector_fund_flow")
    if sector_fund is not None:
        errors.extend(_validate_benchmark_sector_fund_flow(sector_fund))

    return errors


def _validate_benchmark_sector_fund_flow(block: dict) -> list[str]:
    errors: list[str] = []
    status = block["status"]
    series = block.get("series") or []

    if status in ("error", "placeholder") and series:
        errors.append(f"logic: benchmark_sector_fund_flow.status={status} requires empty series")
    if status in ("ok", "stale") and not series:
        errors.append(f"logic: benchmark_sector_fund_flow.status={status} requires non-empty series")
    if status == "placeholder" and not block.get("reason"):
        errors.append("logic: benchmark_sector_fund_flow placeholder requires reason")
    if status == "stale":
        lag = block.get("lag_trading_days")
        if lag is None or lag <= 1:
            errors.append("logic: benchmark_sector_fund_flow stale requires lag_trading_days > 1")

    for row in series:
        inflow = row["main_net_inflow"]
        expected = inflow > 0
        if row["is_net_in"] != expected:
            errors.append(
                f"logic: benchmark_sector_fund_flow row {row['date']} is_net_in={row['is_net_in']} "
                f"!= (main_net_inflow>0)={expected}"
            )
    return errors


def _validate_overlays(kline: dict, overlays: dict) -> list[str]:
    errors: list[str] = []
    status = kline["status"]
    series = kline["series"]
    n = len(series)
    o_status = overlays["status"]
    dates = overlays.get("dates") or []
    stock_pct = overlays.get("stock_pct") or []

    if status == "unavailable":
        if o_status != "unavailable":
            errors.append("logic: overlays.status must be unavailable when kline unavailable")
        if dates or stock_pct:
            errors.append("logic: overlays dates/stock_pct must be empty when kline unavailable")
        return errors

    if not dates and o_status != "unavailable":
        errors.append("logic: overlays.dates required when kline ok/partial")
    if len(dates) != n:
        errors.append(f"logic: overlays.dates length {len(dates)} != kline series {n}")
    if len(stock_pct) != n:
        errors.append(f"logic: overlays.stock_pct length {len(stock_pct)} != kline series {n}")

    sh = overlays.get("sh_index") or {}
    if o_status in ("ok", "partial") and sh.get("status") == "ok":
        if len(sh.get("pct") or []) != n:
            errors.append(f"logic: overlays.sh_index.pct length != kline series {n}")
    if o_status == "ok" and sh.get("status") != "ok":
        errors.append("logic: overlays.status=ok requires sh_index.status=ok")

    sector = overlays.get("sector") or {}
    if sector.get("status") == "ok":
        pct = sector.get("pct") or []
        if len(pct) != n:
            errors.append(f"logic: overlays.sector.pct length != kline series {n}")
    elif sector.get("status") == "skipped" and sector.get("pct") is not None:
        errors.append("logic: overlays.sector skipped requires pct=null")

    if o_status == "partial" and sector.get("status") == "ok":
        errors.append("logic: overlays.status=partial should not have sector.status=ok")

    return errors


def validate_fetch_html(doc: dict) -> list[str]:
    schema = json.loads(FETCH_HTML_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []
    for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.path) or "(root)"
        errors.append(f"schema: {path}: {err.message}")
    if not errors:
        errors.extend(validate_logic(doc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate stock-radar fetch_html JSON")
    parser.add_argument("path", type=Path, nargs="?", help="Path to *.html-data.json")
    parser.add_argument("--test", action="store_true", help="Run fixture unit tests")
    parser.add_argument("--json", action="store_true", help="Emit errors as JSON")
    args = parser.parse_args()

    if args.test:
        return run_tests()

    if not args.path:
        parser.error("path required unless --test")

    try:
        doc = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read: {exc}", file=sys.stderr)
        return 2

    errors = validate_fetch_html(doc)
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    elif errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
    else:
        print(f"OK: {args.path}")
    return 1 if errors else 0


def run_tests() -> int:
    board_errors = run_board_name_tests()
    if board_errors:
        for err in board_errors:
            print(f"FAIL board_name: {err}", file=sys.stderr)
        return 1

    fixtures_dir = FETCH_HTML_SCHEMA_PATH.parents[1] / "fixtures" / "html-data"
    paths = sorted(fixtures_dir.glob("*.html-data.json"))
    if not paths:
        print(f"ERROR: no fixtures in {fixtures_dir}", file=sys.stderr)
        return 2

    failed = 0
    for path in paths:
        doc = json.loads(path.read_text(encoding="utf-8"))
        errors = validate_fetch_html(doc)
        if errors:
            failed += 1
            print(f"FAIL {path.name}:", file=sys.stderr)
            for err in errors:
                print(f"  {err}", file=sys.stderr)
        else:
            print(f"OK {path.name}")
    return 1 if failed else 0


def run_board_name_tests() -> list[str]:
    from board_name_resolve import ROBOT_SECTOR_ALIASES, sector_board_candidates

    errors: list[str] = []
    robot_candidates = sector_board_candidates("机器人")
    if not robot_candidates:
        errors.append("机器人 produced empty candidate list")
    elif robot_candidates[0] not in ROBOT_SECTOR_ALIASES:
        errors.append(
            f"机器人 should prioritize ROBOT_SECTOR_ALIASES first, got {robot_candidates[0]!r}"
        )
    if "机器人" in robot_candidates and robot_candidates.index("机器人") < len(ROBOT_SECTOR_ALIASES):
        errors.append("bare 机器人 should appear after ROBOT_SECTOR_ALIASES")
    return errors


if __name__ == "__main__":
    sys.exit(main())
