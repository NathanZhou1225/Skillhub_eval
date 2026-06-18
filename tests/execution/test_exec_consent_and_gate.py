"""W8: exec consent gate + security blocked bundle must not spawn."""

import json

import pytest

from skillhub_eval.execution.consent import clear_exec_consent, grant_exec_consent
from skillhub_eval.execution.local_agent_source import LocalAgentSource
from skillhub_eval.execution.runner import LocalAgentRunner, _FakeProcess
from skillhub_eval.execution.workspace import PerRunWorkspace


class _CountingAdapter:
    agent_id = "claude"
    calls = 0

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        return ["stub"]

    def detect(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _reset_consent():
    clear_exec_consent()
    _CountingAdapter.calls = 0
    yield
    clear_exec_consent()


def test_local_agent_requires_consent_before_spawn(tmp_path):
    bundle = {
        "skill_id": "needs-consent",
        "bundle_path": str(tmp_path),
        "has_scripts": False,
    }
    lines = [json.dumps({"type": "result"})]

    def fake_spawn(args, **kwargs):
        _CountingAdapter.calls += 1
        return _FakeProcess(returncode=0, stdout_lines=[ln + "\n" for ln in lines])

    src = LocalAgentSource(
        runner=LocalAgentRunner(spawn_fn=fake_spawn),
        workspace=PerRunWorkspace(retain=True),
        adapter=_CountingAdapter(),
    )
    result = src.get_actual_output(
        bundle["bundle_path"],
        "h01",
        case={"id": "h01", "type": "happy_path"},
        bundle=bundle,
    )
    assert result.status == "incomplete"
    assert result.degrade_reason == "consent_required"
    assert _CountingAdapter.calls == 0

    grant_exec_consent("needs-consent")
    result2 = src.get_actual_output(
        bundle["bundle_path"],
        "h01",
        case={"id": "h01", "type": "happy_path"},
        bundle=bundle,
    )
    assert _CountingAdapter.calls == 1
    assert result2.status in ("ok", "incomplete")
