import json
from unittest.mock import patch

import yaml

from skillhub_eval.execution import diagnostics, models as models_module
from skillhub_eval.execution.adapters.trae import TraeAdapter
from skillhub_eval.execution.evidence import verify_entrypoint_evidence
from skillhub_eval.execution.events import AgentEventType
from skillhub_eval.execution.exec_result_builder import parsed_stream_from_events


def _assert_equivalent_to_event_builder(adapter: TraeAdapter, lines: list[str]) -> None:
    parsed = adapter.parse_stream(lines)
    from_events = parsed_stream_from_events(adapter.normalize_events(lines))

    assert from_events.final_text == parsed.final_text
    assert from_events.tool_results == parsed.tool_results
    assert from_events.usage == parsed.usage
    assert from_events.duration_ms == parsed.duration_ms
    assert from_events.is_complete == parsed.is_complete
    assert from_events.is_error == parsed.is_error
    assert from_events.error_text == parsed.error_text


def test_build_args_stream_json():
    with patch("skillhub_eval.execution.adapters.trae._resolved_bin", return_value="trae-cli"):
        args = TraeAdapter(model=None).build_args(cwd="/tmp")
    assert args[0] == "trae-cli"
    assert "-p" in args or "--print" in args
    assert "--output-format" in args and "stream-json" in args
    assert "--yolo" in args
    assert "acp" not in args  # G1: no longer ACP


def test_build_args_unlocks_bash_tool():
    """Real-machine finding (2026-07-02): --permission-mode bypass_permissions and
    --yolo only skip the confirmation prompt; the tools available to the model are
    a separate, read-only default whitelist (cat/find/grep/... — no python/node/sh)
    that only --allowed-tool/allowed_tools can widen, additively. Without this flag
    Trae can never actually invoke a skill's entrypoint script, so every non-redline
    case looks like agent_unavailable-style failure even though the CLI itself ran."""
    with patch("skillhub_eval.execution.adapters.trae._resolved_bin", return_value="trae-cli"):
        args = TraeAdapter(model=None).build_args(cwd="/tmp")
    assert "--allowed-tool" in args
    idx = args.index("--allowed-tool")
    assert args[idx + 1] == "Bash"


def test_build_args_includes_model():
    with patch("skillhub_eval.execution.adapters.trae._resolved_bin", return_value="trae-cli"):
        args = TraeAdapter(model="GLM-5.2").build_args(cwd="/tmp")
    assert "--model" not in args
    assert "-c" in args
    assert "model.name=GLM-5.2" in args


def test_trae_prompt_via_stdin_false():
    assert TraeAdapter().prompt_via_stdin is False


def test_parse_stream_trae_result_event():
    a = TraeAdapter()
    lines = [
        '{"type":"stream_event","delta":{"role":"assistant","content":"OK"}}',
        '{"type":"result","subtype":"success","result":"OK","duration_ms":12004,'
        '"usage":{"input_tokens":10,"output_tokens":1}}',
    ]
    parsed = a.parse_stream(lines)
    assert parsed.is_complete is True
    assert "OK" in parsed.final_text


def test_parse_stream_reuses_generic_parser():
    a = TraeAdapter()
    parsed = a.parse_stream(['{"type":"result","result":"ok"}'])
    assert parsed.is_complete is True


def test_trae_parse_stream_captures_bash_tool_result_as_evidence():
    """Real trae-cli reports tool execution as `type: "user", subtype:
    "tool_result"` with output nested under content.structured_content, and
    never echoes the invoked command back in the tool_result itself — the
    command only appears on the matching assistant `tool_calls` entry,
    correlated by id/tool_use_id. The generic stream parser only recognized a
    flat top-level `type: "tool_result"` shape, so verify_entrypoint_evidence()
    always saw an empty list even when the entrypoint genuinely ran (2026-07-02
    real-machine finding, same class of gap as the Cursor Agent D14 fix)."""
    adapter = TraeAdapter()
    lines = [
        json.dumps({
            "type": "assistant",
            "message": {
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "Bash", "arguments": json.dumps({"command": "python scripts/run.py"})},
                    }
                ]
            },
        }),
        json.dumps({
            "type": "user",
            "subtype": "tool_result",
            "tool_use_id": "call_1",
            "tool_name": "Bash",
            "content": {
                "content": [{"type": "text", "text": '{"status": "success", "ok": true}'}],
                "structured_content": {"stdout": '{"status": "success", "ok": true}\n', "stderr": "", "interrupted": False},
                "is_error": False,
            },
        }),
        json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "done"}),
    ]
    parsed = adapter.parse_stream(lines)
    assert len(parsed.tool_results) == 1
    assert verify_entrypoint_evidence(parsed.tool_results, "scripts/run.py") is True


def test_trae_parse_stream_failed_bash_tool_result_is_not_evidence():
    adapter = TraeAdapter()
    lines = [
        json.dumps({
            "type": "assistant",
            "message": {
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "Bash", "arguments": json.dumps({"command": "python scripts/run.py"})},
                    }
                ]
            },
        }),
        json.dumps({
            "type": "user",
            "subtype": "tool_result",
            "tool_use_id": "call_1",
            "tool_name": "Bash",
            "content": {
                "content": [{"type": "text", "text": "boom"}],
                "structured_content": {"stdout": "", "stderr": "boom", "interrupted": False},
                "is_error": True,
            },
        }),
        json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "done"}),
    ]
    parsed = adapter.parse_stream(lines)
    assert verify_entrypoint_evidence(parsed.tool_results, "scripts/run.py") is False


def test_trae_normalize_events_correlates_tool_call_and_tool_result():
    lines = [
        json.dumps({
            "type": "assistant",
            "message": {
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {
                            "name": "Bash",
                            "arguments": json.dumps({"command": "python scripts/run.py"}),
                        },
                    }
                ]
            },
        }),
        json.dumps({
            "type": "user",
            "subtype": "tool_result",
            "tool_use_id": "call-1",
            "tool_name": "Bash",
            "content": {
                "structured_content": {"stdout": '{"ok": true}\n', "stderr": "", "exit_code": 0},
                "is_error": False,
            },
        }),
        json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": '```json\n{"ok": true}\n```',
            "duration_ms": 50,
        }),
    ]

    events = TraeAdapter().normalize_events(lines)

    assert any(
        e.type == AgentEventType.TOOL_RESULT and e.payload.command == "python scripts/run.py"
        for e in events
    )
    assert any(e.type == AgentEventType.DONE for e in events)


def test_trae_normalize_events_matches_parse_stream_for_generic_result_and_tool_result():
    adapter = TraeAdapter()
    lines = [
        json.dumps({
            "type": "assistant",
            "message": {
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "Bash", "arguments": json.dumps({"command": "python scripts/run.py"})},
                    }
                ]
            },
        }),
        json.dumps({
            "type": "user",
            "subtype": "tool_result",
            "tool_use_id": "call_1",
            "tool_name": "Bash",
            "content": {
                "structured_content": {"stdout": '{"status": "success"}\n', "stderr": "", "exit_code": 0},
                "is_error": False,
            },
        }),
        json.dumps({
            "type": "result",
            "subtype": "success",
            "result": "done",
            "duration_ms": 12004,
            "usage": {"input_tokens": 10, "output_tokens": 1},
        }),
    ]

    _assert_equivalent_to_event_builder(adapter, lines)


def test_diagnose_missing_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    result = TraeAdapter().diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_CONFIG_DIR_MISSING"


def test_diagnose_dir_not_writable(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / ".trae").mkdir()
    with patch.object(diagnostics, "check_writable", return_value=False):
        result = TraeAdapter().diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_CONFIG_DIR_NOT_WRITABLE"


def test_diagnose_missing_models_section(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump({"model": {"name": "GLM-5.2"}}), encoding="utf-8"
    )
    # Mock the live probe boundary so this test is deterministic regardless of
    # whether the machine running it happens to have a working trae-cli install.
    with patch.object(models_module, "_run_probe", return_value=None):
        result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_MODEL_NOT_CONFIGURED"


def test_diagnose_reads_fallback_config_filename(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "traecli.yaml").write_text(
        yaml.safe_dump({"model": {"name": "GLM-5.2"}}), encoding="utf-8"
    )
    with patch.object(models_module, "_run_probe", return_value=None):
        result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_MODEL_NOT_CONFIGURED"


def test_diagnose_malformed_config_returns_parse_error(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text("model: [\n", encoding="utf-8")
    result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_CONFIG_PARSE_ERROR"


def test_diagnose_probe_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump(
            {"model": {"name": "GLM-5.2"}, "models": [{"name": "GLM-5.2", "provider": "zhipu"}]}
        ),
        encoding="utf-8",
    )
    with patch.object(models_module, "_run_probe", return_value=None):
        result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_MODEL_PROBE_UNAVAILABLE"


def test_diagnose_model_not_in_probe_list(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump(
            {"model": {"name": "GLM-5.2"}, "models": [{"name": "other-model", "provider": "zhipu"}]}
        ),
        encoding="utf-8",
    )
    with patch.object(models_module, "_run_probe", return_value="other-model\n"):
        result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_MODEL_NOT_IN_LIST"


def test_diagnose_ok_when_live_verified_even_without_models_section(tmp_path, monkeypatch):
    """Regression (found during 2026-07-02 real-machine verification): built-in
    Trae models (e.g. GLM-5.2) authenticate via account login and need no local
    models: provider block. A live probe that actually confirms the configured
    model must win over "no models: section" — trae-cli demonstrably runs this
    model successfully even though trae_cli.yaml has no models: key at all."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump({"model": {"name": "GLM-5.2"}}), encoding="utf-8"
    )
    with patch.object(models_module, "_run_probe", return_value="GLM-5.2\n"):
        result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is True
    assert result.reason_code is None


def test_diagnose_not_in_list_wins_over_missing_models_section(tmp_path, monkeypatch):
    """A live probe that positively rules out the model is authoritative
    regardless of the local models: section — don't blame a "missing config"
    when we have direct evidence the model itself isn't available."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump({"model": {"name": "GLM-5.2"}}), encoding="utf-8"
    )
    with patch.object(models_module, "_run_probe", return_value="some-other-model\n"):
        result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_MODEL_NOT_IN_LIST"


def test_diagnose_ok_when_model_resolves(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump(
            {"model": {"name": "GLM-5.2"}, "models": [{"name": "GLM-5.2", "provider": "zhipu"}]}
        ),
        encoding="utf-8",
    )
    with patch.object(models_module, "_run_probe", return_value="GLM-5.2\n"):
        result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is True
    assert result.reason_code is None
