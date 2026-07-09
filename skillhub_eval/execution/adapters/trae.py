"""Trae CLI adapter — stream-json print mode (G1/G6)."""

from __future__ import annotations

import json
from dataclasses import dataclass

import yaml

from skillhub_eval.execution.events import AgentEvent, AgentEventType, ToolResultPayload
from skillhub_eval.execution.exec_result_builder import parsed_stream_from_events


def _extract_bash_commands(lines: list[str]) -> dict[str, str]:
    """Map assistant tool_call id -> Bash command string.

    Real trae-cli tool_result events never echo the command they ran back to
    the caller — the command only appears on the matching assistant
    `tool_calls` entry, correlated by id/tool_use_id (2026-07-02 real-machine
    finding).
    """
    commands: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "assistant":
            continue
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            call_id = call.get("id")
            function = call.get("function")
            if not call_id or not isinstance(function, dict) or function.get("name") != "Bash":
                continue
            raw_args = function.get("arguments")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                continue
            if isinstance(args, dict) and isinstance(args.get("command"), str):
                commands[call_id] = args["command"]
    return commands


def _normalize_tool_result_event(event: dict, commands: dict[str, str]) -> dict | None:
    """Normalize a real Trae `type: "user", subtype: "tool_result"` event into
    the flat shape verify_entrypoint_evidence() understands (command/stdout/
    stderr/exit_code/is_error).

    Real trae-cli nests execution output under `content.structured_content`
    and never emits the flat top-level `type: "tool_result"` shape the generic
    stream parser (`stream_parser.parse_stream_events`) assumes — so
    `verify_entrypoint_evidence()` always saw an empty list even when the
    entrypoint genuinely ran (2026-07-02 real-machine finding, same class of
    gap as the Cursor Agent D14 fix).
    """
    if event.get("type") != "user" or event.get("subtype") != "tool_result":
        return None
    content = event.get("content")
    if not isinstance(content, dict):
        return None
    structured = content.get("structured_content")
    structured = structured if isinstance(structured, dict) else {}
    return {
        "tool": event.get("tool_name"),
        "command": commands.get(event.get("tool_use_id")),
        "stdout": structured.get("stdout"),
        "stderr": structured.get("stderr"),
        "exit_code": structured.get("exit_code", structured.get("exitCode")),
        "is_error": bool(content.get("is_error")),
    }


def _resolved_bin() -> str:
    from skillhub_eval.execution.agent_registry import get_agent_def
    from skillhub_eval.execution.detection import resolve_agent_binary

    agent = get_agent_def("trae")
    return (resolve_agent_binary(agent) if agent else None) or "trae-cli"


@dataclass
class TraeAdapter:
    agent_id: str = "trae"
    model: str | None = None
    prompt_via_stdin: bool = False

    def detect(self) -> bool:
        from skillhub_eval.execution.agent_registry import get_agent_def
        from skillhub_eval.execution.detection import resolve_agent_binary

        agent = get_agent_def("trae")
        return bool(agent and resolve_agent_binary(agent))

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        args = [
            _resolved_bin(),
            "-p",
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--permission-mode", "bypass_permissions",
            "--yolo",
            # --permission-mode/--yolo only skip the confirmation prompt; the
            # model's actual tool access is a separate, additive allowlist that
            # otherwise defaults to a read-only command set (no python/node/sh —
            # confirmed via real-machine trace, 2026-07-02). Without this, Trae
            # can never invoke a skill's entrypoint script. Redline cases never
            # reach here for Trae (no hardened profile → degrades earlier), so
            # unlocking full Bash here only ever applies to happy/edge cases.
            "--allowed-tool", "Bash",
        ]
        if self.model:
            args.extend(["-c", f"model.name={self.model}"])
        return args

    def parse_stream(self, lines: list[str]):
        return parsed_stream_from_events(self.normalize_events(lines))

    def normalize_events(self, lines: list[str]) -> list[AgentEvent]:
        commands = _extract_bash_commands(lines)
        events: list[AgentEvent] = []
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            event_type = event.get("type")
            if event_type in ("text", "assistant"):
                delta = event.get("delta") or event.get("text") or ""
                if isinstance(delta, str) and delta:
                    events.append(AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": delta}))
            elif event_type == "item.completed":
                item = event.get("item")
                if isinstance(item, dict) and item.get("type") == "agent_message":
                    text = item.get("text") or ""
                    if isinstance(text, str) and text:
                        events.append(AgentEvent(type=AgentEventType.TEXT_DELTA, payload={"text": text}))
            elif event_type == "tool_result":
                events.append(AgentEvent(type=AgentEventType.TOOL_RESULT, payload=event))
            elif event_type in ("result", "turn.completed"):
                payload: dict = {}
                if event.get("is_error") or event.get("subtype") == "error_during_execution":
                    payload["is_error"] = True
                    raw_error = event.get("error") or event.get("message")
                    if isinstance(raw_error, str) and raw_error:
                        payload["error_text"] = raw_error
                elif event_type == "result":
                    result_text = event.get("result") or event.get("text")
                    if isinstance(result_text, str) and result_text:
                        payload["result"] = result_text
                if isinstance(event.get("usage"), dict):
                    events.append(AgentEvent(type=AgentEventType.USAGE, payload=event["usage"]))
                if event.get("duration_ms") is not None:
                    payload["duration_ms"] = event["duration_ms"]
                events.append(AgentEvent(type=AgentEventType.DONE, payload=payload))
            normalized = _normalize_tool_result_event(event, commands)
            if normalized is not None:
                events.append(AgentEvent(type=AgentEventType.TOOL_RESULT, payload=_tool_result_payload(normalized)))
        return events

    def diagnose(self):
        from skillhub_eval.execution.agent_registry import get_agent_def
        from skillhub_eval.execution import diagnostics, models as models_module
        from skillhub_eval.execution.detection import config_dir_path

        agent = get_agent_def("trae")
        cfg_dir = config_dir_path(agent) if agent else None
        if cfg_dir is None or not cfg_dir.is_dir():
            return diagnostics.DiagnosisResult(
                ok=False,
                reason_code="TRAE_CONFIG_DIR_MISSING",
                message_zh="未找到 Trae 配置目录，trae-cli 可能尚未初始化或未登录。",
                manual_hint="请先在运行 SkillHub serve 的同一账号下完成 trae-cli 登录/初始化。",
            )
        if not diagnostics.check_writable(cfg_dir):
            return diagnostics.DiagnosisResult(
                ok=False,
                reason_code="TRAE_CONFIG_DIR_NOT_WRITABLE",
                message_zh="SkillHub 当前进程无法写入 Trae 配置目录。",
                manual_hint=f"请确认运行 serve 的账号对 {cfg_dir} 具有写权限。",
            )

        config_path = cfg_dir / "trae_cli.yaml"
        if not config_path.is_file():
            config_path = cfg_dir / "traecli.yaml"
        try:
            raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
        except yaml.YAMLError:
            return diagnostics.DiagnosisResult(
                ok=False,
                reason_code="TRAE_CONFIG_PARSE_ERROR",
                message_zh="Trae 配置文件无法解析，请检查 YAML 格式。",
                manual_hint=f"请打开 {config_path} 检查缩进、括号和冒号格式。",
            )
        except OSError:
            raw_config = {}
        config = raw_config if isinstance(raw_config, dict) else {}
        configured_model = self.model or (
            config.get("model", {}).get("name") if isinstance(config.get("model"), dict) else None
        )

        # Built-in Trae models (e.g. GLM-5.2) authenticate via account login and
        # need no local `models:` provider block, so a live probe that actually
        # confirms/rules out the configured model is authoritative and checked
        # first. The static `models:` section is only a fallback signal for when
        # the live probe itself is unavailable (found via real-machine testing,
        # 2026-07-02 — see design.md Q-29 follow-up).
        if configured_model:
            verified, source = models_module.is_model_verified_live(agent, configured_model)
            if source == "live":
                if verified:
                    return diagnostics.DiagnosisResult(ok=True, reason_code=None, message_zh="Trae 配置检查通过。")
                return diagnostics.DiagnosisResult(
                    ok=False,
                    reason_code="TRAE_MODEL_NOT_IN_LIST",
                    message_zh=f"当前选择的 Trae 模型 {configured_model} 未出现在在线探测结果中。",
                    manual_hint="请确认模型名拼写与 trae-cli models 输出一致，或调整 Trae 配置中的默认模型。",
                )
            if not config.get("models"):
                return diagnostics.DiagnosisResult(
                    ok=True,
                    reason_code=None,
                    message_zh=(
                        f"Trae 已配置模型 {configured_model}，但当前 CLI 无法在线枚举模型列表；"
                        "连接测试通过时可继续使用，正式评估以实际 case 执行为准。"
                    ),
                    manual_hint="如需精确校验模型，请手动运行 trae-cli models；自定义 provider 场景可在 trae_cli.yaml 中补充 models: 列表。",
                )
            return diagnostics.DiagnosisResult(
                ok=False,
                reason_code="TRAE_MODEL_PROBE_UNAVAILABLE",
                message_zh="无法通过 trae-cli models 在线确认当前模型列表。",
                manual_hint="请手动运行 trae-cli models，确认 CLI 已登录且模型 provider 配置可用。",
            )

        if not config.get("models"):
            return diagnostics.DiagnosisResult(
                ok=False,
                reason_code="TRAE_MODEL_NOT_CONFIGURED",
                message_zh="Trae 配置里缺少 models provider 定义，且未指定具体模型名。",
                manual_hint="请在 trae_cli.yaml 中补充 models: 列表，包含模型名、provider、endpoint/API Key 等信息，或在 SkillHub 中选择具体模型。",
            )

        return diagnostics.DiagnosisResult(ok=True, reason_code=None, message_zh="Trae 配置检查通过。")


def _tool_result_payload(raw: dict) -> ToolResultPayload:
    return ToolResultPayload(
        tool=str(raw.get("tool") or ""),
        command=raw.get("command") if isinstance(raw.get("command"), str) else None,
        stdout=raw.get("stdout") if isinstance(raw.get("stdout"), str) else "",
        stderr=raw.get("stderr") if isinstance(raw.get("stderr"), str) else "",
        exit_code=raw.get("exit_code") if isinstance(raw.get("exit_code"), int) else None,
        is_error=bool(raw.get("is_error")),
    )
