import json

import pytest

from skillhub_eval.core.schemas.report import ExecResult, ParsedStream, RunOutcome
from skillhub_eval.execution.consent import clear_exec_consent, grant_exec_consent
from skillhub_eval.execution.local_agent_source import LocalAgentSource
from skillhub_eval.execution.runner import LocalAgentRunner, _FakeProcess
from skillhub_eval.execution.workspace import PerRunWorkspace


class _StubAdapter:
    agent_id = "claude"
    model = "claude-sonnet-4-6"

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        return ["stub"]

    def detect(self) -> bool:
        return True

    def parse_stream(self, lines: list[str]):
        from skillhub_eval.execution.stream_parser import parse_stream_events

        return parse_stream_events(lines)


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
    assert result.agent_id == "claude"
    assert result.agent_label == "Claude"
    assert result.model_id == "claude-sonnet-4-6"
    assert result.model_label == "claude-sonnet-4-6"


def test_local_agent_source_collects_workspace_artifacts(tmp_path):
    lines = [
        json.dumps({"type": "text", "delta": "wrote report"}),
        json.dumps({"type": "result"}),
    ]

    class _Runner:
        def is_run_complete(self, outcome):
            return True

        def run(self, adapter, prompt, *, cwd, timeout_s=300.0, hardened=False):
            report = tmp_path / "run" / "report.json"
            report.parent.mkdir(exist_ok=True)
            report.write_bytes(b'{"answer": 42}\n')
            return RunOutcome(parsed_stream=ParsedStream(final_text="wrote report", is_complete=True))

    class _Workspace:
        def acquire(self, bundle_path, case_id):
            run_dir = tmp_path / "run"
            run_dir.mkdir(exist_ok=True)
            return run_dir

        def release(self, run_dir):
            pass

    src = LocalAgentSource(
        runner=_Runner(),
        workspace=_Workspace(),
        adapter=_StubAdapter(),
    )

    result = src.get_actual_output(
        str(tmp_path),
        "h01",
        case={"id": "h01", "type": "happy_path"},
        bundle={"skill_id": "s", "has_scripts": False},
    )

    assert result.status == "ok"
    artifacts = result.actual_output["artifacts"]
    assert artifacts == [
        {
            "path": "report.json",
            "size_bytes": 15,
            "content": '{"answer": 42}\n',
        }
    ]


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


def test_rate_limit_retries_and_downgrades_concurrency(tmp_path):
    class _CodexAdapter:
        agent_id = "codex"
        model = None

        def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
            return ["codex"]

        def detect(self) -> bool:
            return True

        def parse_stream(self, lines: list[str]):
            from skillhub_eval.execution.stream_parser import parse_stream_events

            return parse_stream_events(lines)

    class _Runner:
        def __init__(self):
            self.calls = 0
            self.timeouts: list[float] = []

        def run(self, adapter, prompt, *, cwd, timeout_s=300.0, hardened=False):
            self.calls += 1
            self.timeouts.append(timeout_s)
            if self.calls == 1:
                return RunOutcome(
                    parsed_stream=ParsedStream(final_text="429 rate limit", is_complete=True),
                )
            return RunOutcome(
                parsed_stream=ParsedStream(final_text='{"ok": true}', is_complete=True),
            )

        def is_run_complete(self, outcome):
            return True

    class _Workspace:
        def acquire(self, bundle_path, case_id):
            return tmp_path

        def release(self, run_dir):
            pass

    runner = _Runner()
    src = LocalAgentSource(
        runner=runner,
        workspace=_Workspace(),
        adapter=_CodexAdapter(),
        concurrency=2,
        timeout_s=30,
    )

    result = src.get_actual_output(
        str(tmp_path),
        "happy_001",
        case={"id": "happy_001", "type": "happy_path"},
        bundle={"skill_id": "s"},
    )

    assert result.status == "ok"
    assert runner.calls == 2
    assert src.current_concurrency == 1
    assert runner.timeouts == [30, 30]


def test_rate_limit_detects_stderr_only(tmp_path):
    class _CodexAdapter:
        agent_id = "codex"
        model = None

        def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
            return ["codex"]

        def detect(self) -> bool:
            return True

        def parse_stream(self, lines: list[str]):
            from skillhub_eval.execution.stream_parser import parse_stream_events

            return parse_stream_events(lines)

    class _Runner:
        def __init__(self):
            self.calls = 0

        def run(self, adapter, prompt, *, cwd, timeout_s=300.0, hardened=False):
            self.calls += 1
            if self.calls == 1:
                return RunOutcome(
                    parsed_stream=ParsedStream(final_text="", is_complete=True),
                    stderr_text="HTTP 429 Too Many Requests",
                )
            return RunOutcome(
                parsed_stream=ParsedStream(final_text='{"ok": true}', is_complete=True),
            )

        def is_run_complete(self, outcome):
            return True

    class _Workspace:
        def acquire(self, bundle_path, case_id):
            return tmp_path

        def release(self, run_dir):
            pass

    src = LocalAgentSource(
        runner=_Runner(),
        workspace=_Workspace(),
        adapter=_CodexAdapter(),
        concurrency=2,
        timeout_s=30,
    )

    result = src.get_actual_output(
        str(tmp_path),
        "happy_001",
        case={"id": "happy_001", "type": "happy_path"},
        bundle={"skill_id": "s"},
    )

    assert result.status == "ok"
    assert src.current_concurrency == 1
