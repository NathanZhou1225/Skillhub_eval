"""Red-line hardened execution profile selection."""

from __future__ import annotations

from skillhub_eval.execution.runner import AgentAdapter

_REDLINE_TYPES = frozenset({
    "refusal", "adversarial", "refusal_case", "adversarial_case",
})


def is_redline_case(case: dict) -> bool:
    return str(case.get("type") or "") in _REDLINE_TYPES


class HardenedProfile:
    """Codex-only hardened red-line runs; other agents degrade."""

    @staticmethod
    def supports_redline(adapter: AgentAdapter) -> bool:
        return getattr(adapter, "agent_id", "") == "codex"

    @staticmethod
    def redline_degrade_reason(adapter: AgentAdapter) -> str | None:
        if HardenedProfile.supports_redline(adapter):
            return None
        return "redline_no_hardened_profile"

    @staticmethod
    def use_hardened(adapter: AgentAdapter, case: dict) -> bool:
        return is_redline_case(case) and HardenedProfile.supports_redline(adapter)
