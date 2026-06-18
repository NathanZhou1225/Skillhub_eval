"""W8: HardenedProfile — codex redline only; others degrade."""

from skillhub_eval.execution.local_agent_source import LocalAgentSource
from skillhub_eval.execution.profile import HardenedProfile


class _ClaudeAdapter:
    agent_id = "claude"

    def detect(self) -> bool:
        return True


class _CodexAdapter:
    agent_id = "codex"


def test_hardened_profile_codex_supports_redline():
    assert HardenedProfile.supports_redline(_CodexAdapter()) is True
    assert HardenedProfile.redline_degrade_reason(_CodexAdapter()) is None
    assert HardenedProfile.use_hardened(
        _CodexAdapter(), {"type": "refusal_case"},
    ) is True


def test_hardened_profile_claude_degrades_redline(tmp_path):
    assert HardenedProfile.supports_redline(_ClaudeAdapter()) is False
    assert HardenedProfile.redline_degrade_reason(_ClaudeAdapter()) == (
        "redline_no_hardened_profile"
    )

    src = LocalAgentSource(adapter=_ClaudeAdapter())
    bundle = {
        "skill_id": "s",
        "bundle_path": str(tmp_path),
        "has_scripts": False,
    }
    from skillhub_eval.execution.consent import grant_exec_consent
    grant_exec_consent("s")
    result = src.get_actual_output(
        bundle["bundle_path"],
        "r01",
        case={"id": "r01", "type": "adversarial_case"},
        bundle=bundle,
    )
    assert result.status == "incomplete"
    assert result.degrade_reason == "redline_no_hardened_profile"
