import json
from unittest.mock import patch

from skillhub_eval.execution.adapters.antigravity import AntigravityAdapter
from skillhub_eval.execution.events import AgentEventType
from skillhub_eval.execution.exec_result_builder import parsed_stream_from_events


def test_antigravity_build_args_default_model():
    args = AntigravityAdapter().build_args(cwd="/ws")

    assert args[0] == "agy"
    assert "--model" not in args


def test_antigravity_build_args_with_model_writes_setting(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    adapter = AntigravityAdapter(model="gemini-3.1-pro")

    args = adapter.build_args(cwd="/ws")

    assert args[0] == "agy"
    assert adapter.model == "gemini-3.1-pro"
    data = json.loads(adapter.settings_path().read_text(encoding="utf-8"))
    assert data["model"] == "gemini-3.1-pro"


def test_antigravity_settings_path_uses_home(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    adapter = AntigravityAdapter(model="gemini-3.1-pro")

    assert adapter.settings_path() == tmp_path / ".gemini" / "antigravity-cli" / "settings.json"


def test_antigravity_write_model_setting_preserves_existing_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    adapter = AntigravityAdapter()
    path = adapter.settings_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"theme": "dark"}, ensure_ascii=False), encoding="utf-8")

    adapter.write_model_setting("gpt-5")

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"theme": "dark", "model": "gpt-5"}


def test_antigravity_write_model_setting_replaces_invalid_json(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    adapter = AntigravityAdapter()
    path = adapter.settings_path()
    path.parent.mkdir(parents=True)
    path.write_text("{bad json", encoding="utf-8")

    adapter.write_model_setting("gpt-5")

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"model": "gpt-5"}


@patch("skillhub_eval.execution.adapters.antigravity.find_cli_binary", return_value="/bin/agy")
def test_antigravity_detect(mock_find):
    adapter = AntigravityAdapter()

    assert adapter.detect() is True
    assert adapter.resolved_bin() == "/bin/agy"


def test_antigravity_parse_stream_accepts_plain_output():
    parsed = AntigravityAdapter().parse_stream(["plain output"])

    assert parsed.final_text == "plain output"
    assert parsed.is_complete is True


def test_antigravity_normalize_events_matches_plain_output_fallback():
    adapter = AntigravityAdapter()
    lines = ["plain output"]

    events = adapter.normalize_events(lines)
    parsed = adapter.parse_stream(lines)
    from_events = parsed_stream_from_events(events)

    assert [event.type for event in events] == [
        AgentEventType.TEXT_DELTA,
        AgentEventType.DONE,
    ]
    assert from_events == parsed


def test_antigravity_normalize_events_matches_structured_stream():
    adapter = AntigravityAdapter()
    lines = [
        json.dumps({"type": "text", "text": "OK"}),
        json.dumps({"type": "result", "duration_ms": 5}),
    ]

    events = adapter.normalize_events(lines)
    parsed = adapter.parse_stream(lines)
    from_events = parsed_stream_from_events(events)

    assert any(event.type == AgentEventType.TEXT_DELTA for event in events)
    assert any(event.type == AgentEventType.DONE for event in events)
    assert from_events == parsed


def test_antigravity_normalize_events_preserves_error_duration():
    adapter = AntigravityAdapter()
    lines = [
        json.dumps({"type": "result", "is_error": True, "error": "boom", "duration_ms": 5}),
    ]

    parsed = adapter.parse_stream(lines)

    assert parsed.is_error
    assert not parsed.is_complete
    assert parsed.error_text == "boom"
    assert parsed.duration_ms == 5


def test_antigravity_normalize_events_falls_back_for_unsupported_json_plus_plain_text():
    adapter = AntigravityAdapter()
    lines = [
        json.dumps({"type": "unknown"}),
        "plain output",
    ]

    parsed = adapter.parse_stream(lines)

    assert parsed.final_text == '{"type": "unknown"}\nplain output'
    assert parsed.is_complete
