import json

import pytest

from skillhub_eval.core.schemas.report import ExecResult
from skillhub_eval.execution.consent import clear_exec_consent, grant_exec_consent
from skillhub_eval.execution.local_agent_source import LocalAgentSource
from skillhub_eval.execution.runner import LocalAgentRunner, _FakeProcess
from skillhub_eval.execution.workspace import PerRunWorkspace


class _StubAdapter:
    agent_id = "claude"

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        return ["stub"]

    def detect(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _consent():
    clear_exec_consent()
    grant_exec_consent("s")
    yield
    clear_exec_consent()


def _bundle_with_scripts(tmp_path):
    root = tmp_path / "skill"
    root.mkdir()
    (root / "SKILL.md").write_text("---\nname: s\n---\n", encoding="utf-8")
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "run.py").write_text("print(1)\n", encoding="utf-8")
    return {
        "skill_id": "s",
        "bundle_path": str(root),
        "has_scripts": True,
        "entrypoint": "scripts/run.py",
    }


def test_local_agent_source_returns_level2_with_evidence(tmp_path):
    lines = [
        json.dumps({"type": "tool_result", "stdout": "scripts/run.py", "exit_code": 0}),
        json.dumps({"type": "text", "delta": '```json\n{"ok": true}\n```'}),
        json.dumps({"type": "result", "usage": {"input_tokens": 3}, "duration_ms": 12}),
    ]

    def fake_spawn(args, **kwargs):
        return _FakeProcess(returncode=0, stdout_lines=[ln + "\n" for ln in lines])

    src = LocalAgentSource(
        runner=LocalAgentRunner(spawn_fn=fake_spawn),
        workspace=PerRunWorkspace(retain=True),
        adapter=_StubAdapter(),
    )
    bundle = _bundle_with_scripts(tmp_path)
    result = src.get_actual_output(
        bundle["bundle_path"],
        "h01",
        case={"id": "h01", "type": "happy_path", "user_intent": "go"},
        bundle=bundle,
    )
    assert isinstance(result, ExecResult)
    assert result.source == "local_agent"
    assert result.status == "ok"
    assert result.level == "level_2"
    assert result.actual_output == {"ok": True}


def test_local_agent_source_incomplete_without_entrypoint_evidence(tmp_path):
    lines = [
        json.dumps({"type": "tool_result", "stdout": "other.py", "exit_code": 0}),
        json.dumps({"type": "result"}),
    ]

    def fake_spawn(args, **kwargs):
        return _FakeProcess(returncode=0, stdout_lines=[ln + "\n" for ln in lines])

    src = LocalAgentSource(
        runner=LocalAgentRunner(spawn_fn=fake_spawn),
        workspace=PerRunWorkspace(retain=True),
        adapter=_StubAdapter(),
    )
    bundle = _bundle_with_scripts(tmp_path)
    result = src.get_actual_output(
        bundle["bundle_path"],
        "h01",
        case={"id": "h01", "type": "happy_path"},
        bundle=bundle,
    )
    assert result.status == "incomplete"


def test_local_agent_source_skips_redline_for_non_codex(tmp_path):
    src = LocalAgentSource(adapter=_StubAdapter())
    bundle = _bundle_with_scripts(tmp_path)
    result = src.get_actual_output(
        bundle["bundle_path"],
        "r01",
        case={"id": "r01", "type": "refusal_case"},
        bundle=bundle,
    )
    assert result.status == "incomplete"
    assert result.degrade_reason == "redline_no_hardened_profile"
