"""Runtime-specific skill injection selection for local CLI execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from skillhub_eval.execution.harness_prompt import build_harness_prompt
from skillhub_eval.execution.runtime_defs import (
    PromptTransport,
    RuntimeDef,
    SkillInjectionStrategy,
)

WINDOWS_COMMAND_LINE_LIMIT_CHARS = 32767
ARGV_PROMPT_LIMIT_CHARS = 24000


@dataclass(frozen=True)
class SkillInjectionError(Exception):
    reason_code: str
    message: str
    strategy: SkillInjectionStrategy | None = None

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class PreparedSkillInjection:
    strategy: SkillInjectionStrategy
    prompt: str
    skill_dir: Path | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


PromptBuilder = Callable[[dict, dict], str]


def prepare_skill_injection(
    runtime: RuntimeDef,
    *,
    case: dict,
    bundle: dict,
    skill_dir: str | Path | None = None,
    prompt_builder: PromptBuilder = build_harness_prompt,
    argv_prompt_limit_chars: int = ARGV_PROMPT_LIMIT_CHARS,
) -> PreparedSkillInjection:
    """Select the first usable injection strategy for a runtime and skill.

    Today the formal local runner still sends a harness prompt for every
    runtime. Native/file-placed injection only changes how the skill is made
    available to the CLI; prompt injection remains the guaranteed fallback.
    """
    skill_root = Path(skill_dir).resolve() if skill_dir is not None else None
    harness_prompt = prompt_builder(case, bundle)

    _guard_prompt_transport(
        runtime,
        harness_prompt,
        argv_prompt_limit_chars=argv_prompt_limit_chars,
    )

    notes: list[str] = []
    for strategy in runtime.skill_injection.ordered():
        if strategy == SkillInjectionStrategy.NATIVE:
            if _native_injection_available(bundle):
                return PreparedSkillInjection(strategy=strategy, prompt=harness_prompt, skill_dir=skill_root)
            notes.append("native injection unavailable for this skill bundle")
            continue
        if strategy == SkillInjectionStrategy.FILE_PLACED:
            if _file_placed_injection_available(skill_root):
                return PreparedSkillInjection(strategy=strategy, prompt=harness_prompt, skill_dir=skill_root)
            notes.append("SKILL.md was not found in the prepared workspace")
            continue
        if strategy == SkillInjectionStrategy.PROMPT:
            prompt = _inject_skill_content_into_prompt(harness_prompt, skill_root)
            _guard_prompt_transport(
                runtime,
                prompt,
                argv_prompt_limit_chars=argv_prompt_limit_chars,
            )
            return PreparedSkillInjection(
                strategy=strategy,
                prompt=prompt,
                skill_dir=skill_root,
                notes=tuple(notes),
            )

    raise SkillInjectionError(
        reason_code="local_runtime_skill_injection_unavailable",
        message=f"{runtime.label} has no usable skill injection strategy for this bundle.",
    )


def _native_injection_available(bundle: dict) -> bool:
    return bool(bundle.get("native_skill_ref") or bundle.get("native_injection_available"))


def _file_placed_injection_available(skill_dir: Path | None) -> bool:
    return bool(skill_dir and (skill_dir / "SKILL.md").is_file())


def _inject_skill_content_into_prompt(harness_prompt: str, skill_dir: Path | None) -> str:
    if skill_dir is None:
        return harness_prompt
    skill_md = _read_text_if_small(skill_dir / "SKILL.md")
    if not skill_md:
        return harness_prompt
    parts = [
        harness_prompt,
        "",
        "【Prompt-injected Skill】",
        "下面是当前 skill 的 SKILL.md 内容；即使 CLI 没有原生 skill 加载能力，也必须按它执行：",
        "```markdown",
        skill_md.rstrip(),
        "```",
    ]
    return "\n".join(parts)


def _read_text_if_small(path: Path, max_chars: int = 20000) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[SKILL.md truncated for prompt injection]"
    return text


def _guard_prompt_transport(
    runtime: RuntimeDef,
    prompt: str,
    *,
    argv_prompt_limit_chars: int,
) -> None:
    if runtime.launch.prompt_transport != PromptTransport.ARGV:
        return
    if len(prompt) <= argv_prompt_limit_chars:
        return
    raise SkillInjectionError(
        reason_code="local_runtime_prompt_too_large",
        message=(
            f"{runtime.label} receives prompts through command-line argv, but this harness prompt "
            f"is {len(prompt)} characters, above the conservative {argv_prompt_limit_chars} "
            "character safety limit. Use a stdin/prompt-file runtime or reduce the case prompt size."
        ),
        strategy=SkillInjectionStrategy.PROMPT,
    )
