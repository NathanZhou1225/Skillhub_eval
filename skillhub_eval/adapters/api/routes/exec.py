"""Execution bridge API routes for local agent preferences and consent."""

from __future__ import annotations

from datetime import UTC, datetime
import subprocess
import time

from fastapi import APIRouter
from pydantic import BaseModel

from skillhub_eval.execution.cli_detect import detect_hint_zh, find_cli_binary
from skillhub_eval.execution.runner import LocalAgentRunner
from skillhub_eval.execution.local_agent_source import _resolve_adapter
from skillhub_eval.execution.preferences import (
    get_preferences,
    grant_persisted_consent,
    set_preferences,
)

router = APIRouter(prefix="/api/exec", tags=["exec"])


class AgentScanItem(BaseModel):
    id: str
    label: str
    detected: bool
    auth_status: str | None = None
    model_hint: str | None = None
    bin_path: str | None = None
    detect_hint: str | None = None


class AgentScanResponse(BaseModel):
    scanned_at: str
    agents: list[AgentScanItem]


class ExecPreferencesResponse(BaseModel):
    exec_source: str
    exec_agent: str
    consent_granted: bool
    ready: bool
    ready_reason: str | None = None


class ExecPreferencesUpdateRequest(BaseModel):
    exec_source: str | None = None
    exec_agent: str | None = None


class ExecConsentResponse(BaseModel):
    granted: bool
    preferences: ExecPreferencesResponse


class AgentTestResponse(BaseModel):
    ok: bool
    message: str
    duration_ms: int | None = None


_AGENT_CATALOG: list[tuple[str, str]] = [
    ("claude", "Claude"),
    ("codex", "Codex"),
    ("cursor-agent", "Cursor Agent"),
]
_SUPPORTED_AGENT_IDS = {agent_id for agent_id, _label in _AGENT_CATALOG}
_spawn_process = subprocess.Popen


@router.get("/agents/scan", response_model=AgentScanResponse)
def scan_agents() -> AgentScanResponse:
    agents: list[AgentScanItem] = []
    for agent_id, label in _AGENT_CATALOG:
        adapter = _resolve_adapter(agent_id)
        bin_name = getattr(adapter, "bin", agent_id) if adapter else agent_id
        bin_path = find_cli_binary(bin_name) if adapter else None
        detected = bin_path is not None
        model_hint = getattr(adapter, "model", None) if adapter else None
        auth_status = None
        if agent_id == "cursor-agent":
            auth_status = _probe_cursor_auth_status()
        agents.append(
            AgentScanItem(
                id=agent_id,
                label=label,
                detected=detected,
                auth_status=auth_status,
                model_hint=model_hint,
                bin_path=bin_path,
                detect_hint=None if detected else detect_hint_zh(bin_name),
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
    )
    return ExecPreferencesResponse.model_validate(updated)


@router.post("/consent", response_model=ExecConsentResponse)
def grant_exec_consent() -> ExecConsentResponse:
    grant_persisted_consent()
    prefs = ExecPreferencesResponse.model_validate(get_preferences())
    return ExecConsentResponse(granted=True, preferences=prefs)


@router.post("/agents/{agent_id}/test", response_model=AgentTestResponse)
def test_agent(agent_id: str) -> AgentTestResponse:
    if agent_id not in _SUPPORTED_AGENT_IDS:
        return AgentTestResponse(ok=False, message=f"Unsupported agent id: {agent_id}.")

    adapter = _resolve_adapter(agent_id)
    if not adapter or not adapter.detect():
        return AgentTestResponse(ok=False, message=f"Agent '{agent_id}' not detected.")

    started = time.perf_counter()
    runner = LocalAgentRunner(spawn_fn=_spawn_process)
    try:
        outcome = runner.run(
            adapter,
            "Reply OK",
            cwd=".",
            timeout_s=5.0,
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
    """Best-effort auth probe; never launches a harness run."""
    adapter = _resolve_adapter("cursor-agent")
    if not adapter or not adapter.detect():
        return "unknown"
    try:
        proc = subprocess.run(
            [adapter.resolved_bin(), "auth", "status"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"

    if proc.returncode == 0:
        return "ok"
    output = f"{proc.stdout}\n{proc.stderr}".lower()
    if any(token in output for token in ("not logged", "unauth", "sign in", "login")):
        return "fail"
    return "unknown"
