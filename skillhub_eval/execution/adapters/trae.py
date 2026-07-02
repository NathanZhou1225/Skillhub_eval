"""Trae CLI adapter — stream-json print mode (G1/G6)."""

from __future__ import annotations

from dataclasses import dataclass

import yaml


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
        ]
        if self.model:
            args.extend(["-c", f"model.name={self.model}"])
        return args

    def parse_stream(self, lines: list[str]):
        from skillhub_eval.execution.stream_parser import parse_stream_events

        return parse_stream_events(lines)

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
        except OSError:
            raw_config = {}
        config = raw_config if isinstance(raw_config, dict) else {}
        configured_model = self.model or (
            config.get("model", {}).get("name") if isinstance(config.get("model"), dict) else None
        )
        if not config.get("models"):
            return diagnostics.DiagnosisResult(
                ok=False,
                reason_code="TRAE_MODEL_NOT_CONFIGURED",
                message_zh="Trae 配置里缺少 models provider 定义，当前模型不知道从哪个 provider 调用。",
                manual_hint="请在 trae_cli.yaml 中补充 models: 列表，包含模型名、provider、endpoint/API Key 等信息。",
            )

        if configured_model:
            verified, source = models_module.is_model_verified_live(agent, configured_model)
            if source != "live":
                return diagnostics.DiagnosisResult(
                    ok=False,
                    reason_code="TRAE_MODEL_PROBE_UNAVAILABLE",
                    message_zh="无法通过 trae-cli models 在线确认当前模型列表。",
                    manual_hint="请手动运行 trae-cli models，确认 CLI 已登录且模型 provider 配置可用。",
                )
            if not verified:
                return diagnostics.DiagnosisResult(
                    ok=False,
                    reason_code="TRAE_MODEL_NOT_IN_LIST",
                    message_zh=f"当前选择的 Trae 模型 {configured_model} 未出现在在线探测结果中。",
                    manual_hint="请确认模型名拼写与 trae-cli models 输出一致，或调整 Trae 配置中的默认模型。",
                )

        return diagnostics.DiagnosisResult(ok=True, reason_code=None, message_zh="Trae 配置检查通过。")
