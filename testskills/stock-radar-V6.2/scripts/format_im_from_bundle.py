#!/usr/bin/env python3
"""Format IM diagnosis text deterministically from diagnosis bundle (single source of truth)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bundle_common import (
    DIMENSION_ORDER,
    J_HEADERS,
    SEPARATOR,
    format_change_pct,
)


def _title_line(meta: dict) -> str:
    name = meta["name"]
    code = meta["code"]
    price = meta["price"]
    change = format_change_pct(meta["change_pct"])
    ctx = meta["title_context"]
    data_as_of = meta["data_as_of"]

    if meta["quote_mode"] == "intraday":
        # e.g. "2026-05-15 13:23 盘中"
        return f"{data_as_of} 盘中 {price} 元，今日 {change}%（{ctx}）"

    # close: e.g. "2026-05-15 收盘"
    if "收盘" in data_as_of:
        date_part = data_as_of.replace(" 收盘", "").strip()
        return f"{date_part} 收盘 {price} 元，今日 {change}%（{ctx}）"

    return f"{data_as_of} 收盘 {price} 元，今日 {change}%（{ctx}）"


def _format_dimension(dim: str, block: dict) -> str:
    lines = [f"【{dim}】", f"结论：{block['conclusion']}"]
    bullets = block.get("data_bullets") or []
    if block["role"] == "secondary":
        lines.append("数据：· 无核心异动。")
    elif len(bullets) == 1:
        lines.append(f"数据：· {bullets[0]}")
    else:
        lines.append("数据：")
        for bullet in bullets:
            lines.append(f"· {bullet}")
    lines.append(f"解读：{block['interpretation']}")
    return "\n".join(lines)


def format_im(bundle: dict) -> str:
    meta = bundle["meta"]
    narrative = bundle["narrative"]
    j = bundle["judgments_j"]
    prov = bundle["provenance"]

    parts: list[str] = [
        f"{meta['name']}（{meta['code']}）个股诊断",
        _title_line(meta),
        "",
        "【总结前瞻】",
        narrative["summary_hook"],
        "",
        SEPARATOR,
        "",
        "【今天告诉客户什么】",
        narrative["client_brief"],
        "",
        SEPARATOR,
        "",
    ]

    dim_sections = [_format_dimension(dim, narrative["dimensions"][dim]) for dim in DIMENSION_ORDER]
    parts.append("\n\n".join(dim_sections))
    parts.extend(["", SEPARATOR, ""])

    j3_line = f"{j['j3']}（{j['j3_consensus']} — 与昨日相比）。"
    j_lines = [
        f"{J_HEADERS['j1']} ▎{j['j1']}",
        f"{J_HEADERS['j2']} ▎{j['j2']}",
        f"{J_HEADERS['j3']} ▎{j3_line}",
        f"{J_HEADERS['j4']} ▎{j['j4']}",
        f"{J_HEADERS['j5']} ▎{j['j5']}",
    ]
    parts.append("\n".join(j_lines))
    parts.extend(["", SEPARATOR, "", f"数据备注：{prov['data_notes']}", "", prov["disclaimer"]])
    return "\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Format IM text from diagnosis bundle")
    parser.add_argument("bundle", type=Path, help="Path to *.bundle.json")
    parser.add_argument("-o", "--output", type=Path, help="Write IM text to file (default: stdout)")
    args = parser.parse_args()

    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read bundle: {exc}", file=sys.stderr)
        return 2

    im_text = format_im(bundle)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(im_text, encoding="utf-8")
        print(str(args.output))
    else:
        sys.stdout.write(im_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
