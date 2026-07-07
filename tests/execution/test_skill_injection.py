from pathlib import Path

import pytest

from skillhub_eval.core.schemas.report import ExecResult
from skillhub_eval.execution.consent import clear_exec_consent, grant_exec_consent
from skillhub_eval.execution.local_agent_source import LocalAgentSource
from skillhub_eval.execution.runtime_defs import (
    PromptTransport,
    RuntimeDef,
    RuntimeLaunch,
    RuntimeModels,
    RuntimeSkillInjection,
    SkillInjectionStrategy,
    get_runtime_def,
)
from skillhub_eval.execution.skill_injection import (
    SkillInjectionError,
    prepare_skill_injection,
)
from skillhub_eval.execution.agent_registry import ModelOption


def _runtime(strategy: SkillInjectionStrategy, *, argv: bool = False) -> RuntimeDef:
    return RuntimeDef(
        runtime_id="test-runtime",
        label="Test Runtime",
        binary=get_runtime_def("codex").binary,
        models=RuntimeModels(fallback_models=(ModelOption("default", "Default"),)),
        launch=RuntimeLaunch(prompt_transport=PromptTransport.ARGV if argv else PromptTransport.STDIN),
        skill_injection=RuntimeSkillInjection(strategy),
    )


def test_prepare_uses_native_when_bundle_exposes_native_ref(tmp_path):
    runtime = _runtime(SkillInjectionStrategy.NATIVE)

    prepared = prepare_skill_injection(
        runtime,
        case={"id": "h01", "user_intent": "run"},
        bundle={"skill_id": "s", "native_skill_ref": "s"},
        skill_dir=tmp_path,
    )

    assert prepared.strategy == SkillInjectionStrategy.NATIVE
    assert "skill_id: s" in prepared.prompt


def test_prepare_falls_back_to_prompt_when_native_unavailable(tmp_path):
    runtime = _runtime(SkillInjectionStrategy.NATIVE)

    prepared = prepare_skill_injection(
        runtime,
        case={"id": "h01", "user_intent": "run"},
        bundle={"skill_id": "s"},
        skill_dir=tmp_path,
    )

    assert prepared.strategy == SkillInjectionStrategy.PROMPT
    assert "native injection unavailable" in prepared.notes[0]


def test_prepare_uses_file_placed_when_skill_md_exists(tmp_path):
    (tmp_path / "SKILL.md").write_text("---\nname: s\n---\n", encoding="utf-8")
    runtime = _runtime(SkillInjectionStrategy.FILE_PLACED)

    prepared = prepare_skill_injection(
        runtime,
        case={"id": "h01", "user_intent": "run"},
        bundle={"skill_id": "s"},
        skill_dir=tmp_path,
    )

    assert prepared.strategy == SkillInjectionStrategy.FILE_PLACED
    assert prepared.skill_dir == tmp_path.resolve()


def test_prepare_prompt_is_guaranteed_fallback(tmp_path):
    (tmp_path / "SKILL.md").write_text("# Demo Skill\nFollow this unique rule.\n", encoding="utf-8")
    runtime = _runtime(SkillInjectionStrategy.NATIVE)

    prepared = prepare_skill_injection(
        runtime,
        case={"id": "h01", "user_intent": "run"},
        bundle={"skill_id": "s"},
        skill_dir=tmp_path,
    )

    assert prepared.strategy == SkillInjectionStrategy.PROMPT
    assert "native injection unavailable" in prepared.notes[0]
    assert "Prompt-injected Skill" in prepared.prompt
    assert "Follow this unique rule." in prepared.prompt


def test_prompt_strategy_injects_skill_md_content(tmp_path):
    (tmp_path / "SKILL.md").write_text("# Demo Skill\nReturn alpha.\n", encoding="utf-8")
    runtime = _runtime(SkillInjectionStrategy.PROMPT)

    prepared = prepare_skill_injection(
        runtime,
        case={"id": "h01", "user_intent": "run"},
        bundle={"skill_id": "s"},
        skill_dir=tmp_path,
    )

    assert prepared.strategy == SkillInjectionStrategy.PROMPT
    assert "Return alpha." in prepared.prompt


def test_prepare_blocks_too_large_prompt_for_argv_runtime(tmp_path):
    runtime = _runtime(SkillInjectionStrategy.PROMPT, argv=True)

    with pytest.raises(SkillInjectionError) as exc:
        prepare_skill_injection(
            runtime,
            case={"id": "h01", "user_intent": "x" * 30},
            bundle={"skill_id": "s"},
            skill_dir=tmp_path,
            argv_prompt_limit_chars=20,
        )

    assert exc.value.reason_code == "local_runtime_prompt_too_large"
    assert "command-line argv" in exc.value.message


def test_local_agent_source_returns_prompt_too_large_before_spawn(tmp_path, monkeypatch):
    clear_exec_consent()
    grant_exec_consent("s")

    class _TraeAdapter:
        agent_id = "trae"
        model = None

        def detect(self):
            return True

        def build_args(self, *, cwd: str | None = None, hardened: bool = False):
            return ["trae-cli"]

        def parse_stream(self, lines: list[str]):
            raise AssertionError("should not spawn")

    class _Runner:
        def run(self, *args, **kwargs):
            raise AssertionError("should not spawn")

        def is_run_complete(self, outcome):
            return True

    class _Workspace:
        def acquire(self, bundle_path, case_id):
            root = Path(bundle_path)
            root.mkdir(exist_ok=True)
            (root / "SKILL.md").write_text("---\nname: s\n---\n", encoding="utf-8")
            return root

        def release(self, run_dir):
            pass

    monkeypatch.setattr("skillhub_eval.execution.skill_injection.ARGV_PROMPT_LIMIT_CHARS", 20)
    monkeypatch.setattr("skillhub_eval.execution.local_agent_source.prepare_skill_injection", lambda *a, **kw: (_ for _ in ()).throw(SkillInjectionError("local_runtime_prompt_too_large", "too large")))

    src = LocalAgentSource(runner=_Runner(), workspace=_Workspace(), adapter=_TraeAdapter())
    result = src.get_actual_output(
        str(tmp_path / "skill"),
        "h01",
        case={"id": "h01", "user_intent": "x" * 30},
        bundle={"skill_id": "s"},
    )

    assert isinstance(result, ExecResult)
    assert result.status == "incomplete"
    assert result.degrade_reason == "local_runtime_prompt_too_large"
    assert result.stderr_excerpt == "too large"
    clear_exec_consent()


def test_local_agent_source_rejects_adapter_without_runtime_definition(tmp_path):
    clear_exec_consent()
    grant_exec_consent("s")

    class _UnknownAdapter:
        agent_id = "future-agent"

        def detect(self):
            return True

        def build_args(self, *, cwd: str | None = None, hardened: bool = False):
            return ["future-agent"]

        def parse_stream(self, lines: list[str]):
            raise AssertionError("should not spawn")

    class _Runner:
        def run(self, *args, **kwargs):
            raise AssertionError("should not spawn")

        def is_run_complete(self, outcome):
            return True

    class _Workspace:
        def acquire(self, bundle_path, case_id):
            return tmp_path

        def release(self, run_dir):
            pass

    src = LocalAgentSource(runner=_Runner(), workspace=_Workspace(), adapter=_UnknownAdapter())
    result = src.get_actual_output(
        str(tmp_path),
        "h01",
        case={"id": "h01", "user_intent": "run"},
        bundle={"skill_id": "s"},
    )

    assert result.status == "incomplete"
    assert result.degrade_reason == "local_runtime_definition_missing"
    clear_exec_consent()
