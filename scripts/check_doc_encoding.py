"""UTF-8 / mojibake guard for Chinese Markdown (RECORD, .project_memory, docs, openspec)."""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

UTF8_BOM = b"\xef\xbb\xbf"

# Substrings typical of UTF-8 misread as GBK then saved again (double encoding).
MOJIBAKE_SUBSTRINGS: tuple[str, ...] = (
    "鎬昏处",
    "浠诲姟鐩",
    "褰撳墠鐘",
    "璇勪及绯",
)

PRIVATE_USE_MAX = 5


@dataclass(frozen=True)
class EncodingIssue:
    path: str
    code: str
    message: str


def check_bytes(raw: bytes, *, path: str = "<string>", record_anchor: bool = False) -> list[EncodingIssue]:
    issues: list[EncodingIssue] = []
    if raw.startswith(UTF8_BOM):
        issues.append(
            EncodingIssue(path, "utf8_bom", "file starts with UTF-8 BOM (use UTF-8 without BOM)")
        )
        raw = raw[len(UTF8_BOM) :]

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        issues.append(EncodingIssue(path, "invalid_utf8", f"not valid UTF-8: {exc}"))
        return issues

    issues.extend(check_decoded_text(text, path=path, record_anchor=record_anchor))
    return issues


def check_decoded_text(text: str, *, path: str = "<string>", record_anchor: bool = False) -> list[EncodingIssue]:
    issues: list[EncodingIssue] = []

    for needle in MOJIBAKE_SUBSTRINGS:
        if needle in text:
            issues.append(
                EncodingIssue(
                    path,
                    "mojibake_substring",
                    f"contains mojibake fingerprint {needle!r}",
                )
            )
            break

    priv = sum(1 for ch in text if 0xE000 <= ord(ch) <= 0xF8FF)
    if priv > PRIVATE_USE_MAX:
        issues.append(
            EncodingIssue(
                path,
                "private_use_chars",
                f"too many private-use characters ({priv} > {PRIVATE_USE_MAX})",
            )
        )

    if record_anchor and "总账文档" not in text:
        issues.append(
            EncodingIssue(path, "record_anchor", 'RECORD.md must contain anchor text "总账文档"')
        )

    return issues


def check_file(path: Path, *, record_anchor: bool = False) -> list[EncodingIssue]:
    rel = path.as_posix()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return [EncodingIssue(rel, "io_error", str(exc))]
    return check_bytes(raw, path=rel, record_anchor=record_anchor)


def default_targets(root: Path) -> list[Path]:
    paths: list[Path] = []
    record = root / "RECORD.md"
    if record.is_file():
        paths.append(record)
    for subdir in (".project_memory", "docs", "openspec"):
        base = root / subdir
        if base.is_dir():
            paths.extend(sorted(base.rglob("*.md")))
    return paths


def resolve_extra_paths(root: Path, extras: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for item in extras:
        p = Path(item)
        if not p.is_absolute():
            p = root / p
        if p.is_file() and p.suffix.lower() == ".md":
            resolved.append(p)
        elif p.is_dir():
            resolved.extend(sorted(p.rglob("*.md")))
    return resolved


def check_all(root: Path, extra_paths: list[str] | None = None) -> list[EncodingIssue]:
    seen: set[Path] = set()
    issues: list[EncodingIssue] = []

    for path in default_targets(root):
        seen.add(path.resolve())

    for path in resolve_extra_paths(root, extra_paths or []):
        seen.add(path.resolve())

    for path in sorted(seen):
        anchor = path.name == "RECORD.md"
        issues.extend(check_file(path, record_anchor=anchor))

    return issues


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description=(
            "Check Chinese Markdown for UTF-8 / mojibake issues "
            "(default: RECORD.md, .project_memory, docs/, openspec/)."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional extra .md files or directories to check",
    )
    args = parser.parse_args(argv)

    issues = check_all(root, args.paths)
    if not issues:
        print("doc encoding OK (RECORD.md, .project_memory, docs/, openspec/)")
        return 0

    for issue in issues:
        print(f"{issue.path}: [{issue.code}] {issue.message}", file=sys.stderr)
    print(f"doc encoding check failed ({len(issues)} issue(s))", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
