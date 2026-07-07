"""Declarative local CLI runtime definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from skillhub_eval.execution.agent_registry import DEFAULT_MODEL_ID, ModelOption


class PromptTransport(StrEnum):
    STDIN = "stdin"
    ARGV = "argv"
    PROMPT_FILE = "prompt_file"


class SkillInjectionStrategy(StrEnum):
    NATIVE = "native"
    FILE_PLACED = "file_placed"
    PROMPT = "prompt"


class StreamFormat(StrEnum):
    STREAM_JSON = "stream-json"
    ACP_JSON_RPC = "acp-json-rpc"


@dataclass(frozen=True)
class RuntimeBinary:
    primary: str
    aliases: tuple[str, ...] = ()
    install_dir_globs: tuple[str, ...] = ()
    version_args: tuple[str, ...] = ("--version",)

    @property
    def names(self) -> tuple[str, ...]:
        return (self.primary, *self.aliases)


@dataclass(frozen=True)
class RuntimeModels:
    fallback_models: tuple[ModelOption, ...]
    model_probe: tuple[str, ...] | None = None
    fallback_model_probes: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class RuntimeLaunch:
    prompt_transport: PromptTransport = PromptTransport.STDIN
    stream_format: StreamFormat = StreamFormat.STREAM_JSON
    supports_hardened_redline: bool = False


@dataclass(frozen=True)
class RuntimeSkillInjection:
    preferred: SkillInjectionStrategy
    fallbacks: tuple[SkillInjectionStrategy, ...] = (SkillInjectionStrategy.PROMPT,)

    def ordered(self) -> tuple[SkillInjectionStrategy, ...]:
        seen: set[SkillInjectionStrategy] = set()
        ordered: list[SkillInjectionStrategy] = []
        for item in (self.preferred, *self.fallbacks, SkillInjectionStrategy.PROMPT):
            if item not in seen:
                ordered.append(item)
                seen.add(item)
        return tuple(ordered)


@dataclass(frozen=True)
class RuntimePreflightProfile:
    fixture_id: str = "exec-fixture-minimal"
    requires_entrypoint_evidence: bool = True
    requires_structured_output: bool = True


@dataclass(frozen=True)
class RuntimeDef:
    runtime_id: str
    label: str
    binary: RuntimeBinary
    models: RuntimeModels
    launch: RuntimeLaunch = field(default_factory=RuntimeLaunch)
    skill_injection: RuntimeSkillInjection = field(
        default_factory=lambda: RuntimeSkillInjection(SkillInjectionStrategy.PROMPT)
    )
    preflight: RuntimePreflightProfile = field(default_factory=RuntimePreflightProfile)
    config_dirs: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    install_docs_url: str | None = None
    install_command: str | None = None


_DEFAULT_MODEL = ModelOption(DEFAULT_MODEL_ID, "Default")


_RUNTIMES: tuple[RuntimeDef, ...] = (
    RuntimeDef(
        runtime_id="claude",
        label="Claude",
        binary=RuntimeBinary(primary="claude"),
        models=RuntimeModels(fallback_models=(_DEFAULT_MODEL,)),
        config_dirs=(".claude",),
        skill_injection=RuntimeSkillInjection(SkillInjectionStrategy.NATIVE),
    ),
    RuntimeDef(
        runtime_id="codex",
        label="Codex",
        binary=RuntimeBinary(
            primary="codex",
            install_dir_globs=("OpenAI/Codex/bin/*",),
        ),
        models=RuntimeModels(
            fallback_models=(
                _DEFAULT_MODEL,
                ModelOption("gpt-5-codex", "GPT-5 Codex"),
            )
        ),
        config_dirs=(".codex",),
        launch=RuntimeLaunch(supports_hardened_redline=True),
        skill_injection=RuntimeSkillInjection(SkillInjectionStrategy.NATIVE),
    ),
    RuntimeDef(
        runtime_id="cursor-agent",
        label="Cursor Agent",
        binary=RuntimeBinary(
            primary="cursor-agent",
            install_dir_globs=("cursor-agent/versions/*",),
        ),
        models=RuntimeModels(
            fallback_models=(_DEFAULT_MODEL, ModelOption("gpt-5", "GPT-5")),
            model_probe=("models",),
            fallback_model_probes=(("--list-models",),),
        ),
        config_dirs=(".cursor",),
        aliases=("cursor_agent",),
        skill_injection=RuntimeSkillInjection(SkillInjectionStrategy.FILE_PLACED),
    ),
    RuntimeDef(
        runtime_id="trae",
        label="Trae",
        binary=RuntimeBinary(
            primary="trae-cli",
            aliases=("traecli", "trae-agent", "ta"),
            install_dir_globs=("trae-cli/bin",),
        ),
        models=RuntimeModels(
            fallback_models=(_DEFAULT_MODEL,),
            model_probe=("models",),
        ),
        launch=RuntimeLaunch(prompt_transport=PromptTransport.ARGV),
        config_dirs=(".trae",),
        skill_injection=RuntimeSkillInjection(SkillInjectionStrategy.PROMPT),
    ),
    RuntimeDef(
        runtime_id="antigravity",
        label="Antigravity",
        binary=RuntimeBinary(primary="agy"),
        models=RuntimeModels(fallback_models=(_DEFAULT_MODEL,)),
        config_dirs=(".gemini/antigravity-cli",),
        skill_injection=RuntimeSkillInjection(SkillInjectionStrategy.PROMPT),
    ),
)


def get_runtime_catalog() -> list[RuntimeDef]:
    return list(_RUNTIMES)


def get_runtime_def(runtime_id: str) -> RuntimeDef | None:
    raw = (runtime_id or "").strip()
    for runtime in _RUNTIMES:
        if (
            raw == runtime.runtime_id
            or raw in runtime.aliases
            or raw == runtime.binary.primary
            or raw in runtime.binary.aliases
        ):
            return runtime
    return None
