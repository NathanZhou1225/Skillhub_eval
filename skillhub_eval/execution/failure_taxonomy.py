"""Stable local runtime failure reason taxonomy."""

from __future__ import annotations

LOCAL_RUNTIME_FAILURE_CODES: dict[str, str] = {
    "consent_required": "LOCAL_RUNTIME_CONSENT_REQUIRED",
    "agent_unavailable": "LOCAL_RUNTIME_CLI_UNAVAILABLE",
    "local_runtime_definition_missing": "LOCAL_RUNTIME_DEFINITION_MISSING",
    "local_runtime_prompt_too_large": "LOCAL_RUNTIME_PROMPT_TOO_LARGE",
    "local_runtime_skill_injection_unavailable": "LOCAL_RUNTIME_SKILL_INJECTION_UNAVAILABLE",
    "run_incomplete": "LOCAL_RUNTIME_RUN_INCOMPLETE",
    "missing_entrypoint_evidence": "LOCAL_RUNTIME_MISSING_ENTRYPOINT_EVIDENCE",
    "output_leak": "LOCAL_RUNTIME_OUTPUT_LEAK",
    "redline_no_hardened_profile": "LOCAL_RUNTIME_HARDENED_PROFILE_UNAVAILABLE",
    "runtime_cli_missing": "LOCAL_RUNTIME_CLI_UNAVAILABLE",
    "runtime_auth_missing": "LOCAL_RUNTIME_AUTH_MISSING",
    "runtime_safe_preflight_required": "LOCAL_RUNTIME_SAFE_PREFLIGHT_REQUIRED",
    "runtime_adapter_unavailable": "LOCAL_RUNTIME_ADAPTER_UNAVAILABLE",
    "runtime_run_incomplete": "LOCAL_RUNTIME_RUN_INCOMPLETE",
    "runtime_parser_missing": "LOCAL_RUNTIME_PARSER_MISSING",
    "runtime_missing_entrypoint_evidence": "LOCAL_RUNTIME_MISSING_ENTRYPOINT_EVIDENCE",
}

LOCAL_RUNTIME_FAILURE_LABELS_ZH: dict[str, str] = {
    "LOCAL_RUNTIME_CONSENT_REQUIRED": "尚未授权本机执行。",
    "LOCAL_RUNTIME_CLI_UNAVAILABLE": "本地 CLI 未检测到或不可调用。",
    "LOCAL_RUNTIME_AUTH_MISSING": "本地 CLI 未登录或配置不可用。",
    "LOCAL_RUNTIME_DEFINITION_MISSING": "该 Agent 缺少 runtime 定义。",
    "LOCAL_RUNTIME_PROMPT_TOO_LARGE": "该 CLI 通过命令行参数接收 prompt，当前 prompt 超过安全长度。",
    "LOCAL_RUNTIME_SKILL_INJECTION_UNAVAILABLE": "当前 skill 无可用注入方式。",
    "LOCAL_RUNTIME_RUN_INCOMPLETE": "本地 runtime 未完成执行或输出流未结束。",
    "LOCAL_RUNTIME_PARSER_MISSING": "本地 runtime 输出无法解析。",
    "LOCAL_RUNTIME_MISSING_ENTRYPOINT_EVIDENCE": "未观察到入口脚本执行证据。",
    "LOCAL_RUNTIME_OUTPUT_LEAK": "本地产出疑似包含敏感信息，已拦截。",
    "LOCAL_RUNTIME_HARDENED_PROFILE_UNAVAILABLE": "该 runtime 不支持红线题所需强化模式。",
    "LOCAL_RUNTIME_SAFE_PREFLIGHT_REQUIRED": "高风险 skill 缺少安全 preflight 用例。",
    "LOCAL_RUNTIME_ADAPTER_UNAVAILABLE": "该 runtime 暂无可用 adapter。",
    "LOCAL_RUNTIME_UNKNOWN": "未知本地 runtime 失败。",
}


def runtime_failure_code(reason: str | None) -> str:
    return LOCAL_RUNTIME_FAILURE_CODES.get(reason or "", "LOCAL_RUNTIME_UNKNOWN")


def runtime_failure_label_zh(reason_or_code: str | None) -> str:
    if not reason_or_code:
        return LOCAL_RUNTIME_FAILURE_LABELS_ZH["LOCAL_RUNTIME_UNKNOWN"]
    code = reason_or_code if reason_or_code.startswith("LOCAL_RUNTIME_") else runtime_failure_code(reason_or_code)
    return LOCAL_RUNTIME_FAILURE_LABELS_ZH.get(code, code)
