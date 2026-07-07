#!/usr/bin/env python3
"""Sanitize raw local CLI stream captures into committed fixture files.

Raw captures live under `.tmp/raw_runtime_streams/` (gitignored).
Sanitized fixtures go to `tests/fixtures/runtime_streams/`.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REDACTED_PATH = "/REDACTED/path"
REDACTED_USER = "REDACTED_USER"
REDACTED_TOKEN = "REDACTED_TOKEN"

_WIN_ABS = re.compile(r"[A-Za-z]:\\[^\s\"']+")
_UNIX_ABS = re.compile(r"(?<![\w./])(?:/Users|/home|/tmp|/var)[^\s\"']+")
_TOKEN_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.I),
    re.compile(r"api[_-]?key[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9._-]{8,}", re.I),
]
_USER_IN_PATH = re.compile(r"(?:/Users/|/home/|\\\\Users\\\\)([^/\\]+)")


def _redact_text(value: str, *, max_len: int = 240) -> str:
    text = value
    text = _WIN_ABS.sub(REDACTED_PATH, text)
    text = _UNIX_ABS.sub(REDACTED_PATH, text)
    text = _USER_IN_PATH.sub(lambda m: m.group(0).replace(m.group(1), REDACTED_USER), text)
    for pattern in _TOKEN_PATTERNS:
        text = pattern.sub(REDACTED_TOKEN, text)
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def _sanitize_json_obj(obj: object) -> object:
    if isinstance(obj, dict):
        out: dict[str, object] = {}
        for key, value in obj.items():
            if key in {"prompt", "system", "instructions", "content"} and isinstance(value, str):
                out[key] = _redact_text(value, max_len=120)
            else:
                out[key] = _sanitize_json_obj(value)
        return out
    if isinstance(obj, list):
        return [_sanitize_json_obj(item) for item in obj]
    if isinstance(obj, str):
        return _redact_text(obj)
    return obj


def sanitize_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return _redact_text(stripped)
    sanitized = _sanitize_json_obj(payload)
    return json.dumps(sanitized, ensure_ascii=False)


def sanitize_text(text: str) -> str:
    lines = text.splitlines()
    return "\n".join(sanitize_line(line) for line in lines if sanitize_line(line))


def sanitize_file(input_path: Path, output_path: Path) -> None:
    raw = input_path.read_text(encoding="utf-8", errors="replace")
    cleaned = sanitize_text(raw)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(cleaned + ("\n" if cleaned and not cleaned.endswith("\n") else ""), encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sanitize raw runtime stream capture into fixture file.")
    parser.add_argument("input", type=Path, help="Raw capture under .tmp/raw_runtime_streams/")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output fixture path (default: tests/fixtures/runtime_streams/<input_stem>_fixture.jsonl)",
    )
    args = parser.parse_args()
    output = args.output or Path("tests/fixtures/runtime_streams") / f"{args.input.stem}_fixture.jsonl"
    sanitize_file(args.input, output)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
