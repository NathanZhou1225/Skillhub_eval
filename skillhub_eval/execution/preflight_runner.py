"""Runtime preflight execution and cache population."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, Literal

from skillhub_eval import __version__ as SKILLHUB_VERSION
from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.execution.agent_registry import DEFAULT_MODEL_ID, get_agent_def, resolve_adapter
from skillhub_eval.execution.detection import detect_agent
from skillhub_eval.execution.evidence import verify_entrypoint_evidence
from skillhub_eval.execution.preflight_cache import get_valid_runtime_preflight
from skillhub_eval.execution.runner import LocalAgentRunner
from skillhub_eval.execution.runtime_defs import RuntimeDef, get_runtime_def
from skillhub_eval.execution.runtime_fingerprint import runtime_fingerprint, skill_fingerprint
from skillhub_eval.execution.skill_injection import SkillInjectionError, prepare_skill_injection
from skillhub_eval.execution.transport.base import run_via_transport
from skillhub_eval.execution.workspace import PerRunWorkspace
from skillhub_eval.persistence.sqlite import SqliteRepository

PreflightStatus = Literal["passed", "failed", "blocked"]


@dataclass(frozen=True)
class PreflightResult:
    runtime_id: str
    model_id: str
    skill_fingerprint: str
    fingerprint: str
    status: PreflightStatus
    checked_at: str
    expires_at: str
    cli_path: str | None = None
    cli_version: str | None = None
    failure_reason: str | None = None
    message_zh: str = ""
    manual_hint: str | None = None
    evidence: dict = field(default_factory=dict)
    cached: bool = False

    def to_cache_row(self) -> dict:
        return {
            "runtime_id": self.runtime_id,
            "model_id": self.model_id,
            "skill_fingerprint": self.skill_fingerprint,
            "fingerprint": self.fingerprint,
            "status": self.status,
            "cli_path": self.cli_path,
            "cli_version": self.cli_version,
            "checked_at": self.checked_at,
            "expires_at": self.expires_at,
            "failure_reason": self.failure_reason,
            "message_zh": self.message_zh,
            "manual_hint": self.manual_hint,
            "evidence": self.evidence,
            "cached": self.cached,
        }


VersionProbe = Callable[[str, tuple[str, ...]], str | None]


class PreflightRunner:
    def __init__(
        self,
        *,
        repo: SqliteRepository,
        runner: LocalAgentRunner | None = None,
        workspace: PerRunWorkspace | None = None,
        version_probe: VersionProbe | None = None,
        ttl: timedelta = timedelta(hours=24),
        timeout_s: float = 300.0,
    ):
        self.repo = repo
        self.runner = runner or LocalAgentRunner()
        self.workspace = workspace or PerRunWorkspace()
        self.version_probe = version_probe or _cli_version
        self.ttl = ttl
        self.timeout_s = timeout_s

    def check_cached(
        self,
        skill_bundle_path: str | Path,
        *,
        runtime_id: str,
        model_id: str | None = None,
        locked_risk_level: str | None = None,
        now: datetime | None = None,
    ) -> dict | None:
        context = self._context(skill_bundle_path, runtime_id, model_id)
        if _requires_explicit_safe_preflight(context["bundle"], locked_risk_level):
            return None
        return get_valid_runtime_preflight(
            self.repo,
            runtime_id=context["runtime"].runtime_id,
            model_id=context["model_id"],
            skill_fingerprint=context["skill_fingerprint"],
            fingerprint=context["fingerprint"],
            now=now,
        )

    def run(
        self,
        skill_bundle_path: str | Path,
        *,
        runtime_id: str,
        model_id: str | None = None,
        locked_risk_level: str | None = None,
        now: datetime | None = None,
    ) -> PreflightResult:
        checked_at_dt = _utc_now(now)
        expires_at_dt = checked_at_dt + self.ttl
        checked_at = checked_at_dt.isoformat()
        expires_at = expires_at_dt.isoformat()

        try:
            context = self._context(skill_bundle_path, runtime_id, model_id)
        except ValueError as exc:
            result = PreflightResult(
                runtime_id=runtime_id,
                model_id=model_id or DEFAULT_MODEL_ID,
                skill_fingerprint="",
                fingerprint="",
                status="blocked",
                checked_at=checked_at,
                expires_at=expires_at,
                failure_reason="runtime_unknown",
                message_zh=str(exc),
            )
            return result

        runtime: RuntimeDef = context["runtime"]
        agent = context["agent"]
        bundle = context["bundle"]
        cli_path = context["cli_path"]
        cli_version = context["cli_version"]
        skill_fp = context["skill_fingerprint"]
        fingerprint = context["fingerprint"]
        model = context["model_id"]

        blocked = self._blocked_before_run(runtime, agent, bundle, cli_path, locked_risk_level)
        if blocked:
            result = self._result(
                runtime=runtime,
                model_id=model,
                skill_fingerprint=skill_fp,
                fingerprint=fingerprint,
                status="blocked",
                checked_at=checked_at,
                expires_at=expires_at,
                cli_path=cli_path,
                cli_version=cli_version,
                **blocked,
            )
            self._persist(result)
            return result

        adapter = resolve_adapter(runtime.runtime_id, model=model)
        if adapter is None:
            result = self._result(
                runtime=runtime,
                model_id=model,
                skill_fingerprint=skill_fp,
                fingerprint=fingerprint,
                status="blocked",
                checked_at=checked_at,
                expires_at=expires_at,
                cli_path=cli_path,
                cli_version=cli_version,
                failure_reason="runtime_adapter_unavailable",
                message_zh=f"{runtime.label} 暂无可用 adapter，无法运行本地 preflight。",
            )
            self._persist(result)
            return result

        run_dir = self.workspace.acquire(str(skill_bundle_path), "runtime-preflight")
        try:
            case = _preflight_case(bundle)
            try:
                prepared = prepare_skill_injection(runtime, case=case, bundle=bundle, skill_dir=run_dir)
            except SkillInjectionError as exc:
                result = self._result(
                    runtime=runtime,
                    model_id=model,
                    skill_fingerprint=skill_fp,
                    fingerprint=fingerprint,
                    status="blocked",
                    checked_at=checked_at,
                    expires_at=expires_at,
                    cli_path=cli_path,
                    cli_version=cli_version,
                    failure_reason=exc.reason_code,
                    message_zh=str(exc),
                )
                self._persist(result)
                return result

            outcome = run_via_transport(
                adapter,
                agent,
                prepared.prompt,
                cwd=str(run_dir),
                timeout_s=self.timeout_s,
                hardened=False,
                runner=self.runner,
            )
        finally:
            self.workspace.release(run_dir)

        parsed = outcome.parsed_stream
        evidence = {
            "exit_code": outcome.exit_code,
            "duration_ms": outcome.duration_ms,
            "stderr_excerpt": (outcome.stderr_text or "")[-1000:] or None,
            "strategy": prepared.strategy.value,
            "preflight_case_id": case.get("id"),
            "preflight_case_type": case.get("type"),
            "safe_preflight": bool(case.get("safe_preflight") or case.get("type") == "preflight"),
        }
        if parsed is not None:
            evidence["is_complete"] = parsed.is_complete
            evidence["is_error"] = parsed.is_error
            evidence["tool_result_count"] = len(parsed.tool_results)

        failure = _runtime_failure(bundle, runtime, outcome, self.runner)
        if failure:
            result = self._result(
                runtime=runtime,
                model_id=model,
                skill_fingerprint=skill_fp,
                fingerprint=fingerprint,
                status="failed",
                checked_at=checked_at,
                expires_at=expires_at,
                cli_path=cli_path,
                cli_version=cli_version,
                evidence=evidence,
                **failure,
            )
            self._persist(result)
            return result

        result = self._result(
            runtime=runtime,
            model_id=model,
            skill_fingerprint=skill_fp,
            fingerprint=fingerprint,
            status="passed",
            checked_at=checked_at,
            expires_at=expires_at,
            cli_path=cli_path,
            cli_version=cli_version,
            message_zh=f"{runtime.label} 已通过当前 skill 的本地 preflight。",
            evidence=evidence,
        )
        self._persist(result)
        return result

    def _context(self, skill_bundle_path: str | Path, runtime_id: str, model_id: str | None) -> dict:
        runtime = get_runtime_def(runtime_id)
        if runtime is None:
            raise ValueError(f"未知本地 runtime：{runtime_id}")
        agent = get_agent_def(runtime.runtime_id)
        if agent is None:
            raise ValueError(f"runtime 缺少 AgentDef 兼容定义：{runtime.runtime_id}")
        detection = detect_agent(agent, force=True)
        cli_path = detection.bin_path
        cli_version = self.version_probe(cli_path, runtime.binary.version_args) if cli_path else None
        model = model_id or DEFAULT_MODEL_ID
        bundle = ingest_bundle(str(skill_bundle_path))
        skill_fp = skill_fingerprint(skill_bundle_path)
        fingerprint = runtime_fingerprint(
            runtime,
            model_id=model,
            cli_path=cli_path,
            cli_version=cli_version,
            skillhub_version=SKILLHUB_VERSION,
        )
        return {
            "runtime": runtime,
            "agent": agent,
            "bundle": bundle,
            "cli_path": cli_path,
            "cli_version": cli_version,
            "model_id": model,
            "skill_fingerprint": skill_fp,
            "fingerprint": fingerprint,
        }

    def _blocked_before_run(
        self,
        runtime: RuntimeDef,
        agent,
        bundle: dict,
        cli_path: str | None,
        locked_risk_level: str | None,
    ) -> dict | None:
        if not cli_path:
            return {
                "failure_reason": "runtime_cli_missing",
                "message_zh": f"未找到 {runtime.label} CLI，无法运行本地 preflight。",
                "manual_hint": f"请先安装并确认 {runtime.binary.primary} 在运行 SkillHub 的同一终端可用。",
            }
        detection = detect_agent(agent, force=False)
        if detection.auth_state == "missing":
            return {
                "failure_reason": "runtime_auth_missing",
                "message_zh": f"{runtime.label} CLI 已安装，但未发现可用登录/配置状态。",
                "manual_hint": "请先在运行 SkillHub 的同一账号下完成 CLI 登录或初始化。",
            }
        if _requires_explicit_safe_preflight(bundle, locked_risk_level):
            return {
                "failure_reason": "runtime_safe_preflight_required",
                "message_zh": "高风险 skill 缺少显式安全 preflight 用例，正式本地执行前已阻止。",
                "manual_hint": "请添加 safe_preflight/preflight 用例，或将一个低风险 happy_path 用例标记 safe_preflight: true。",
            }
        return None

    def _result(self, **kwargs) -> PreflightResult:
        runtime = kwargs.pop("runtime")
        return PreflightResult(runtime_id=runtime.runtime_id, **kwargs)

    def _persist(self, result: PreflightResult) -> None:
        row = result.to_cache_row()
        row.pop("cached", None)
        self.repo.upsert_runtime_preflight(**row)


def _preflight_case(bundle: dict) -> dict:
    for case in bundle.get("eval_cases") or []:
        if case.get("safe_preflight") or case.get("type") == "preflight":
            return dict(case)
    for case in bundle.get("eval_cases") or []:
        if case.get("type") == "happy_path":
            return dict(case)
    return {
        "id": "runtime_preflight",
        "type": "preflight",
        "user_intent": "Run the skill preflight with the smallest safe input and return the declared schema.",
    }


def _requires_explicit_safe_preflight(bundle: dict, locked_risk_level: str | None = None) -> bool:
    risk = str(locked_risk_level or bundle.get("risk_level_declared") or bundle.get("risk_level") or "low").lower()
    if risk != "high":
        return False
    for case in bundle.get("eval_cases") or []:
        if case.get("safe_preflight") or case.get("type") == "preflight":
            return False
    return True


def _runtime_failure(bundle: dict, runtime: RuntimeDef, outcome, runner: LocalAgentRunner) -> dict | None:
    if not runner.is_run_complete(outcome):
        return {
            "failure_reason": "runtime_run_incomplete",
            "message_zh": f"{runtime.label} preflight 未完成或返回错误。",
            "manual_hint": outcome.stderr_text,
        }
    parsed = outcome.parsed_stream
    if parsed is None:
        return {
            "failure_reason": "runtime_parser_missing",
            "message_zh": f"{runtime.label} preflight 没有可解析的输出流。",
        }
    if runtime.preflight.requires_entrypoint_evidence and bundle.get("has_scripts") and bundle.get("entrypoint"):
        if not verify_entrypoint_evidence(parsed.tool_results, bundle["entrypoint"]):
            return {
                "failure_reason": "runtime_missing_entrypoint_evidence",
                "message_zh": f"{runtime.label} preflight 未观察到 entrypoint 调用证据。",
                "manual_hint": f"请确认 CLI 可调用 {bundle['entrypoint']}，并能在流事件中暴露 tool_result。",
            }
    return None


def _cli_version(cli_path: str, version_args: tuple[str, ...]) -> str | None:
    try:
        completed = subprocess.run(
            [cli_path, *version_args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = (completed.stdout or completed.stderr or "").strip()
    return text.splitlines()[0][:200] if text else None


def _utc_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
