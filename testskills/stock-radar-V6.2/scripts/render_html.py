#!/usr/bin/env python3
"""Render single-file HTML diagnosis view from assembled diagnosis bundle."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from bundle_common import (
    DEFAULT_OUTPUT_DIR,
    DIMENSION_ORDER,
    J_HEADERS,
    compute_radar_weights,
    format_change_pct,
)
from fetch_html_common import unavailable_fetch_html

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = SKILL_ROOT / "templates"
TEMPLATE_NAME = "radar_view.html.j2"

ANNOTATION_LABELS = {
    "ma_alignment": {
        "bullish_stack": "多头排列",
        "bearish_stack": "空头排列",
        "mixed": "均线交织",
    },
    "trend_strength": {
        "upward": "趋势向上",
        "downward": "趋势向下",
        "sideways": "横盘整理",
    },
    "volume_vs_20d": {
        "elevated": "量能放大",
        "normal": "量能正常",
        "subdued": "量能萎缩",
    },
}

DIM_CHART_IDS = {
    "技术面": "kline-chart-technical",
    "资金面": "fund-chart-fund",
    "资金面板块": "fund-chart-sector",
}

J_CARD_LABELS = {
    "j1": "J1 · 主驱动",
    "j2": "J2 · 窗口",
    "j3": "J3 · 阶段",
    "j4": "J4 · 板块",
    "j5": "J5 · 风险",
}

STATE_BADGE_VARIANT = {
    "个股异动态": "alert",
    "板块共振态": "sector",
    "活跃热点态": "hot",
    "阶段切换态": "shift",
    "平静无驱动态": "calm",
}

RISK_TONE_LABELS = {"加剧": "风险加剧", "缓和": "风险缓和", "持平": "风险持平"}

# HTML cockpit · J row priority dots (Claude mockup)
J_DOT_KIND = {
    "j1": "focus",
    "j2": "secondary",
    "j3": "normal",
    "j4": "normal",
    "j5": "focus",
}

J_PRIORITY_LABEL = {
    "j1": "重点关注",
    "j2": "次要",
}


def _build_radar_insight(bundle: dict, radar_weights: dict[str, int]) -> str:
    judgment = bundle["judgment"]
    state = judgment["state_primary"]
    core_dims = list(judgment.get("core_dimensions") or [])
    core_sorted = sorted(core_dims, key=lambda d: (-radar_weights.get(d, 0), DIMENSION_ORDER.index(d)))

    focal = next((dim for dim in DIMENSION_ORDER if dim not in set(core_dims)), "基本面")
    core_text = "】【".join(core_sorted)
    insight = f"雷达洞察：当前属【{state}】，【{core_text}】主导定价；【{focal}】暂非博弈焦点。"

    tech_block = bundle["narrative"]["dimensions"]["技术面"]
    if judgment.get("technical_evolution") and tech_block.get("role") == "secondary_technical":
        insight += "技术面处于临界观察。"
    return insight


def _title_line(meta: dict) -> str:
    price = meta["price"]
    change = format_change_pct(meta["change_pct"])
    ctx = meta["title_context"]
    data_as_of = meta["data_as_of"]

    if meta["quote_mode"] == "intraday":
        return f"{data_as_of} 盘中 {price} 元，今日 {change}%（{ctx}）"

    if "收盘" in data_as_of:
        date_part = data_as_of.replace(" 收盘", "").strip()
        return f"{date_part} 收盘 {price} 元，今日 {change}%（{ctx}）"

    return f"{data_as_of} 收盘 {price} 元，今日 {change}%（{ctx}）"


def _ensure_fetch_html(bundle: dict) -> dict:
    fetch_html = bundle.get("fetch_html")
    if fetch_html:
        return fetch_html
    code = bundle["meta"]["code"]
    return unavailable_fetch_html(code, reason_code="FETCH_FAILED", reason="fetch_html missing from bundle")


def _format_annotations(annotations: dict | None) -> list[dict[str, str]]:
    if not annotations:
        return []
    rows: list[dict[str, str]] = []

    ma = ANNOTATION_LABELS["ma_alignment"].get(annotations.get("ma_alignment", ""), "—")
    trend = ANNOTATION_LABELS["trend_strength"].get(annotations.get("trend_strength", ""), "—")
    vol = ANNOTATION_LABELS["volume_vs_20d"].get(annotations.get("volume_vs_20d", ""), "—")
    rows.extend(
        [
            {"label": "均线结构", "value": ma},
            {"label": "趋势强度", "value": trend},
            {"label": "相对 20 日量能", "value": vol},
        ]
    )

    if annotations.get("breakout_60d_high"):
        rows.append({"label": "60 日突破", "value": "创 60 日新高"})
    elif annotations.get("broke_60d_low"):
        rows.append({"label": "60 日突破", "value": "创 60 日新低"})
    else:
        near_high = annotations.get("near_60d_high_pct")
        near_low = annotations.get("near_60d_low_pct")
        if near_high is not None:
            rows.append({"label": "距 60 日高点", "value": f"{near_high:+.1f}%"})
        if near_low is not None:
            rows.append({"label": "距 60 日低点", "value": f"{near_low:+.1f}%"})

    rows.append({"label": "20 日涨跌", "value": f"{annotations.get('change_20d_pct', 0):+.1f}%"})
    rows.append({"label": "60 日涨跌", "value": f"{annotations.get('change_60d_pct', 0):+.1f}%"})
    return rows


def _signal_badge_technical(annotations: dict | None) -> str | None:
    if not annotations:
        return None
    signals: list[str] = []
    if annotations.get("broke_60d_low"):
        signals.append("60日新低")
    elif annotations.get("breakout_60d_high"):
        signals.append("60日新高")

    vol = annotations.get("volume_vs_20d")
    if vol == "elevated":
        signals.append("量能放大")
    elif vol == "subdued":
        signals.append("量能萎缩")

    ma = annotations.get("ma_alignment")
    if ma == "mixed":
        signals.append("均线交织")
    elif ma == "bullish_stack":
        signals.append("多头排列")
    elif ma == "bearish_stack":
        signals.append("空头排列")

    trend = annotations.get("trend_strength")
    if trend == "upward" and "趋势向上" not in signals:
        signals.append("趋势向上")
    elif trend == "downward" and "趋势向下" not in signals:
        signals.append("趋势向下")

    return " · ".join(signals[:3]) if signals else None


def _signal_badge_fund(fund_flow: dict) -> str | None:
    if fund_flow.get("status") not in ("ok", "stale"):
        return None
    series = fund_flow.get("series") or []
    if not series:
        return None
    total_yi = sum(row["main_net_inflow"] for row in series) / 1e8
    sign = "+" if total_yi >= 0 else ""
    badge = f"近5日主力 {sign}{total_yi:.1f}亿"
    if fund_flow["status"] == "stale":
        badge += " · 滞后"
    return badge


def _last_numeric(values: list) -> float | None:
    for value in reversed(values or []):
        if value is not None:
            return float(value)
    return None


def _format_signed_pct(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def _build_kline_snapshot(meta: dict, payload: dict) -> dict:
    last_close = None
    if payload.get("ohlc"):
        last_close = payload["ohlc"][-1][1]
    if last_close is None:
        last_close = meta.get("price")

    change_pct = meta.get("change_pct")
    stock_change = format_change_pct(change_pct) if change_pct is not None else "—"

    stock_pct_60 = _last_numeric(payload.get("overlay_stock_pct"))
    sh_pct_60 = _last_numeric(payload.get("overlay_sh_pct"))
    sector_pct_60 = _last_numeric(payload.get("overlay_sector_pct"))

    sector_label = payload["overlay_labels"]["sector"]
    sh_label = payload["overlay_labels"]["sh"]

    return {
        "absolute_line": (
            f"最新价: {last_close} 元 ({stock_change}%)"
            f" | {sh_label}: {_format_signed_pct(sh_pct_60)}"
            f" | {sector_label}: {_format_signed_pct(sector_pct_60)}"
        ),
        "percentage_line": (
            f"60日累计: 个股 {_format_signed_pct(stock_pct_60)}"
            f" | {sh_label} {_format_signed_pct(sh_pct_60)}"
            f" | {sector_label} {_format_signed_pct(sector_pct_60)}"
        ),
        "compare_caption": (
            f"对比：{meta['name']}（{meta['code']}）· {sh_label}"
            f" · {sector_label}"
        ),
    }


def _sector_fund_chart_label(benchmark_sector: dict | None, block: dict) -> str:
    name = block.get("matched_name") or block.get("sector_name")
    if not name and benchmark_sector:
        name = benchmark_sector.get("name")
    return name or "关联板块"


def _sector_fund_match_note(block: dict) -> str | None:
    requested = (block.get("requested_name") or block.get("sector_name") or "").strip()
    matched = (block.get("matched_name") or "").strip()
    if requested and matched and requested != matched:
        return f"已匹配：{matched}"
    return None


def _append_fund_series(payload: dict, prefix: str, block: dict) -> None:
    dates_key = f"{prefix}_dates"
    values_key = f"{prefix}_values"
    colors_key = f"{prefix}_colors"
    payload[dates_key] = []
    payload[values_key] = []
    payload[colors_key] = []
    if block.get("status") not in ("ok", "stale"):
        return
    for row in block.get("series") or []:
        payload[dates_key].append(row["date"])
        val = row["main_net_inflow"] / 1e8
        payload[values_key].append(round(val, 2))
        payload[colors_key].append("#16a34a" if row["is_net_in"] else "#dc2626")


def _sanitize_display_reason(reason: str | None, fallback: str = "接口暂时不可用") -> str:
    text = str(reason or "").strip()
    if not text:
        return fallback
    lowered = text.lower()
    if "connection aborted" in lowered or "remotedisconnected" in lowered or "timeout" in lowered:
        return "数据源连接中断，请稍后重试"
    if "未匹配" in text or "未配置" in text:
        return text
    if "连接中断" in text or "接口连接中断" in text or "代理阻断" in text:
        return text
    if len(text) > 80 or text.startswith("("):
        return fallback
    return text


def _build_chart_payload(
    fetch_html: dict,
    benchmark_sector: dict | None = None,
    meta: dict | None = None,
) -> dict:
    kline = fetch_html["kline"]
    ma = fetch_html["ma_overlay"]
    fund = fetch_html["fund_flow"]
    sector_fund = fetch_html.get("benchmark_sector_fund_flow") or {
        "status": "placeholder",
        "reason": "benchmark_sector_fund_flow missing",
        "series": [],
    }
    overlays = fetch_html.get("overlays") or {}

    payload: dict = {
        "kline_status": kline["status"],
        "kline_reason": kline.get("reason"),
        "kline_partial_note": None,
        "fund_status": fund["status"],
        "fund_reason": _sanitize_display_reason(fund.get("reason"), "个股资金流接口不可用"),
        "fund_stale_note": None,
        "dates": [],
        "ohlc": [],
        "ma5": [],
        "ma20": [],
        "ma60": [],
        "fund_dates": [],
        "fund_values": [],
        "fund_colors": [],
        "kline_chart_id": DIM_CHART_IDS["技术面"],
        "fund_chart_id": DIM_CHART_IDS["资金面"],
        "fund_sector_chart_id": DIM_CHART_IDS["资金面板块"],
        "sector_fund_status": sector_fund.get("status", "placeholder"),
        "sector_fund_reason": _sanitize_display_reason(sector_fund.get("reason"), "板块资金流数据缺失"),
        "sector_fund_label": _sector_fund_chart_label(benchmark_sector, sector_fund),
        "sector_fund_match_note": _sector_fund_match_note(sector_fund),
        "sector_fund_stale_note": None,
        "sector_fund_dates": [],
        "sector_fund_values": [],
        "sector_fund_colors": [],
        "overlay_status": overlays.get("status", "unavailable"),
        "overlay_reason": overlays.get("reason"),
        "overlay_stock_pct": [],
        "overlay_sh_pct": [],
        "overlay_sector_pct": [],
        "overlay_labels": {
            "stock": "个股",
            "sh": overlays.get("sh_index", {}).get("name") or "上证指数",
            "sector": (
                (benchmark_sector or {}).get("name")
                or overlays.get("sector", {}).get("name")
                or "板块"
            ),
        },
        "overlay_show_sector": False,
        "overlay_stale_note": None,
    }

    if kline["status"] == "partial":
        payload["kline_partial_note"] = (
            f"仅 {kline['bars_available']} 根 K 线（目标 {kline['bars_requested']} 根）"
        )

    if kline["status"] in ("ok", "partial") and kline.get("series"):
        series = kline["series"]
        payload["dates"] = [bar["date"] for bar in series]
        payload["ohlc"] = [[bar["open"], bar["close"], bar["low"], bar["high"]] for bar in series]
        payload["ma5"] = ma.get("ma5", [])
        payload["ma20"] = ma.get("ma20", [])
        payload["ma60"] = ma.get("ma60", [])

    if overlays.get("status") in ("ok", "partial") and overlays.get("stock_pct"):
        payload["overlay_stock_pct"] = overlays.get("stock_pct") or []
        sh_block = overlays.get("sh_index") or {}
        if sh_block.get("status") == "ok":
            payload["overlay_sh_pct"] = sh_block.get("pct") or []
        sector_block = overlays.get("sector") or {}
        if sector_block.get("status") == "ok" and sector_block.get("pct"):
            payload["overlay_sector_pct"] = sector_block.get("pct") or []
            payload["overlay_show_sector"] = True
            payload["overlay_stale_note"] = overlays.get("overlay_stale_note")
        elif overlays.get("status") == "partial":
            payload["overlay_show_sector"] = False
            payload["overlay_sector_pct"] = []

    if fund["status"] == "stale":
        lag = fund.get("lag_trading_days")
        ref = fund.get("reference_date") or "—"
        payload["fund_stale_note"] = f"资金流数据滞后 {lag} 个交易日（参考日 {ref}）"

    if sector_fund.get("status") == "stale":
        lag = sector_fund.get("lag_trading_days")
        ref = sector_fund.get("reference_date") or "—"
        payload["sector_fund_stale_note"] = f"板块资金流数据滞后 {lag} 个交易日（参考日 {ref}）"

    _append_fund_series(payload, "fund", fund)
    _append_fund_series(payload, "sector_fund", sector_fund)

    if meta:
        payload["kline_snapshot"] = _build_kline_snapshot(meta, payload)
    else:
        payload["kline_snapshot"] = {
            "absolute_line": "",
            "percentage_line": "",
            "compare_caption": "",
        }

    return payload


def _sort_dimensions(items: list[dict], radar_weights: dict[str, int]) -> list[dict]:
    core = [d for d in items if d["is_core"]]
    secondary_tech = [d for d in items if not d["is_core"] and d["role"] == "secondary_technical"]
    rest = [d for d in items if not d["is_core"] and d["role"] != "secondary_technical"]

    core.sort(key=lambda d: (-radar_weights.get(d["key"], 0), DIMENSION_ORDER.index(d["key"])))
    rest.sort(key=lambda d: DIMENSION_ORDER.index(d["key"]))
    return core + secondary_tech + rest


def _dimension_display_layers(block: dict) -> dict[str, object]:
    """Map bundle dimension block → tier-2 (conclusion/data) + tier-3 (interpretation)."""
    expanded = block.get("html_expanded")
    if expanded:
        return {
            "stub_conclusion": block["conclusion"],
            "conclusion": expanded["conclusion"],
            "data_bullets": expanded.get("data_bullets") or [],
            "interpretation": expanded["interpretation"],
            "uses_expanded": True,
        }
    return {
        "stub_conclusion": None,
        "conclusion": block["conclusion"],
        "data_bullets": block.get("data_bullets") or [],
        "interpretation": block["interpretation"],
        "uses_expanded": False,
    }


def _build_dimensions(bundle: dict, fetch_html: dict, radar_weights: dict[str, int]) -> list[dict]:
    core_dims = set(bundle["judgment"]["core_dimensions"])
    narrative = bundle["narrative"]["dimensions"]
    annotations = fetch_html.get("annotations")
    fund_flow = fetch_html["fund_flow"]
    tech_signal = _signal_badge_technical(annotations)
    fund_signal = _signal_badge_fund(fund_flow)
    annotation_rows = _format_annotations(annotations)

    items: list[dict] = []
    for dim in DIMENSION_ORDER:
        block = narrative[dim]
        role = block["role"]
        is_core = dim in core_dims or role == "core"
        layers = _dimension_display_layers(block)

        signal_badge = None
        if dim == "技术面":
            signal_badge = tech_signal
        elif dim == "资金面":
            signal_badge = fund_signal

        dot_kind = None
        if is_core:
            dot_kind = "core"
        elif role == "secondary_technical":
            dot_kind = "critical"

        items.append(
            {
                "key": dim,
                "role": role,
                "is_core": is_core,
                "dot_kind": dot_kind,
                "stub_conclusion": layers["stub_conclusion"],
                "conclusion": layers["conclusion"],
                "data_bullets": layers["data_bullets"],
                "interpretation": layers["interpretation"],
                "uses_expanded": layers["uses_expanded"],
                "badge": "核心" if is_core else ("临界" if role == "secondary_technical" else "次要"),
                "signal_badge": signal_badge,
                "show_technical_chart": dim == "技术面",
                "show_fund_chart": dim == "资金面",
                "chart_id": DIM_CHART_IDS.get(dim),
                "annotation_rows": annotation_rows if dim == "技术面" else [],
            }
        )
    return _sort_dimensions(items, radar_weights)


def _build_summary_display(bundle: dict) -> str:
    narrative = bundle["narrative"]
    display = (narrative.get("summary_hook_display") or "").strip()
    if display:
        return display
    return narrative["summary_hook"].strip()


def _state_badge_variant(bundle: dict) -> str:
    state = bundle["judgment"].get("state_primary", "")
    return STATE_BADGE_VARIANT.get(state, "calm")


def _risk_tone_label(bundle: dict) -> str:
    tone = bundle["judgment"].get("risk_tone", "")
    return RISK_TONE_LABELS.get(tone, f"风险{tone}" if tone else "风险")


def _build_j_items(bundle: dict) -> list[dict]:
    j = bundle["judgments_j"]
    expanded_root = bundle.get("judgments_j_expanded") or {}
    j3_subtitle = f"{j['j3_consensus']} — 与昨日相比"
    risk_tone_label = _risk_tone_label(bundle)

    items: list[dict] = []
    for key in ("j1", "j2", "j3", "j4", "j5"):
        im_line = (j[key] or "").strip()
        expanded = expanded_root.get(key)
        is_j5 = key == "j5"

        if is_j5:
            risks = (expanded or {}).get("risks") or []
            headline = ((expanded or {}).get("headline") or im_line).strip()
            items.append(
                {
                    "key": key,
                    "short_label": J_CARD_LABELS[key],
                    "full_header": J_HEADERS[key],
                    "headline": headline,
                    "subtitle": None,
                    "is_j5": True,
                    "dot_kind": J_DOT_KIND[key],
                    "priority_label": None,
                    "risk_tone_label": risk_tone_label,
                    "conclusion": (expanded or {}).get("conclusion"),
                    "counter_examples": [],
                    "key_rhythm": None,
                    "footnote": None,
                    "risks": risks,
                    "legacy_fallback": not expanded,
                    "fallback_text": im_line,
                    "has_expand": bool(risks or (expanded or {}).get("conclusion") or not expanded),
                }
            )
            continue

        headline = ((expanded or {}).get("headline") if expanded else None) or im_line
        items.append(
            {
                "key": key,
                "short_label": J_CARD_LABELS[key],
                "full_header": J_HEADERS[key],
                "headline": headline.strip(),
                "subtitle": j3_subtitle if key == "j3" else None,
                "is_j5": False,
                "dot_kind": J_DOT_KIND[key],
                "priority_label": J_PRIORITY_LABEL.get(key),
                "risk_tone_label": None,
                "conclusion": (expanded or {}).get("conclusion") if expanded else None,
                "counter_examples": (expanded or {}).get("counter_examples") or [] if expanded else [],
                "key_rhythm": (expanded or {}).get("key_rhythm") if expanded else None,
                "footnote": (expanded or {}).get("footnote") if expanded else None,
                "risks": [],
                "legacy_fallback": expanded is None,
                "fallback_text": im_line,
                "has_expand": True,
            }
        )
    return items


def _client_brief_display(brief: str) -> dict[str, str]:
    text = (brief or "").strip()
    return {"full": text}


def build_context(bundle: dict) -> dict:
    meta = bundle["meta"]
    judgment = bundle["judgment"]
    j = bundle["judgments_j"]
    fetch_html = _ensure_fetch_html(bundle)
    radar_weights = compute_radar_weights(bundle)

    return {
        "meta": meta,
        "title_line": _title_line(meta),
        "judgment": judgment,
        "narrative": bundle["narrative"],
        "summary_display": _build_summary_display(bundle),
        "state_badge_variant": _state_badge_variant(bundle),
        "judgments_j": j,
        "j_items": _build_j_items(bundle),
        "client_brief": _client_brief_display(bundle["narrative"]["client_brief"]),
        "j_headers": J_HEADERS,
        "provenance": bundle["provenance"],
        "radar_weights": radar_weights,
        "radar_series": [radar_weights[dim] for dim in DIMENSION_ORDER],
        "radar_labels": list(DIMENSION_ORDER),
        "radar_insight": _build_radar_insight(bundle, radar_weights),
        "dimensions": _build_dimensions(bundle, fetch_html, radar_weights),
        "fetch_html": fetch_html,
        "chart_payload": _build_chart_payload(
            fetch_html,
            bundle.get("meta", {}).get("benchmark_sector"),
            meta=meta,
        ),
        "rendered_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }


def render_html(bundle: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(TEMPLATE_NAME)
    return template.render(**build_context(bundle))


def main() -> int:
    parser = argparse.ArgumentParser(description="Render stock-radar HTML from assembled bundle")
    parser.add_argument("bundle", type=Path, help="Assembled *.assembled.bundle.json")
    parser.add_argument("-o", "--output", type=Path, help="Output HTML path")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Default output directory when -o omitted",
    )
    args = parser.parse_args()

    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read bundle: {exc}", file=sys.stderr)
        return 2

    if "fetch" not in bundle and "fetch_html" not in bundle:
        print("WARN: bundle looks unassembled (no fetch/fetch_html); rendering with placeholders", file=sys.stderr)

    try:
        html = render_html(bundle)
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"ERROR: render failed: {exc}", file=sys.stderr)
        return 1

    code = bundle["meta"]["code"]
    if args.output:
        out_path = args.output
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = args.output_dir / code
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{ts}.html"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
