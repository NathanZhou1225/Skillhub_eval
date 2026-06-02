#!/usr/bin/env python3
"""Assemble full diagnosis bundle by merging agent bundle with fetch artifacts."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from fetch_html_common import unavailable_fetch_html
from board_probe import enrich_fetch_html_sector_board, reset_probe_memo
from overlay_fetch import enrich_overlays_if_missing
from bundle_common import DEFAULT_FETCH_DIR, DEFAULT_OUTPUT_DIR, SCHEMA_VERSION


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def assemble(agent_bundle: dict, code: str, fetch_dir: Path) -> dict:
    merged = dict(agent_bundle)
    merged.setdefault("schema_version", SCHEMA_VERSION)

    fetch_path = fetch_dir / f"{code}.json"
    html_data_path = fetch_dir / f"{code}.html-data.json"

    fetch = _load_json(fetch_path)
    if fetch:
        merged["fetch"] = fetch
    elif "fetch" in merged:
        pass
    else:
        merged["fetch"] = {"code": code, "missing": True, "path": str(fetch_path)}

    fetch_html = _load_json(html_data_path)
    if fetch_html:
        benchmark = agent_bundle.get("meta", {}).get("benchmark_sector")
        reset_probe_memo()
        enrich_started = time.monotonic()
        fetch_html = enrich_overlays_if_missing(fetch_html, benchmark)
        kline = fetch_html.get("kline") or {}
        series = kline.get("series") or []
        trading_dates = [bar["date"] for bar in series]
        reference_date = series[-1]["date"] if series else None
        fetch_html = enrich_fetch_html_sector_board(
            fetch_html,
            benchmark,
            reference_date=reference_date,
            trading_dates=trading_dates,
        )
        enrich_elapsed = time.monotonic() - enrich_started
        fetch_html.setdefault("_assemble_meta", {})["sector_enrich_sec"] = round(enrich_elapsed, 2)
        merged["fetch_html"] = fetch_html
    else:
        merged["fetch_html"] = unavailable_fetch_html(
            code,
            reason_code="FETCH_FAILED",
            reason=f"html-data not found at {html_data_path}",
        )

    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge fetch data into diagnosis bundle")
    parser.add_argument("bundle", type=Path, help="Agent-written *.bundle.json (no fetch)")
    parser.add_argument(
        "--fetch-dir",
        type=Path,
        default=Path(os.environ.get("STOCK_RADAR_OUT_DIR", str(DEFAULT_FETCH_DIR))),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("STOCK_RADAR_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Explicit output path (default: output-dir/<code>/<ts>.assembled.bundle.json)",
    )
    args = parser.parse_args()

    try:
        agent_bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read bundle: {exc}", file=sys.stderr)
        return 2

    code = agent_bundle.get("meta", {}).get("code")
    if not code:
        print("ERROR: bundle.meta.code is required", file=sys.stderr)
        return 2

    merged = assemble(agent_bundle, code, args.fetch_dir)

    if args.output:
        out_path = args.output
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = args.output_dir / code
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{ts}.assembled.bundle.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    enrich_sec = (merged.get("fetch_html") or {}).get("_assemble_meta", {}).get("sector_enrich_sec")
    if enrich_sec is not None:
        print(f"sector_enrich_sec={enrich_sec}", file=sys.stderr)
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
