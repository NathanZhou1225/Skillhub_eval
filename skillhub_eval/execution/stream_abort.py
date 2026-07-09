"""Streaming early-abort policies for local agent runs (preflight)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from skillhub_eval.core.schemas.report import ParsedStream

AbortCheck = Callable[["ParsedStream"], str | None]

_POST_KILL_WAIT_S = 5.0


def tool_call_failed(tool_result: dict) -> bool:
    """True when a normalized tool result indicates failure."""
    if tool_result.get("is_error") or tool_result.get("isError"):
        return True
    exit_code = tool_result.get("exit_code", tool_result.get("exitCode"))
    if exit_code is None:
        return False
    try:
        return int(exit_code) != 0
    except (TypeError, ValueError):
        return False


@dataclass(frozen=True)
class PreflightStreamAbortPolicy:
    max_failed_tools: int = 5
    max_consecutive_failures: int = 3
    max_total_tools: int = 12

    @classmethod
    def from_settings(cls) -> PreflightStreamAbortPolicy:
        from skillhub_eval.settings import settings

        return cls(
            max_failed_tools=int(settings.runtime_preflight_max_failed_tools),
            max_consecutive_failures=int(settings.runtime_preflight_max_consecutive_failures),
            max_total_tools=int(settings.runtime_preflight_max_total_tools),
        )


def preflight_abort_reason(parsed: ParsedStream, policy: PreflightStreamAbortPolicy) -> str | None:
    tools = list(parsed.tool_results or [])
    if len(tools) >= policy.max_total_tools:
        return "runtime_preflight_tool_budget_exceeded"

    failed_count = sum(1 for item in tools if tool_call_failed(item))
    if failed_count >= policy.max_failed_tools:
        return "runtime_tool_failures_exceeded"

    consecutive = 0
    for item in tools:
        if tool_call_failed(item):
            consecutive += 1
            if consecutive >= policy.max_consecutive_failures:
                return "runtime_tool_failures_exceeded"
        else:
            consecutive = 0
    return None


def preflight_abort_check(policy: PreflightStreamAbortPolicy | None = None) -> AbortCheck:
    resolved = policy or PreflightStreamAbortPolicy.from_settings()

    def _check(parsed: ParsedStream) -> str | None:
        return preflight_abort_reason(parsed, resolved)

    return _check


PREFLIGHT_ABORT_MESSAGES_ZH: dict[str, str] = {
    "runtime_tool_failures_exceeded": (
        "本地 preflight 在多次工具调用失败后已提前终止，请检查 CLI 环境与 Skill 入口。"
    ),
    "runtime_preflight_tool_budget_exceeded": (
        "本地 preflight 工具调用次数超出环境检查预算，疑似误跑完整业务流程，已提前终止。"
    ),
}
