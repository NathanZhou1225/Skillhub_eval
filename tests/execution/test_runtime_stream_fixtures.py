"""Sanitizer + committed runtime stream fixture regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.sanitize_runtime_stream import REDACTED_PATH, REDACTED_TOKEN, REDACTED_USER, sanitize_line, sanitize_text
from skillhub_eval.execution.adapters.antigravity import AntigravityAdapter
from skillhub_eval.execution.adapters.claude import ClaudeAdapter
from skillhub_eval.execution.adapters.codex import CodexAdapter
from skillhub_eval.execution.adapters.cursor_agent import CursorAgentAdapter
from skillhub_eval.execution.adapters.trae import TraeAdapter
from skillhub_eval.execution.evidence import verify_entrypoint_evidence
from skillhub_eval.execution.exec_result_builder import parsed_stream_from_events

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "runtime_streams"


def _load_lines(name: str) -> list[str]:
    path = FIXTURE_DIR / name
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_sanitizer_removes_sensitive_fields():
    raw = json.dumps(
        {
            "type": "tool_call",
            "prompt": "C:\\Users\\alice\\secret\\prompt " + ("x" * 400),
            "token": "sk-live-abcdefghijklmnopqrstuvwxyz",
            "command": "python C:\\Users\\alice\\proj\\scripts\\run.py",
        },
        ensure_ascii=False,
    )
    cleaned = sanitize_line(raw)
    assert REDACTED_USER in cleaned or REDACTED_PATH in cleaned
    assert "sk-live" not in cleaned
    assert REDACTED_TOKEN in cleaned
    assert len(cleaned) < len(raw)


def test_sanitizer_preserves_event_shape():
    raw = json.dumps({"type": "result", "subtype": "success", "duration_ms": 9})
    cleaned = sanitize_line(raw)
    payload = json.loads(cleaned)
    assert payload["type"] == "result"
    assert payload["duration_ms"] == 9


@pytest.mark.parametrize(
    ("fixture", "adapter_cls"),
    [
        ("cursor_agent_fixture.jsonl", CursorAgentAdapter),
        ("codex_fixture.jsonl", CodexAdapter),
        ("trae_fixture.jsonl", TraeAdapter),
        ("claude_fixture.jsonl", ClaudeAdapter),
        ("antigravity_fixture.txt", AntigravityAdapter),
    ],
)
def test_fixture_parses_through_adapter(fixture: str, adapter_cls):
    adapter = adapter_cls()
    lines = _load_lines(fixture)
    parsed = adapter.parse_stream(lines)
    from_events = parsed_stream_from_events(adapter.normalize_events(lines))
    assert from_events.is_complete == parsed.is_complete
    assert from_events.final_text == parsed.final_text


def test_cursor_fixture_has_entrypoint_evidence():
    adapter = CursorAgentAdapter()
    lines = _load_lines("cursor_agent_fixture.jsonl")
    parsed = adapter.parse_stream(lines)
    assert verify_entrypoint_evidence(parsed.tool_results, "scripts/run.py") is True


def test_codex_fixture_has_entrypoint_evidence():
    adapter = CodexAdapter()
    lines = _load_lines("codex_fixture.jsonl")
    parsed = adapter.parse_stream(lines)
    assert verify_entrypoint_evidence(parsed.tool_results, "scripts/run.py") is True


def test_sanitize_text_jsonl_roundtrip(tmp_path: Path):
    raw_path = tmp_path / "raw.jsonl"
    raw_path.write_text(
        "\n".join(
            [
                json.dumps({"type": "text", "text": "hello from /Users/bob/work"}),
                json.dumps({"type": "result", "duration_ms": 1}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    cleaned = sanitize_text(raw_path.read_text(encoding="utf-8"))
    assert REDACTED_PATH in cleaned or REDACTED_USER in cleaned
    assert json.loads(cleaned.splitlines()[0])["type"] == "text"
