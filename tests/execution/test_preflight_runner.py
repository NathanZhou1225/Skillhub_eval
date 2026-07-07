import json
from datetime import UTC, datetime
from unittest.mock import patch

from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.execution.preflight_runner import PreflightRunner
from skillhub_eval.execution.runner import LocalAgentRunner, _FakeProcess
from skillhub_eval.persistence.sqlite import SqliteRepository


def _skill(tmp_path, *, risk: str = "low"):
    root = tmp_path / "skill"
    root.mkdir()
    (root / "SKILL.md").write_text(
        f"---\nid: skill.test\nname: Test Skill\nrisk_level: {risk}\nentrypoint: scripts/run.py\n---\n# Test\n",
        encoding="utf-8",
    )
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "run.py").write_text("print(1)\n", encoding="utf-8")
    eval_cases = root / "eval_cases"
    eval_cases.mkdir()
    (eval_cases / "h01.yaml").write_text(
        "id: h01\ntype: happy_path\nuser_intent: run it\n",
        encoding="utf-8",
    )
    return root


def _repo(tmp_path):
    repo = SqliteRepository(str(tmp_path / "preflight.db"))
    repo.init_db()
    return repo


def test_preflight_passes_and_writes_cache(tmp_path):
    skill = _skill(tmp_path)
    lines = [
        json.dumps({"type": "tool_result", "stdout": "scripts/run.py", "exit_code": 0}),
        json.dumps({"type": "text", "delta": '```json\n{"ok": true}\n```'}),
        json.dumps({"type": "result", "duration_ms": 3}),
    ]

    def fake_spawn(args, **kwargs):
        return _FakeProcess(returncode=0, stdout_lines=[line + "\n" for line in lines])

    repo = _repo(tmp_path)
    runner = PreflightRunner(
        repo=repo,
        runner=LocalAgentRunner(spawn_fn=fake_spawn),
        version_probe=lambda _path, _args: "codex 1.0",
    )

    with patch("skillhub_eval.execution.detection.resolve_agent_binary", return_value="/bin/codex"), \
         patch("skillhub_eval.execution.detection._config_dir_present", return_value=True):
        result = runner.run(skill, runtime_id="codex", model_id="default", now=datetime(2026, 7, 5, tzinfo=UTC))

    assert result.status == "passed"
    cached = repo.get_runtime_preflight(
        runtime_id="codex",
        model_id="default",
        skill_fingerprint=result.skill_fingerprint,
    )
    assert cached["status"] == "passed"
    assert cached["fingerprint"] == result.fingerprint
    assert cached["evidence"]["strategy"] in {"native", "prompt"}


def test_preflight_fails_when_entrypoint_evidence_missing(tmp_path):
    skill = _skill(tmp_path)
    lines = [
        json.dumps({"type": "tool_result", "stdout": "other.py", "exit_code": 0}),
        json.dumps({"type": "result", "duration_ms": 3}),
    ]

    def fake_spawn(args, **kwargs):
        return _FakeProcess(returncode=0, stdout_lines=[line + "\n" for line in lines])

    runner = PreflightRunner(
        repo=_repo(tmp_path),
        runner=LocalAgentRunner(spawn_fn=fake_spawn),
        version_probe=lambda _path, _args: "codex 1.0",
    )

    with patch("skillhub_eval.execution.detection.resolve_agent_binary", return_value="/bin/codex"), \
         patch("skillhub_eval.execution.detection._config_dir_present", return_value=True):
        result = runner.run(skill, runtime_id="codex")

    assert result.status == "failed"
    assert result.failure_reason == "runtime_missing_entrypoint_evidence"


def test_preflight_blocks_when_cli_missing(tmp_path):
    runner = PreflightRunner(repo=_repo(tmp_path), version_probe=lambda _path, _args: None)

    with patch("skillhub_eval.execution.detection.resolve_agent_binary", return_value=None):
        result = runner.run(_skill(tmp_path), runtime_id="codex")

    assert result.status == "blocked"
    assert result.failure_reason == "runtime_cli_missing"


def test_preflight_blocks_high_risk_without_safe_preflight_case(tmp_path):
    skill = _skill(tmp_path, risk="high")
    runner = PreflightRunner(
        repo=_repo(tmp_path),
        version_probe=lambda _path, _args: "codex 1.0",
    )

    with patch("skillhub_eval.execution.detection.resolve_agent_binary", return_value="/bin/codex"), \
         patch("skillhub_eval.execution.detection._config_dir_present", return_value=True):
        result = runner.run(skill, runtime_id="codex")

    assert result.status == "blocked"
    assert result.failure_reason == "runtime_safe_preflight_required"


def test_preflight_cache_invalidates_when_skill_changes(tmp_path):
    skill = _skill(tmp_path)
    lines = [
        json.dumps({"type": "tool_result", "stdout": "scripts/run.py", "exit_code": 0}),
        json.dumps({"type": "result", "duration_ms": 3}),
    ]

    def fake_spawn(args, **kwargs):
        return _FakeProcess(returncode=0, stdout_lines=[line + "\n" for line in lines])

    repo = _repo(tmp_path)
    runner = PreflightRunner(
        repo=repo,
        runner=LocalAgentRunner(spawn_fn=fake_spawn),
        version_probe=lambda _path, _args: "codex 1.0",
    )

    with patch("skillhub_eval.execution.detection.resolve_agent_binary", return_value="/bin/codex"), \
         patch("skillhub_eval.execution.detection._config_dir_present", return_value=True):
        result = runner.run(skill, runtime_id="codex", now=datetime(2026, 7, 5, tzinfo=UTC))
        assert runner.check_cached(skill, runtime_id="codex", now=datetime(2026, 7, 5, 1, tzinfo=UTC))

    (skill / "SKILL.md").write_text((skill / "SKILL.md").read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")

    with patch("skillhub_eval.execution.detection.resolve_agent_binary", return_value="/bin/codex"), \
         patch("skillhub_eval.execution.detection._config_dir_present", return_value=True):
        assert runner.check_cached(skill, runtime_id="codex", now=datetime(2026, 7, 5, 1, tzinfo=UTC)) is None
    assert result.skill_fingerprint


def test_preflight_cache_invalidates_when_runtime_fingerprint_changes(tmp_path):
    skill = _skill(tmp_path)
    lines = [
        json.dumps({"type": "tool_result", "stdout": "scripts/run.py", "exit_code": 0}),
        json.dumps({"type": "result", "duration_ms": 3}),
    ]

    def fake_spawn(args, **kwargs):
        return _FakeProcess(returncode=0, stdout_lines=[line + "\n" for line in lines])

    repo = _repo(tmp_path)
    runner = PreflightRunner(
        repo=repo,
        runner=LocalAgentRunner(spawn_fn=fake_spawn),
        version_probe=lambda _path, _args: "codex 1.0",
    )

    with patch("skillhub_eval.execution.detection.resolve_agent_binary", return_value="/bin/codex"), \
         patch("skillhub_eval.execution.detection._config_dir_present", return_value=True):
        runner.run(skill, runtime_id="codex", now=datetime(2026, 7, 5, tzinfo=UTC))
        assert runner.check_cached(skill, runtime_id="codex", now=datetime(2026, 7, 5, 1, tzinfo=UTC))

    changed_runner = PreflightRunner(
        repo=repo,
        runner=LocalAgentRunner(spawn_fn=fake_spawn),
        version_probe=lambda _path, _args: "codex 2.0",
    )
    with patch("skillhub_eval.execution.detection.resolve_agent_binary", return_value="/bin/codex"), \
         patch("skillhub_eval.execution.detection._config_dir_present", return_value=True):
        assert changed_runner.check_cached(skill, runtime_id="codex", now=datetime(2026, 7, 5, 1, tzinfo=UTC)) is None
