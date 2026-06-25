from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app


class _FakeAdapter:
    def __init__(self, agent_id: str, detected: bool, model: str | None = None):
        self.agent_id = agent_id
        self._detected = detected
        self.model = model
        self.bin = "traecli" if agent_id == "trae" else ("agy" if agent_id == "antigravity" else agent_id)

    def detect(self) -> bool:
        return self._detected

    def resolved_bin(self) -> str:
        return self.bin if self._detected else self.bin

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        _ = cwd, hardened
        return [self.bin, "exec"]

    def parse_stream(self, lines: list[str]):
        from skillhub_eval.execution.stream_parser import parse_stream_events

        return parse_stream_events(lines)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "exec_bridge_api.db")
    monkeypatch.setattr("skillhub_eval.settings.settings.eval_db_path", db_path)
    monkeypatch.setattr("skillhub_eval.settings.settings.exec_consent_required", True)
    monkeypatch.setattr("skillhub_eval.execution.consent._consented_skill_ids", set())

    detected = {
        "claude": True,
        "codex": False,
        "cursor-agent": True,
        "cursor_agent": True,
        "trae": True,
        "antigravity": False,
    }

    def fake_resolve(agent_id: str, model: str | None = None):
        ok = detected.get(agent_id, False)
        return _FakeAdapter(agent_id=agent_id, detected=ok, model=model or f"{agent_id}-model")

    def fake_find_cli(name: str):
        if name == "claude":
            return "/bin/claude"
        if name == "cursor-agent":
            return "/bin/cursor-agent"
        if name == "traecli":
            return "/bin/traecli"
        return None

    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec.resolve_adapter", fake_resolve
    )
    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec.find_cli_binary", fake_find_cli
    )
    monkeypatch.setattr(
        "skillhub_eval.execution.preferences._resolve_adapter", fake_resolve
    )
    monkeypatch.setattr(
        "skillhub_eval.execution.cli_detect.find_cli_binary", fake_find_cli
    )

    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_scan_and_preferences(client: TestClient):
    scan_resp = client.get("/api/exec/agents/scan")
    assert scan_resp.status_code == 200
    scan = scan_resp.json()
    assert "scanned_at" in scan
    agents = scan["agents"]
    assert [a["id"] for a in agents] == ["claude", "codex", "cursor-agent", "trae", "antigravity"]
    assert [a["label"] for a in agents] == [
        "Claude",
        "Codex",
        "Cursor Agent",
        "Trae",
        "Antigravity",
    ]
    assert [a["detected"] for a in agents] == [True, False, True, True, False]
    assert agents[0]["bin_path"] == "/bin/claude"
    assert agents[1]["detect_hint"]
    assert agents[2]["auth_status"] == "unknown"  # scan defers auth probe (Test button)
    assert all("models" in a for a in agents)
    assert all(a["models_source"] in {"fallback", "none"} for a in agents)
    assert agents[0]["selected_model"] == "default"

    pref_resp = client.get("/api/exec/preferences")
    assert pref_resp.status_code == 200
    prefs = pref_resp.json()
    assert prefs["exec_source"] == "local"
    assert prefs["exec_agent"] == "claude"
    assert prefs["exec_model"] == "default"
    assert prefs["consent_granted"] is False

    put_resp = client.put("/api/exec/preferences", json={"exec_source": "sample_io"})
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["exec_source"] == "sample_io"
    assert updated["ready"] is True
    assert updated["ready_reason"] is None

    after_put = client.get("/api/exec/preferences")
    assert after_put.status_code == 200
    assert after_put.json()["exec_source"] == "sample_io"
    assert after_put.json()["ready"] is True

    consent_resp = client.post("/api/exec/consent")
    assert consent_resp.status_code == 200
    consent_body = consent_resp.json()
    assert consent_body["granted"] is True
    assert consent_body["preferences"]["consent_granted"] is True

    final_pref = client.get("/api/exec/preferences")
    assert final_pref.status_code == 200
    assert final_pref.json()["consent_granted"] is True


def test_preferences_accept_exec_model(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "skillhub_eval.execution.preferences._is_agent_detected",
        lambda _agent: True,
    )

    resp = client.put(
        "/api/exec/preferences",
        json={"exec_source": "local", "exec_agent": "cursor-agent", "exec_model": "gpt-5"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["exec_model"] == "gpt-5"


def test_agent_test(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    class _FakeProcess:
        def __init__(self, lines: list[str], returncode: int = 0):
            self._stdout = "\n".join(lines)
            self.returncode = returncode

        def communicate(self, input: str | None = None, timeout: float | None = None):
            return (self._stdout, "")

        def wait(self, timeout: float | None = None) -> int:
            return self.returncode

    def fake_spawn(*args, **kwargs):
        _ = args, kwargs
        return _FakeProcess(
            [
                json.dumps({"type": "text", "delta": "OK"}),
                json.dumps({"type": "result", "duration_ms": 7}),
            ],
            returncode=0,
        )

    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec._spawn_process", fake_spawn)

    ok_resp = client.post("/api/exec/agents/claude/test")
    assert ok_resp.status_code == 200
    ok_body = ok_resp.json()
    assert ok_body["ok"] is True
    assert "message" in ok_body
    assert ok_body["duration_ms"] == 7

    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec.resolve_adapter",
        lambda agent_id, model=None: _FakeAdapter(agent_id=agent_id, detected=False, model=f"{agent_id}-model"),
    )
    fail_resp = client.post("/api/exec/agents/claude/test")
    assert fail_resp.status_code == 200
    fail_body = fail_resp.json()
    assert fail_body["ok"] is False
    assert "not detected" in fail_body["message"].lower()
