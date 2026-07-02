"""Execution bridge API routes for local agent preferences and consent."""

from __future__ import annotations

from datetime import UTC, datetime
import subprocess
import tempfile
import time

from fastapi import APIRouter, Body
from pydantic import BaseModel

from skillhub_eval.execution.agent_registry import (
    DEFAULT_MODEL_ID,
    get_agent_catalog,
    resolve_adapter,
)
from skillhub_eval.execution.detection import detect_agent
from skillhub_eval.execution.models import discover_models, is_model_verified_live
from skillhub_eval.execution.install_hints import get_install_hint
from skillhub_eval.execution.runner import LocalAgentRunner
from skillhub_eval.execution.preferences import (
    get_preferences,
    grant_persisted_consent,
    set_preferences,
)

router = APIRouter(prefix="/api/exec", tags=["exec"])


class AgentModelItem(BaseModel):
    id: str
    label: str
    source: str = "fallback"


class AgentScanItem(BaseModel):
    id: str
    label: str
    detected: bool
    auth_status: str | None = None
    model_hint: str | None = None
    bin_path: str | None = None
    detect_hint: str | None = None
    models: list[AgentModelItem] = []
    models_source: str = "none"
    selected_model: str | None = None
    selected_model_status: str | None = None
    selected_model_message: str | None = None
    install_command: str | None = None
    install_docs_url: str | None = None
    install_note: str | None = None
    diagnosis_ok: bool | None = None
    diagnosis_reason_code: str | None = None
    diagnosis_message: str | None = None
    diagnosis_hint: str | None = None


class AgentScanResponse(BaseModel):
    scanned_at: str
    agents: list[AgentScanItem]


class ExecPreferencesResponse(BaseModel):
    exec_source: str
    exec_agent: str
    exec_model: str
    consent_granted: bool
    ready: bool
    ready_reason: str | None = None


class ExecPreferencesUpdateRequest(BaseModel):
    exec_source: str | None = None
    exec_agent: str | None = None
    exec_model: str | None = None


class ExecConsentResponse(BaseModel):
    granted: bool
    preferences: ExecPreferencesResponse


class AgentTestResponse(BaseModel):
    ok: bool
    message: str
    duration_ms: int | None = None


class AgentTestRequest(BaseModel):
    model: str | None = None


_spawn_process = subprocess.Popen


def _supported_agent_ids() -> set[str]:
    return {agent.id for agent in get_agent_catalog()}


@router.get("/agents/scan", response_model=AgentScanResponse)
def scan_agents() -> AgentScanResponse:
    agents: list[AgentScanItem] = []
    prefs = get_preferences()
    selected_model = str(prefs.get("exec_model") or DEFAULT_MODEL_ID)
    active_agent_id = str(prefs.get("exec_agent") or "")
    for agent in get_agent_catalog():
        # Explicit user-initiated scan: bypass the TTL cache so a freshly
        # installed / authenticated CLI is picked up immediately.
        det = detect_agent(agent, force=True)
        models: list[AgentModelItem] = []
        models_source = "none"
        install_command = install_docs_url = install_note = None
        diagnosis_ok: bool | None = None
        diagnosis_reason_code: str | None = None
        diagnosis_message: str | None = None
        diagnosis_hint: str | None = None
        selected_model_status: str | None = None
        selected_model_message: str | None = None
        if det.detected:
            disc = discover_models(agent, stored_model=selected_model)
            models = [
                AgentModelItem(id=m["id"], label=m["label"], source=m.get("source", "fallback"))
                for m in disc.models
            ]
            models_source = disc.models_source
            adapter = resolve_adapter(agent.id, model=None)
            diagnose_fn = getattr(adapter, "diagnose", None)
            if callable(diagnose_fn):
                try:
                    diagnosis = diagnose_fn()
                except Exception:
                    diagnosis = None
                if diagnosis is not None:
                    diagnosis_ok = diagnosis.ok
                    diagnosis_reason_code = diagnosis.reason_code
                    diagnosis_message = diagnosis.message_zh
                    diagnosis_hint = diagnosis.manual_hint

            if agent.id == active_agent_id:
                if selected_model == DEFAULT_MODEL_ID:
                    selected_model_status = "default"
                    selected_model_message = "使用该 CLI 的默认模型（未在 SkillHub 中显式选择具体模型）。"
                else:
                    verified, probe_source = is_model_verified_live(agent, selected_model)
                    if probe_source != "live":
                        selected_model_status = "probe_unavailable"
                        selected_model_message = "暂时无法在线探测该 Agent 的模型列表，无法确认已选模型是否有效。"
                    elif verified:
                        selected_model_status = "ok"
                        selected_model_message = "已选模型已通过在线探测确认存在。"
                    else:
                        selected_model_status = "stale"
                        selected_model_message = (
                            f"已选模型 {selected_model} 未出现在最近一次在线探测结果中，可能已失效或输入有误。"
                        )
        else:
            hint = get_install_hint(agent.id)
            if hint:
                install_command = hint.get("install_command")
                install_docs_url = hint.get("docs_url")
                install_note = hint.get("platform_note")
        agents.append(
            AgentScanItem(
                id=agent.id,
                label=agent.label,
                detected=det.detected,
                auth_status=det.auth_state,
                bin_path=det.bin_path,
                detect_hint=det.detect_hint,
                models=models,
                models_source=models_source,
                selected_model=selected_model,
                selected_model_status=selected_model_status,
                selected_model_message=selected_model_message,
                install_command=install_command,
                install_docs_url=install_docs_url,
                install_note=install_note,
                diagnosis_ok=diagnosis_ok,
                diagnosis_reason_code=diagnosis_reason_code,
                diagnosis_message=diagnosis_message,
                diagnosis_hint=diagnosis_hint,
            )
        )
    return AgentScanResponse(scanned_at=datetime.now(UTC).isoformat(), agents=agents)


@router.get("/preferences", response_model=ExecPreferencesResponse)
def get_exec_preferences() -> ExecPreferencesResponse:
    return ExecPreferencesResponse.model_validate(get_preferences())


@router.put("/preferences", response_model=ExecPreferencesResponse)
def update_exec_preferences(
    body: ExecPreferencesUpdateRequest,
) -> ExecPreferencesResponse:
    updated = set_preferences(
        exec_source=body.exec_source,
        exec_agent=body.exec_agent,
        exec_model=body.exec_model,
    )
    return ExecPreferencesResponse.model_validate(updated)


@router.post("/consent", response_model=ExecConsentResponse)
def grant_exec_consent() -> ExecConsentResponse:
    grant_persisted_consent()
    prefs = ExecPreferencesResponse.model_validate(get_preferences())
    return ExecConsentResponse(granted=True, preferences=prefs)


@router.post("/agents/{agent_id}/test", response_model=AgentTestResponse)
def test_agent(agent_id: str, body: AgentTestRequest | None = Body(default=None)) -> AgentTestResponse:
    if agent_id not in _supported_agent_ids():
        return AgentTestResponse(ok=False, message=f"Unsupported agent id: {agent_id}.")

    # The caller must explicitly provide a model for this exact agent; otherwise
    # smoke tests keep using the CLI default to avoid cross-agent model leakage.
    requested_model = body.model if body else None
    adapter = resolve_adapter(agent_id, model=requested_model)
    if not adapter or not adapter.detect():
        return AgentTestResponse(ok=False, message=f"Agent '{agent_id}' not detected.")

    started = time.perf_counter()
    runner = LocalAgentRunner(spawn_fn=_spawn_process)
    smoke_cwd = tempfile.mkdtemp(prefix="skillhub_agent_test_")
    timeout_s = 90.0 if agent_id == "trae" else 60.0
    try:
        outcome = runner.run(
            adapter,
            "Reply OK",
            cwd=smoke_cwd,
            timeout_s=timeout_s,
        )
    except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
        return AgentTestResponse(
            ok=False,
            message=f"Agent smoke test failed: {exc}",
        )

    if not runner.is_run_complete(outcome):
        return AgentTestResponse(ok=False, message="Agent smoke test did not complete.")

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return AgentTestResponse(
        ok=True,
        message=f"Agent '{agent_id}' smoke test passed.",
        duration_ms=outcome.duration_ms if outcome.duration_ms is not None else elapsed_ms,
    )


def _probe_cursor_auth_status() -> str:
    """Best-effort auth probe for explicit checks; scan skips this (can hang on Windows)."""
    adapter = resolve_adapter("cursor-agent")
    if not adapter or not adapter.detect():
        return "unknown"
    bin_path = adapter.resolved_bin()
    proc = subprocess.Popen(
        [bin_path, "auth", "status"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        stdout, stderr = proc.communicate(timeout=1.5)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.communicate(timeout=0.5)
        except subprocess.TimeoutExpired:
            pass
        return "unknown"
    except OSError:
        return "unknown"

    text_out = (stdout or b"").decode("utf-8", errors="replace")
    text_err = (stderr or b"").decode("utf-8", errors="replace")
    if proc.returncode == 0:
        return "ok"
    output = f"{text_out}\n{text_err}".lower()
    if any(token in output for token in ("not logged", "unauth", "sign in", "login")):
        return "fail"
    return "unknown"
