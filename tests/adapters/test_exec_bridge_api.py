from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
import yaml
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.execution.diagnostics import DiagnosisResult


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

    def fake_detect(agent, force=False):
        from skillhub_eval.execution.detection import DetectionResult
        ok = detected.get(agent.agent_id, False)
        if not ok:
            return DetectionResult(agent.agent_id, False, None, "missing", "未检测到")
        auth = "unknown" if agent.agent_id == "cursor-agent" else "ok"
        return DetectionResult(agent.agent_id, True, f"/bin/{agent.agent_id}", auth)

    def fake_discover(agent, stored_model=None):
        from skillhub_eval.execution.models import ModelDiscovery
        return ModelDiscovery(
            models=[{"id": "default", "label": "默认模型", "source": "fallback"}],
            models_source="fallback",
        )

    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec.resolve_adapter", fake_resolve
    )
    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec.detect_agent", fake_detect
    )
    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec.discover_models", fake_discover
    )
    monkeypatch.setattr(
        "skillhub_eval.execution.preferences._resolve_adapter", fake_resolve
    )
    monkeypatch.setattr(
        "skillhub_eval.execution.preferences._is_agent_detected",
        lambda agent_id: detected.get(agent_id, False),
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


def test_scan_returns_authstate_models_install_hint():
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from skillhub_eval.adapters.api.app import create_app
    from skillhub_eval.execution import detection
    from skillhub_eval.execution.detection import DetectionResult

    detection.clear_detection_cache()

    def fake_detect(agent, force=False):
        if agent.agent_id == "codex":
            return DetectionResult("codex", True, "/bin/codex", "ok")
        return DetectionResult(agent.agent_id, False, None, "missing", "not found")

    with patch("skillhub_eval.adapters.api.routes.exec.detect_agent", side_effect=fake_detect):
        resp = TestClient(create_app()).get("/api/exec/agents/scan")
    assert resp.status_code == 200
    agents = {a["id"]: a for a in resp.json()["agents"]}
    assert agents["codex"]["detected"] is True
    assert agents["codex"]["auth_status"] == "ok"
    assert agents["codex"]["models"]
    assert agents["claude"]["detected"] is False
    assert agents["claude"]["install_command"]


def test_scan_surfaces_agent_diagnosis(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    class _DiagnosingAdapter(_FakeAdapter):
        def diagnose(self):
            return DiagnosisResult(
                ok=False,
                reason_code="TRAE_MODEL_NOT_CONFIGURED",
                message_zh="Trae 模型未配置",
                manual_hint="补齐 models provider",
            )

    def fake_resolve(agent_id: str, model: str | None = None):
        if agent_id == "trae":
            return _DiagnosingAdapter(agent_id=agent_id, detected=True, model=model)
        return _FakeAdapter(agent_id=agent_id, detected=True, model=model)

    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec.resolve_adapter", fake_resolve)

    resp = client.get("/api/exec/agents/scan")
    assert resp.status_code == 200
    trae = next(a for a in resp.json()["agents"] if a["id"] == "trae")
    assert trae["diagnosis_ok"] is False
    assert trae["diagnosis_reason_code"] == "TRAE_MODEL_NOT_CONFIGURED"
    assert trae["diagnosis_message"] == "Trae 模型未配置"
    assert trae["diagnosis_hint"] == "补齐 models provider"


def test_scan_selected_model_default_does_not_probe(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    mock_verify = Mock(return_value=(True, "live"))
    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec.is_model_verified_live", mock_verify, raising=False)

    resp = client.get("/api/exec/agents/scan")
    assert resp.status_code == 200
    agents = {a["id"]: a for a in resp.json()["agents"]}
    assert agents["claude"]["selected_model_status"] == "default"
    assert "默认模型" in agents["claude"]["selected_model_message"]
    assert agents["trae"]["selected_model_status"] is None
    mock_verify.assert_not_called()


def test_scan_selected_model_stale_uses_live_verifier(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    client.put(
        "/api/exec/preferences",
        json={"exec_source": "local", "exec_agent": "trae", "exec_model": "GLM-5.2"},
    )
    mock_verify = Mock(return_value=(False, "live"))
    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec.is_model_verified_live", mock_verify, raising=False)

    resp = client.get("/api/exec/agents/scan")
    assert resp.status_code == 200
    agents = {a["id"]: a for a in resp.json()["agents"]}
    assert agents["trae"]["selected_model_status"] == "stale"
    assert "GLM-5.2" in agents["trae"]["selected_model_message"]
    mock_verify.assert_called_once()


def test_scan_reuses_discovered_live_models_for_active_selected_model(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    client.put(
        "/api/exec/preferences",
        json={"exec_source": "local", "exec_agent": "cursor-agent", "exec_model": "auto"},
    )
    calls: list[str] = []

    def fake_discover(agent, stored_model=None):
        from skillhub_eval.execution.models import ModelDiscovery

        calls.append(agent.id)
        if agent.id == "cursor-agent":
            return ModelDiscovery(
                models=[
                    {"id": "default", "label": "默认模型", "source": "live"},
                    {"id": "auto", "label": "Auto", "source": "live"},
                ],
                models_source="live",
            )
        return ModelDiscovery(
            models=[{"id": "default", "label": "默认模型", "source": "fallback"}],
            models_source="fallback",
        )

    unexpected_verify = Mock(side_effect=AssertionError("scan should reuse discovered models"))
    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec.discover_models", fake_discover)
    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec.is_model_verified_live", unexpected_verify, raising=False)
    monkeypatch.setattr("skillhub_eval.execution.runtime_readiness.is_model_verified_live", unexpected_verify, raising=False)

    resp = client.get("/api/exec/agents/scan")

    assert resp.status_code == 200
    cursor = next(a for a in resp.json()["agents"] if a["id"] == "cursor-agent")
    assert cursor["models_source"] == "live"
    assert cursor["selected_model_status"] == "ok"
    assert cursor["model_status"] == "ok"
    assert calls.count("cursor-agent") == 1
    unexpected_verify.assert_not_called()


def test_agent_smoke_uses_default_model_not_global_prefs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    """Test must not pass exec_model from prefs (e.g. trae GLM-5.2) to other agents."""
    seen: list[str | None] = []

    def fake_resolve(agent_id: str, model: str | None = None):
        seen.append(model)
        return _FakeAdapter(agent_id=agent_id, detected=True, model=model)

    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec.get_preferences",
        lambda: {"exec_model": "GLM-5.2", "exec_agent": "trae"},
    )
    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec.resolve_adapter",
        fake_resolve,
    )

    class _DoneProcess:
        returncode = 0

        def communicate(self, input=None, timeout=None):
            return ('{"type":"result","duration_ms":1}\n', "")

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec._spawn_process",
        lambda *a, **k: _DoneProcess(),
    )

    resp = client.post("/api/exec/agents/codex/test")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert seen == [None]


def test_agent_test_accepts_explicit_model(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen: list[str | None] = []

    def fake_resolve(agent_id: str, model: str | None = None):
        seen.append(model)
        return _FakeAdapter(agent_id=agent_id, detected=True, model=model)

    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec.resolve_adapter", fake_resolve)

    class _DoneProcess:
        returncode = 0

        def communicate(self, input=None, timeout=None):
            return ('{"type":"result","duration_ms":1}\n', "")

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec._spawn_process",
        lambda *a, **k: _DoneProcess(),
    )

    resp = client.post("/api/exec/agents/trae/test", json={"model": "GLM-5.2"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert seen == ["GLM-5.2"]


def test_agent_test_without_body_still_defaults_to_none(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen: list[str | None] = []

    def fake_resolve(agent_id: str, model: str | None = None):
        seen.append(model)
        return _FakeAdapter(agent_id=agent_id, detected=True, model=model)

    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec.resolve_adapter", fake_resolve)

    class _DoneProcess:
        returncode = 0

        def communicate(self, input=None, timeout=None):
            return ('{"type":"result","duration_ms":1}\n', "")

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec._spawn_process",
        lambda *a, **k: _DoneProcess(),
    )

    resp = client.post("/api/exec/agents/codex/test")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert seen == [None]


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


def test_runtime_preflight_returns_cached_result_without_switching_preferences(
    client: TestClient,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nid: skill.test\nname: Test\nrisk_level: low\n---\n# Test\n", encoding="utf-8")

    before = client.get("/api/exec/preferences").json()

    class _FakePreflightRunner:
        def __init__(self, repo):
            self.repo = repo

        def check_cached(self, skill_bundle_path, *, runtime_id, model_id):
            return {
                "runtime_id": runtime_id,
                "model_id": model_id,
                "skill_fingerprint": "skill-fp",
                "fingerprint": "runtime-fp",
                "status": "passed",
                "checked_at": "2026-07-05T00:00:00+00:00",
                "expires_at": "2026-07-06T00:00:00+00:00",
                "cli_path": "/bin/codex",
                "cli_version": "codex 1.0",
                "failure_reason": None,
                "message_zh": "cached ok",
                "manual_hint": None,
                "evidence": {"source": "cache"},
            }

        def run(self, *args, **kwargs):
            raise AssertionError("cache hit should not run preflight")

    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec.PreflightRunner", _FakePreflightRunner)

    resp = client.post(
        "/api/exec/runtimes/codex/preflight",
        json={"skill_bundle_path": str(skill), "model": "default"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "passed"
    assert body["cached"] is True
    assert body["evidence"] == {"source": "cache"}
    assert client.get("/api/exec/preferences").json() == before


def test_runtime_preflight_runs_when_cache_missing(client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch):
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nid: skill.test\nname: Test\nrisk_level: low\n---\n# Test\n", encoding="utf-8")

    class _FakeResult:
        def to_cache_row(self):
            return {
                "runtime_id": "trae",
                "model_id": "GLM-5.2",
                "skill_fingerprint": "skill-fp",
                "fingerprint": "runtime-fp",
                "status": "failed",
                "cached": False,
                "checked_at": "2026-07-05T00:00:00+00:00",
                "expires_at": "2026-07-06T00:00:00+00:00",
                "cli_path": "/bin/trae",
                "cli_version": "trae 1.0",
                "failure_reason": "runtime_missing_entrypoint_evidence",
                "message_zh": "missing evidence",
                "manual_hint": "check stream",
                "evidence": {"source": "run"},
            }

    class _FakePreflightRunner:
        def __init__(self, repo):
            self.repo = repo

        def check_cached(self, skill_bundle_path, *, runtime_id, model_id):
            return None

        def run(self, skill_bundle_path, *, runtime_id, model_id):
            assert runtime_id == "trae"
            assert model_id == "GLM-5.2"
            return _FakeResult()

    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec.PreflightRunner", _FakePreflightRunner)

    resp = client.post(
        "/api/exec/runtimes/trae/preflight",
        json={"skill_bundle_path": str(skill), "model": "GLM-5.2"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["cached"] is False
    assert body["failure_reason"] == "runtime_missing_entrypoint_evidence"
    assert body["evidence"] == {"source": "run"}


def test_runtime_preflight_regenerate_uses_template_without_provider(
    client: TestClient,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nid: skill.test\nname: Test\nrisk_level: high\nentrypoint: scripts/run.py\n---\n# Test\n",
        encoding="utf-8",
    )
    scripts = skill / "scripts"
    scripts.mkdir()
    (scripts / "run.py").write_text("print('ok')\n", encoding="utf-8")
    cases = skill / "eval_cases"
    cases.mkdir()
    for idx, ctype in enumerate(
        ["happy_path", "happy_path", "happy_path", "edge", "edge", "refusal", "refusal", "adversarial", "adversarial"]
    ):
        (cases / f"c{idx}.yaml").write_text(
            f"id: c{idx}\ntype: {ctype}\nuser_intent: test\ninput_template: x\nexpected_behavior: y\n",
            encoding="utf-8",
        )

    class _FakeResult:
        def to_cache_row(self):
            return {
                "runtime_id": "codex",
                "model_id": "default",
                "skill_fingerprint": "skill-fp",
                "fingerprint": "runtime-fp",
                "status": "failed",
                "cached": False,
                "checked_at": "2026-07-05T00:00:00+00:00",
                "expires_at": "2026-07-06T00:00:00+00:00",
                "failure_reason": "runtime_missing_entrypoint_evidence",
                "message_zh": "missing evidence",
                "evidence": {},
            }

    class _FakePreflightRunner:
        def __init__(self, repo):
            self.repo = repo

        def check_cached(self, *args, **kwargs):
            return None

        def run(self, *args, **kwargs):
            return _FakeResult()

    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec.PreflightRunner", _FakePreflightRunner)

    resp = client.post(
        "/api/exec/runtimes/codex/preflight",
        json={
            "skill_bundle_path": str(skill),
            "model": "default",
            "force": True,
            "regenerate_check_case": True,
        },
    )

    assert resp.status_code == 200
    generated = yaml.safe_load((cases / "runtime_preflight_01.yaml").read_text(encoding="utf-8"))
    assert generated["origin"] == "runtime_platform_template"


def test_runtime_preflight_rejects_unknown_runtime(client: TestClient, tmp_path):
    skill = tmp_path / "skill"
    skill.mkdir()
    resp = client.post(
        "/api/exec/runtimes/nope/preflight",
        json={"skill_bundle_path": str(skill), "model": "default"},
    )

    assert resp.status_code == 404


def test_scan_includes_runtime_readiness_fields(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "skillhub_eval.execution.runtime_readiness.probe_cli_invocation",
        lambda _path, _args: "ok",
    )
    resp = client.get("/api/exec/agents/scan")
    assert resp.status_code == 200
    agents = resp.json()["agents"]
    claude = next(a for a in agents if a["id"] == "claude")
    assert claude["install_status"] == "installed"
    assert claude["invocation_status"] == "ok"
    assert claude["local_check_status"] == "not_applicable"
    assert claude["can_run_local_check"] is False


def test_scan_local_check_passed_when_cache_valid(
    client: TestClient,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    from datetime import UTC, datetime, timedelta

    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nid: skill.test\nname: Test\nrisk_level: low\n---\n# Test\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "skillhub_eval.execution.runtime_readiness.probe_cli_invocation",
        lambda _path, _args: "ok",
    )
    monkeypatch.setattr("skillhub_eval.execution.preferences.get_exec_agent", lambda: "claude")
    monkeypatch.setattr("skillhub_eval.execution.preferences.get_exec_model", lambda: "default")

    from skillhub_eval.execution.preflight_runner import PreflightRunner
    from skillhub_eval.persistence.sqlite import SqliteRepository
    from skillhub_eval.settings import settings

    repo = SqliteRepository(settings.eval_db_path)
    repo.init_db()
    runner = PreflightRunner(repo=repo, version_probe=lambda _p, _a: "claude 1.0")
    context = runner._context(str(skill), "claude", "default")
    now = datetime.now(UTC)
    repo.upsert_runtime_preflight(
        runtime_id=context["runtime"].runtime_id,
        model_id=context["model_id"],
        skill_fingerprint=context["skill_fingerprint"],
        fingerprint=context["fingerprint"],
        status="passed",
        cli_path=context["cli_path"],
        cli_version=context["cli_version"],
        checked_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        failure_reason=None,
        message_zh="ok",
        manual_hint=None,
        evidence={},
    )

    resp = client.get("/api/exec/agents/scan", params={"skill_bundle_path": str(skill)})
    assert resp.status_code == 200
    claude = next(a for a in resp.json()["agents"] if a["id"] == "claude")
    assert claude["local_check_status"] == "passed"
    assert claude["local_check_message_zh"] == "已通过"
    assert claude["can_switch_and_rerun"] is True


def test_switch_verified_runtime_updates_preferences(client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch):
    from datetime import UTC, datetime, timedelta

    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nid: skill.test\nname: Test\nrisk_level: low\n---\n# Test\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "skillhub_eval.execution.runtime_readiness.probe_cli_invocation",
        lambda _path, _args: "ok",
    )

    from skillhub_eval.execution.preflight_runner import PreflightRunner
    from skillhub_eval.persistence.sqlite import SqliteRepository
    from skillhub_eval.settings import settings

    repo = SqliteRepository(settings.eval_db_path)
    repo.init_db()
    runner = PreflightRunner(repo=repo, version_probe=lambda _p, _a: "claude 1.0")
    context = runner._context(str(skill), "claude", "default")
    now = datetime.now(UTC)
    repo.upsert_runtime_preflight(
        runtime_id=context["runtime"].runtime_id,
        model_id=context["model_id"],
        skill_fingerprint=context["skill_fingerprint"],
        fingerprint=context["fingerprint"],
        status="passed",
        cli_path=context["cli_path"],
        cli_version=context["cli_version"],
        checked_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        failure_reason=None,
        message_zh="ok",
        manual_hint=None,
        evidence={},
    )

    before_catalog = [a.id for a in __import__("skillhub_eval.execution.agent_registry", fromlist=["get_agent_catalog"]).get_agent_catalog()]
    resp = client.post(
        "/api/exec/runtimes/switch",
        json={"runtime_id": "claude", "model": "default", "skill_bundle_path": str(skill)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["preferences"]["exec_agent"] == "claude"
    after_catalog = [a.id for a in __import__("skillhub_eval.execution.agent_registry", fromlist=["get_agent_catalog"]).get_agent_catalog()]
    assert before_catalog == after_catalog


def test_switch_verified_runtime_preserves_verified_model(client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch):
    from datetime import UTC, datetime, timedelta

    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nid: skill.test\nname: Test\nrisk_level: low\n---\n# Test\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "skillhub_eval.execution.runtime_readiness.probe_cli_invocation",
        lambda _path, _args: "ok",
    )
    from skillhub_eval.execution.detection import DetectionResult

    monkeypatch.setattr(
        "skillhub_eval.execution.runtime_readiness.detect_agent",
        lambda agent, force=True: DetectionResult(agent.agent_id, True, f"/bin/{agent.agent_id}", "ok"),
    )
    monkeypatch.setattr(
        "skillhub_eval.execution.preflight_runner.detect_agent",
        lambda agent, force=True: DetectionResult(agent.agent_id, True, f"/bin/{agent.agent_id}", "ok"),
    )

    from skillhub_eval.execution.preflight_runner import PreflightRunner
    from skillhub_eval.persistence.sqlite import SqliteRepository
    from skillhub_eval.settings import settings

    repo = SqliteRepository(settings.eval_db_path)
    repo.init_db()
    runner = PreflightRunner(repo=repo, version_probe=lambda _p, _a: None)
    context = runner._context(str(skill), "trae", "GLM-5.2")
    now = datetime.now(UTC)
    repo.upsert_runtime_preflight(
        runtime_id=context["runtime"].runtime_id,
        model_id=context["model_id"],
        skill_fingerprint=context["skill_fingerprint"],
        fingerprint=context["fingerprint"],
        status="passed",
        cli_path=context["cli_path"],
        cli_version=context["cli_version"],
        checked_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        failure_reason=None,
        message_zh="ok",
        manual_hint=None,
        evidence={},
    )

    resp = client.post(
        "/api/exec/runtimes/switch",
        json={"runtime_id": "trae", "model": "GLM-5.2", "skill_bundle_path": str(skill)},
    )

    assert resp.status_code == 200
    assert resp.json()["preferences"]["exec_agent"] == "trae"
    assert resp.json()["preferences"]["exec_model"] == "GLM-5.2"


def test_switch_rejects_unverified_runtime(client: TestClient, tmp_path, monkeypatch: pytest.MonkeyPatch):
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nid: skill.test\nname: Test\nrisk_level: low\n---\n# Test\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "skillhub_eval.execution.runtime_readiness.probe_cli_invocation",
        lambda _path, _args: "ok",
    )
    resp = client.post(
        "/api/exec/runtimes/switch",
        json={"runtime_id": "claude", "model": "default", "skill_bundle_path": str(skill)},
    )
    assert resp.status_code == 409
