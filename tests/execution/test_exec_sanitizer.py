"""W8: local agent output sanitized before returning ExecResult."""

import json

import pytest

from skillhub_eval.execution.consent import grant_exec_consent
from skillhub_eval.execution.local_agent_source import LocalAgentSource
from skillhub_eval.execution.runner import LocalAgentRunner, _FakeProcess
from skillhub_eval.execution.workspace import PerRunWorkspace


class _StubAdapter:
    agent_id = "claude"

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        return ["stub"]

    def detect(self) -> bool:
        return True

    def parse_stream(self, lines: list[str]):
        from skillhub_eval.execution.stream_parser import parse_stream_events

        return parse_stream_events(lines)


@pytest.fixture(autouse=True)
def _consent():
    grant_exec_consent("s")


def test_local_agent_rejects_pii_in_actual_output(tmp_path):
    phone = "13800138000"
    lines = [
        json.dumps({
            "type": "text",
            "delta": f'```json\n{{"contact": "{phone}"}}\n```',
        }),
        json.dumps({"type": "result"}),
    ]

    def fake_spawn(args, **kwargs):
        return _FakeProcess(returncode=0, stdout_lines=[ln + "\n" for ln in lines])

    src = LocalAgentSource(
        runner=LocalAgentRunner(spawn_fn=fake_spawn),
        workspace=PerRunWorkspace(retain=True),
        adapter=_StubAdapter(),
    )
    bundle = {
        "skill_id": "s",
        "bundle_path": str(tmp_path),
        "has_scripts": False,
    }
    result = src.get_actual_output(
        bundle["bundle_path"],
        "h01",
        case={"id": "h01", "type": "happy_path"},
        bundle=bundle,
    )
    assert result.status == "incomplete"
    assert result.degrade_reason == "output_leak"
