#!/usr/bin/env python3
"""Validate diagnosis bundle: JSON Schema + attention matrix + V5.1 narrative rules."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

from bundle_common import (
    BANNED_EVOLUTION_WORDS,
    DIMENSION_ORDER,
    SCHEMA_PATH,
    STATE_CORE_MATRIX,
    TECHNICAL_PRICE_BANNED,
    THEME_WORD_LIMITS,
    TRADING_BANNED_PHRASES,
    all_dimension_keys,
    collect_narrative_text,
    expected_core_dimensions,
)


def _longest_common_substring_len(a: str, b: str, min_len: int = 4) -> list[str]:
    matches: list[str] = []
    for i in range(len(a)):
        for j in range(len(b)):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            if k >= min_len:
                matches.append(a[i : i + k])
    return matches


def validate_schema(bundle: dict) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(bundle), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.path) or "(root)"
        errors.append(f"schema: {path}: {err.message}")
    return errors


def validate_matrix(bundle: dict) -> list[str]:
    errors: list[str] = []
    judgment = bundle["judgment"]
    state = judgment["state_primary"]
    core = judgment["core_dimensions"]
    secondary = judgment["secondary_dimensions"]
    expected = expected_core_dimensions(state)

    if sorted(core) != sorted(expected):
        errors.append(
            f"matrix: core_dimensions {core!r} != expected {expected!r} for state {state!r}"
        )

    union = set(core) | set(secondary)
    if union != all_dimension_keys():
        errors.append(
            f"matrix: core+secondary must cover all 6 dimensions; got {sorted(union)!r}"
        )
    if set(core) & set(secondary):
        errors.append("matrix: core_dimensions and secondary_dimensions overlap")

    dims = bundle["narrative"]["dimensions"]
    for dim in core:
        if dims[dim]["role"] != "core":
            errors.append(f"matrix: {dim} is core but role={dims[dim]['role']!r}")

    tech_evo = judgment["technical_evolution"]
    tech_role = dims["技术面"]["role"]
    if tech_evo:
        if tech_role not in ("core", "secondary_technical"):
            errors.append(
                "matrix: technical_evolution=true requires 技术面 role core or secondary_technical"
            )
        if "技术面" in core and tech_role != "core":
            errors.append("matrix: 技术面 in core_dimensions must have role=core")
    elif dims["技术面"]["role"] == "secondary_technical":
        errors.append("matrix: secondary_technical 技术面 requires technical_evolution=true")

    for dim in secondary:
        block = dims[dim]
        if dim == "技术面" and tech_evo:
            continue
        if block["role"] != "secondary":
            errors.append(f"matrix: {dim} is secondary but role={block['role']!r}")

    if state not in STATE_CORE_MATRIX:
        errors.append(f"matrix: unknown state_primary {state!r}")

    return errors


def _collect_html_expanded_text(block: dict) -> str:
    expanded = block.get("html_expanded") or {}
    parts = [
        expanded.get("conclusion", ""),
        expanded.get("interpretation", ""),
        *(expanded.get("data_bullets") or []),
    ]
    return "\n".join(p for p in parts if p)


def validate_html_expanded(bundle: dict) -> list[str]:
    errors: list[str] = []
    dims = bundle["narrative"]["dimensions"]

    for dim in DIMENSION_ORDER:
        block = dims[dim]
        role = block["role"]
        expanded = block.get("html_expanded")

        if role == "secondary":
            if not expanded:
                errors.append(f"html_expanded: {dim} role=secondary requires html_expanded")
                continue
            text = _collect_html_expanded_text(block)
            for phrase in TRADING_BANNED_PHRASES:
                if phrase in text:
                    errors.append(
                        f"html_expanded: {dim} contains banned trading phrase {phrase!r}"
                    )
            if dim == "技术面":
                for phrase in TECHNICAL_PRICE_BANNED:
                    if phrase in text:
                        errors.append(
                            f"html_expanded: 技术面 contains banned price term {phrase!r}"
                        )
        elif expanded is not None:
            errors.append(f"html_expanded: {dim} role={role!r} must not include html_expanded")

    return errors


J5_RISK_CATEGORIES = [
    "估值风险",
    "主线切换风险",
    "商誉应收风险",
    "股东减持解禁",
    "流动性风险",
    "合规风险",
    "政策反转风险",
    "个股专属风险",
]


SUMMARY_RISK_MARKERS = ("核心风险加剧", "核心风险缓和", "核心风险持平")


def validate_summary_hook_display(bundle: dict) -> list[str]:
    errors: list[str] = []
    display = (bundle.get("narrative") or {}).get("summary_hook_display")
    if not display:
        return errors
    for marker in SUMMARY_RISK_MARKERS:
        if marker in display:
            errors.append(
                f"summary_hook_display: must not contain IM risk marker {marker!r}; "
                "use judgments_j.j5 in HTML J5 row instead"
            )
    summary = bundle["narrative"]["summary_hook"]
    if display == summary:
        errors.append(
            "summary_hook_display: should omit core risk clause and differ from summary_hook"
        )
    return errors


def validate_judgments_j_expanded(bundle: dict) -> list[str]:
    errors: list[str] = []
    expanded_root = bundle.get("judgments_j_expanded")
    if not expanded_root:
        return errors

    for key in ("j1", "j2", "j3", "j4"):
        block = expanded_root.get(key)
        if not block:
            errors.append(f"judgments_j_expanded: missing {key}")
            continue
        headline = block.get("headline", "")
        if len(headline) < 4 or len(headline) > 24:
            errors.append(f"judgments_j_expanded: {key}.headline length must be 4–24 chars")
        text = "\n".join(
            part
            for part in [
                block.get("conclusion", ""),
                block.get("key_rhythm", ""),
                block.get("footnote", ""),
                * (block.get("counter_examples") or []),
            ]
            if part
        )
        for phrase in TRADING_BANNED_PHRASES:
            if phrase in text:
                errors.append(
                    f"judgments_j_expanded: {key} contains banned trading phrase {phrase!r}"
                )

    j5 = expanded_root.get("j5")
    if not j5:
        errors.append("judgments_j_expanded: missing j5")
    elif not j5.get("risks"):
        errors.append("judgments_j_expanded: j5.risks must be non-empty")
    else:
        for idx, risk in enumerate(j5["risks"]):
            cat = risk.get("category")
            if cat not in J5_RISK_CATEGORIES:
                errors.append(f"judgments_j_expanded: j5.risks[{idx}] invalid category {cat!r}")

    return errors


def validate_narrative_rules(bundle: dict) -> list[str]:
    errors: list[str] = []
    summary = bundle["narrative"]["summary_hook"]
    client = bundle["narrative"]["client_brief"]
    dupes = _longest_common_substring_len(summary, client, min_len=4)
    if dupes:
        errors.append(
            f"narrative: summary_hook and client_brief share phrase(s) >=4 chars: {dupes[:3]!r}"
        )

    text = collect_narrative_text(bundle)
    for word in BANNED_EVOLUTION_WORDS:
        if word in text:
            errors.append(f"narrative: banned evolution word {word!r} in narrative/judgments")

    for phrase in TRADING_BANNED_PHRASES:
        if phrase in text:
            errors.append(f"narrative: banned trading phrase {phrase!r}")

    for theme, limit in THEME_WORD_LIMITS.items():
        count = text.count(theme)
        if count > limit:
            errors.append(f"narrative: theme word {theme!r} appears {count} times (max {limit})")

    j1 = bundle["judgments_j"]["j1"]
    if "详见上方【" not in j1:
        errors.append("narrative: j1 must contain 详见上方【")
    for dim in bundle["judgment"]["core_dimensions"]:
        if f"【{dim}】" not in j1:
            errors.append(f"narrative: j1 must reference core dimension 【{dim}】")

    if "➔" in summary or "➔" in bundle["judgment"].get("state_evolution", ""):
        notes = bundle["provenance"]["data_notes"]
        for banned in ("暂无法对比昨日", "首次诊断无昨日对比基准"):
            if banned in notes:
                errors.append(f"narrative: data_notes must not contain {banned!r} when evolution present")

    return errors


def warn_benchmark_sector(bundle: dict) -> list[str]:
    warnings: list[str] = []
    benchmark = (bundle.get("meta") or {}).get("benchmark_sector") or {}
    name = (benchmark.get("name") or "").strip()
    if not name:
        return warnings
    if len(name) <= 3 or name == "机器人":
        warnings.append(
            f"warn: meta.benchmark_sector.name={name!r} is ambiguous; "
            "prefer EM full name (e.g. 人形机器人, 机器人概念) and index_code when known"
        )
    return warnings


def validate_bundle(bundle: dict) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_schema(bundle))
    if not any(e.startswith("schema:") for e in errors):
        errors.extend(validate_matrix(bundle))
        errors.extend(validate_narrative_rules(bundle))
        errors.extend(validate_html_expanded(bundle))
        errors.extend(validate_judgments_j_expanded(bundle))
        errors.extend(validate_summary_hook_display(bundle))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate stock-radar diagnosis bundle JSON")
    parser.add_argument("bundle", type=Path, help="Path to *.bundle.json")
    parser.add_argument("--json", action="store_true", help="Emit errors as JSON array")
    args = parser.parse_args()

    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read bundle: {exc}", file=sys.stderr)
        return 2

    errors = validate_bundle(bundle)
    warnings = warn_benchmark_sector(bundle)
    for warn in warnings:
        print(f"WARN: {warn}", file=sys.stderr)
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    elif errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
    else:
        print(f"OK: {args.bundle}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
