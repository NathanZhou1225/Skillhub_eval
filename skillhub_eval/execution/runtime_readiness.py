"""Product-level runtime readiness summaries for scan/API surfaces."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from typing import Any

from skillhub_eval.execution.agent_registry import AgentDef, DEFAULT_MODEL_ID
from skillhub_eval.execution.detection import DetectionResult, detect_agent
from skillhub_eval.execution.models import discover_models, is_model_verified_live
from skillhub_eval.execution.preflight_cache import _parse_iso_datetime
from skillhub_eval.execution.preflight_runner import PreflightRunner
from skillhub_eval.execution.runtime_defs import get_runtime_def
from skillhub_eval.execution.safe_preflight_case import build_safe_preflight_case
from skillhub_eval.persistence.sqlite import SqliteRepository

LOCAL_CHECK_MESSAGES_ZH: dict[str, str] = {
    "missing": "尚未检查",
    "passed": "已通过",
    "failed": "检查失败",
    "expired": "已过期",
    "blocked": "需要生成检查用例或修复环境",
    "not_applicable": "未选择 Skill",
}


def probe_cli_invocation(bin_path: str | None, version_args: tuple[str, ...]) -> str:
    """Return ok | missing | failed."""
    if not bin_path:
        return "missing"
    try:
        completed = subprocess.run(
            [bin_path, *version_args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError, TimeoutError):
        return "failed"
    if completed.returncode != 0:
        return "failed"
    return "ok"


def _model_readiness(agent: AgentDef, selected_model: str, *, is_active: bool) -> tuple[str, str]:
    if not is_active:
        return "unknown", "仅当前选中的本地工具会校验已选模型。"
    if selected_model == DEFAULT_MODEL_ID:
        return "default", "使用该 CLI 的默认模型（未在 SkillHub 中显式选择具体模型）。"
    verified, probe_source = is_model_verified_live(agent, selected_model)
    if probe_source != "live":
        return "probe_unavailable", "暂时无法在线探测该 Agent 的模型列表，无法确认已选模型是否有效。"
    if verified:
        return "ok", "已选模型已通过在线探测确认存在。"
    return "stale", (
        f"已选模型 {selected_model} 未出现在最近一次在线探测结果中，可能已失效或输入有误。"
    )


def _local_check_state(
    *,
    skill_bundle_path: str | None,
    runtime_id: str,
    model_id: str,
    repo: SqliteRepository | None,
    locked_risk_level: str | None = None,
) -> dict[str, Any]:
    if not skill_bundle_path or repo is None:
        return {
            "local_check_status": "not_applicable",
            "local_check_checked_at": None,
            "local_check_expires_at": None,
            "local_check_message_zh": LOCAL_CHECK_MESSAGES_ZH["not_applicable"],
            "can_run_local_check": False,
            "can_switch_and_rerun": False,
        }

    runner = PreflightRunner(repo=repo)
    try:
        context = runner._context(skill_bundle_path, runtime_id, model_id)
    except ValueError:
        return {
            "local_check_status": "blocked",
            "local_check_checked_at": None,
            "local_check_expires_at": None,
            "local_check_message_zh": LOCAL_CHECK_MESSAGES_ZH["blocked"],
            "can_run_local_check": False,
            "can_switch_and_rerun": False,
        }

    cached = runner.check_cached(
        skill_bundle_path,
        runtime_id=runtime_id,
        model_id=model_id,
        locked_risk_level=locked_risk_level,
    )
    if cached is not None and cached.get("status") == "passed":
        return {
            "local_check_status": "passed",
            "local_check_checked_at": cached.get("checked_at"),
            "local_check_expires_at": cached.get("expires_at"),
            "local_check_message_zh": LOCAL_CHECK_MESSAGES_ZH["passed"],
            "can_run_local_check": True,
            "can_switch_and_rerun": True,
        }

    latest = repo.get_runtime_preflight(
        runtime_id=context["runtime"].runtime_id,
        model_id=context["model_id"],
        skill_fingerprint=context["skill_fingerprint"],
    )
    if latest:
        expires_at = _parse_iso_datetime(latest.get("expires_at"))
        now = datetime.now(UTC)
        if latest.get("status") != "passed":
            status = "failed"
        elif expires_at is not None and expires_at <= now:
            status = "expired"
        elif latest.get("fingerprint") != context["fingerprint"]:
            status = "expired"
        else:
            status = "missing"
        return {
            "local_check_status": status,
            "local_check_checked_at": latest.get("checked_at"),
            "local_check_expires_at": latest.get("expires_at"),
            "local_check_message_zh": LOCAL_CHECK_MESSAGES_ZH.get(status, LOCAL_CHECK_MESSAGES_ZH["missing"]),
            "can_run_local_check": True,
            "can_switch_and_rerun": False,
        }

    can_generate = build_safe_preflight_case(
        context["bundle"],
        locked_risk_level=locked_risk_level,
    ) is not None or any(
        c.get("safe_preflight") or c.get("type") == "preflight"
        for c in context["bundle"].get("eval_cases") or []
    )
    status = "missing" if can_generate else "blocked"
    return {
        "local_check_status": status,
        "local_check_checked_at": None,
        "local_check_expires_at": None,
        "local_check_message_zh": LOCAL_CHECK_MESSAGES_ZH[status],
        "can_run_local_check": can_generate,
        "can_switch_and_rerun": False,
    }


def build_runtime_readiness(
    agent: AgentDef,
    *,
    det: DetectionResult | None = None,
    selected_model: str,
    active_agent_id: str,
    skill_bundle_path: str | None = None,
    repo: SqliteRepository | None = None,
    locked_risk_level: str | None = None,
    cli_version: str | None = None,
    model_readiness: tuple[str, str] | None = None,
) -> dict[str, Any]:
    det = det or detect_agent(agent, force=True)
    runtime = get_runtime_def(agent.id)
    version_args = runtime.binary.version_args if runtime else ("--version",)

    install_status = "installed" if det.detected else "missing"
    invocation_status = probe_cli_invocation(det.bin_path, version_args) if det.detected else "missing"
    auth_status = det.auth_state if det.detected else "missing"

    is_active = agent.id == active_agent_id
    if model_readiness is not None:
        model_status, model_message_zh = model_readiness
    else:
        model_status, model_message_zh = _model_readiness(agent, selected_model, is_active=is_active)

    capability_status = "ready" if det.detected and invocation_status == "ok" else "unavailable"
    if det.detected and auth_status == "missing":
        capability_status = "auth_missing"

    local_check = _local_check_state(
        skill_bundle_path=skill_bundle_path,
        runtime_id=agent.id,
        model_id=selected_model,
        repo=repo,
        locked_risk_level=locked_risk_level,
    )

    return {
        "install_status": install_status,
        "invocation_status": invocation_status,
        "auth_status": auth_status,
        "model_status": model_status,
        "model_message_zh": model_message_zh,
        "capability_status": capability_status,
        "cli_version": cli_version,
        **local_check,
    }
