"""Execution bridge API routes for local agent preferences and consent."""

from __future__ import annotations

from datetime import UTC, datetime
import subprocess
import time

from fastapi import APIRouter
from pydantic import BaseModel

from skillhub_eval.execution.cli_detect import detect_hint_zh, find_cli_binary
from skillhub_eval.execution.agent_registry import (
    DEFAULT_MODEL_ID,
    ModelOption,
    get_agent_catalog,
    resolve_adapter,
)
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


_spawn_process = subprocess.Popen


def _supported_agent_ids() -> set[str]:
    return {agent.id for agent in get_agent_catalog()}


def _model_items(models: list[ModelOption]) -> list[AgentModelItem]:
    return [
        AgentModelItem(id=model.id, label=model.label, source="fallback")
        for model in models
    ]


@router.get("/agents/scan", response_model=AgentScanResponse)
def scan_agents() -> AgentScanResponse:
    agents: list[AgentScanItem] = []
    prefs = get_preferences()
    selected_model = str(prefs.get("exec_model") or DEFAULT_MODEL_ID)
    for agent in get_agent_catalog():
        adapter = resolve_adapter(agent.id, model=selected_model)
        bin_path = None
        for bin_name in agent.binary_names:
            bin_path = find_cli_binary(bin_name)
            if bin_path:
                break
        detected = bin_path is not None
        model_hint = getattr(adapter, "model", None) if adapter else None
        auth_status = None
        if agent.id == "cursor-agent" and detected:
            # Defer auth probe to Test — `cursor-agent auth status` can hang on Windows.
            auth_status = "unknown"
        models = _model_items(list(agent.fallback_models))
        agents.append(
            AgentScanItem(
                id=agent.id,
                label=agent.label,
                detected=detected,
                auth_status=auth_status,
                model_hint=model_hint,
                bin_path=bin_path,
                detect_hint=None if detected else detect_hint_zh(agent.bin),
                models=models,
                models_source="fallback" if models else "none",
                selected_model=selected_model,
            )
        )
    return AgentScanResponse(
        scanned_at=datetime.now(UTC).isoformat(),
        agents=agents,
    )


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
def test_agent(agent_id: str) -> AgentTestResponse:
    if agent_id not in _supported_agent_ids():
        return AgentTestResponse(ok=False, message=f"Unsupported agent id: {agent_id}.")

    prefs = get_preferences()
    adapter = resolve_adapter(
        agent_id,
        model=str(prefs.get("exec_model") or DEFAULT_MODEL_ID),
    )
    if not adapter or not adapter.detect():
        return AgentTestResponse(ok=False, message=f"Agent '{agent_id}' not detected.")

    started = time.perf_counter()
    runner = LocalAgentRunner(spawn_fn=_spawn_process)
    try:
        outcome = runner.run(
            adapter,
            "Reply OK",
            cwd=".",
            timeout_s=60.0,
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
