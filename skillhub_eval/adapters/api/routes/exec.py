"""Execution bridge API routes for local agent preferences and consent."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import subprocess
import tempfile
import time

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from skillhub_eval.adapters.api.deps import get_repo
from skillhub_eval.execution.agent_registry import (
    DEFAULT_MODEL_ID,
    get_agent_catalog,
    resolve_adapter,
)
from skillhub_eval.execution.preflight_runner import PreflightRunner
from skillhub_eval.execution.runtime_defs import get_runtime_def
from skillhub_eval.execution.runtime_readiness import build_runtime_readiness
from skillhub_eval.execution.safe_preflight_case import ensure_safe_preflight_case_with_provider
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.execution.detection import detect_agent
from skillhub_eval.execution.models import ModelDiscovery, discover_models, is_model_verified_live
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
    install_status: str | None = None
    invocation_status: str | None = None
    model_status: str | None = None
    model_message_zh: str | None = None
    capability_status: str | None = None
    local_check_status: str | None = None
    local_check_checked_at: str | None = None
    local_check_expires_at: str | None = None
    local_check_message_zh: str | None = None
    can_run_local_check: bool | None = None
    can_switch_and_rerun: bool | None = None
    cli_version: str | None = None


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


class RuntimePreflightRequest(BaseModel):
    skill_bundle_path: str
    model: str | None = None
    force: bool = False
    regenerate_check_case: bool = False


class RuntimeSwitchRequest(BaseModel):
    runtime_id: str
    model: str | None = None
    skill_bundle_path: str


class RuntimeSwitchResponse(BaseModel):
    ok: bool
    message_zh: str
    preferences: ExecPreferencesResponse


class RuntimePreflightResponse(BaseModel):
    runtime_id: str
    model_id: str
    skill_fingerprint: str
    fingerprint: str
    status: str
    cached: bool = False
    checked_at: str
    expires_at: str
    cli_path: str | None = None
    cli_version: str | None = None
    failure_reason: str | None = None
    message_zh: str = ""
    manual_hint: str | None = None
    evidence: dict = Field(default_factory=dict)


_spawn_process = subprocess.Popen


def _supported_agent_ids() -> set[str]:
    return {agent.id for agent in get_agent_catalog()}


def _selected_model_readiness_from_discovery(
    *,
    selected_model: str,
    discovery: ModelDiscovery,
) -> tuple[str, str] | None:
    if selected_model == DEFAULT_MODEL_ID:
        return "default", "使用该 CLI 的默认模型（未在 SkillHub 中显式选择具体模型）。"
    if discovery.models_source != "live":
        return None
    live_ids = {m["id"] for m in discovery.models if m.get("source") == "live"}
    if selected_model in live_ids:
        return "ok", "已选模型已通过在线探测确认存在。"
    return "stale", (
        f"已选模型 {selected_model} 未出现在最近一次在线探测结果中，可能已失效或输入有误。"
    )


@router.get("/agents/scan", response_model=AgentScanResponse)
def scan_agents(
    skill_bundle_path: str | None = None,
    repo: SqliteRepository = Depends(get_repo),
) -> AgentScanResponse:
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
        selected_model_readiness: tuple[str, str] | None = None
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
                selected_model_readiness = _selected_model_readiness_from_discovery(
                    selected_model=selected_model,
                    discovery=disc,
                )
                if selected_model_readiness is None:
                    verified, probe_source = is_model_verified_live(agent, selected_model)
                    if probe_source != "live":
                        selected_model_readiness = (
                            "probe_unavailable",
                            "暂时无法在线探测该 Agent 的模型列表，无法确认已选模型是否有效。",
                        )
                    elif verified:
                        selected_model_readiness = (
                            "ok",
                            "已选模型已通过在线探测确认存在。",
                        )
                    else:
                        selected_model_readiness = (
                            "stale",
                            f"已选模型 {selected_model} 未出现在最近一次在线探测结果中，可能已失效或输入有误。",
                        )
                selected_model_status, selected_model_message = selected_model_readiness
        else:
            hint = get_install_hint(agent.id)
            if hint:
                install_command = hint.get("install_command")
                install_docs_url = hint.get("docs_url")
                install_note = hint.get("platform_note")

        readiness = build_runtime_readiness(
            agent,
            det=det,
            selected_model=selected_model if agent.id == active_agent_id else DEFAULT_MODEL_ID,
            active_agent_id=active_agent_id,
            skill_bundle_path=skill_bundle_path,
            repo=repo if skill_bundle_path else None,
            model_readiness=selected_model_readiness if agent.id == active_agent_id else None,
        )
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
                selected_model=selected_model if agent.id == active_agent_id else None,
                selected_model_status=selected_model_status,
                selected_model_message=selected_model_message,
                install_command=install_command,
                install_docs_url=install_docs_url,
                install_note=install_note,
                diagnosis_ok=diagnosis_ok,
                diagnosis_reason_code=diagnosis_reason_code,
                diagnosis_message=diagnosis_message,
                diagnosis_hint=diagnosis_hint,
                install_status=readiness["install_status"],
                invocation_status=readiness["invocation_status"],
                model_status=readiness["model_status"] if agent.id == active_agent_id else None,
                model_message_zh=readiness["model_message_zh"] if agent.id == active_agent_id else None,
                capability_status=readiness["capability_status"],
                local_check_status=readiness["local_check_status"],
                local_check_checked_at=readiness["local_check_checked_at"],
                local_check_expires_at=readiness["local_check_expires_at"],
                local_check_message_zh=readiness["local_check_message_zh"],
                can_run_local_check=readiness["can_run_local_check"],
                can_switch_and_rerun=readiness["can_switch_and_rerun"],
                cli_version=readiness.get("cli_version"),
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


@router.post("/runtimes/{runtime_id}/preflight", response_model=RuntimePreflightResponse)
async def run_runtime_preflight(
    runtime_id: str,
    body: RuntimePreflightRequest,
    repo: SqliteRepository = Depends(get_repo),
) -> RuntimePreflightResponse:
    runtime = get_runtime_def(runtime_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail=f"Unsupported runtime id: {runtime_id}")

    runner = PreflightRunner(repo=repo)
    model_id = body.model or DEFAULT_MODEL_ID
    if body.regenerate_check_case:
        await ensure_safe_preflight_case_with_provider(
            body.skill_bundle_path,
            force=True,
        )
    if not body.force:
        cached = runner.check_cached(
            body.skill_bundle_path,
            runtime_id=runtime.runtime_id,
            model_id=model_id,
        )
        if cached is not None:
            return RuntimePreflightResponse.model_validate({**cached, "cached": True})

    await ensure_safe_preflight_case_with_provider(body.skill_bundle_path)
    result = await asyncio.to_thread(
        runner.run,
        body.skill_bundle_path,
        runtime_id=runtime.runtime_id,
        model_id=model_id,
    )
    return RuntimePreflightResponse.model_validate(result.to_cache_row())


@router.post("/runtimes/switch", response_model=RuntimeSwitchResponse)
def switch_verified_runtime(
    body: RuntimeSwitchRequest,
    repo: SqliteRepository = Depends(get_repo),
) -> RuntimeSwitchResponse:
    runtime = get_runtime_def(body.runtime_id)
    if runtime is None:
        raise HTTPException(status_code=404, detail=f"Unsupported runtime id: {body.runtime_id}")

    model_id = body.model or DEFAULT_MODEL_ID
    readiness = build_runtime_readiness(
        next(agent for agent in get_agent_catalog() if agent.id == body.runtime_id),
        selected_model=model_id,
        active_agent_id=body.runtime_id,
        skill_bundle_path=body.skill_bundle_path,
        repo=repo,
    )
    if readiness.get("local_check_status") != "passed":
        raise HTTPException(
            status_code=409,
            detail="所选本地工具尚未通过当前 Skill 的本地执行环境检查，无法切换。",
        )

    updated = set_preferences(exec_agent=body.runtime_id, exec_model=model_id)
    label = runtime.label
    return RuntimeSwitchResponse(
        ok=True,
        message_zh=f"已切换到已检查通过的 {label}，可重新发起正式评估。",
        preferences=ExecPreferencesResponse.model_validate(updated),
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
