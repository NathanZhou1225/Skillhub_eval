import json

from skillhub_eval.execution.stream_parser import (
    collect_actual_output,
    extract_fenced_json,
    parse_stream_events,
)


def test_parse_stream_empty():
    parsed = parse_stream_events([])
    assert parsed.final_text == ""
    assert not parsed.is_complete


def test_extract_fenced_json_invalid_returns_none():
    assert extract_fenced_json("no json here") is None
    assert extract_fenced_json("```json\n{bad}\n```") is None


def test_collect_actual_output_empty_parsed():
    from skillhub_eval.core.schemas.report import ParsedStream

    assert collect_actual_output(ParsedStream()) == {}


def test_parse_stream_ignores_malformed_lines():
    lines = ["not-json", json.dumps({"type": "result"})]
    parsed = parse_stream_events(lines)
    assert parsed.is_complete
