"""Declarative local-agent registry and model preferences."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from skillhub_eval.execution.runner import AgentAdapter

DEFAULT_MODEL_ID = "default"


@dataclass(frozen=True)
class ModelOption:
    model_id: str
    label: str

    @property
    def id(self) -> str:
        return self.model_id

    @property
    def model(self) -> str:
        return self.model_id


@dataclass(frozen=True)
class AgentDef:
    agent_id: str
    label: str
    adapter_factory: Callable[..., AgentAdapter] | None
    fallback_models: tuple[ModelOption, ...]
    primary_bin: str | None = None
    binary_aliases: tuple[str, ...] = ()
    supports_hardened_redline: bool = False
    aliases: tuple[str, ...] = ()

    @property
    def id(self) -> str:
        return self.agent_id

    @property
    def bin(self) -> str:
        return self.primary_bin or self.agent_id

    @property
    def binary_names(self) -> tuple[str, ...]:
        return (self.bin, *self.binary_aliases)


def _claude_adapter(**kwargs) -> AgentAdapter:
    from skillhub_eval.execution.adapters.claude import ClaudeAdapter

    return ClaudeAdapter(**kwargs)


def _codex_adapter(**kwargs) -> AgentAdapter:
    from skillhub_eval.execution.adapters.codex import CodexAdapter

    return CodexAdapter(**kwargs)


def _cursor_agent_adapter(**kwargs) -> AgentAdapter:
    from skillhub_eval.execution.adapters.cursor_agent import CursorAgentAdapter

    return CursorAgentAdapter(**kwargs)


def _trae_adapter(**kwargs) -> AgentAdapter:
    from skillhub_eval.execution.adapters.trae import TraeAdapter

    return TraeAdapter(**kwargs)


def _antigravity_adapter(**kwargs) -> AgentAdapter:
    from skillhub_eval.execution.adapters.antigravity import AntigravityAdapter

    return AntigravityAdapter(**kwargs)


_DEFAULT_MODEL = ModelOption(DEFAULT_MODEL_ID, "Default")

_CATALOG: tuple[AgentDef, ...] = (
    AgentDef(
        agent_id="claude",
        label="Claude",
        adapter_factory=_claude_adapter,
        fallback_models=(_DEFAULT_MODEL,),
    ),
    AgentDef(
        agent_id="codex",
        label="Codex",
        adapter_factory=_codex_adapter,
        fallback_models=(_DEFAULT_MODEL, ModelOption("gpt-5-codex", "GPT-5 Codex")),
        supports_hardened_redline=True,
    ),
    AgentDef(
        agent_id="cursor-agent",
        label="Cursor Agent",
        adapter_factory=_cursor_agent_adapter,
        fallback_models=(_DEFAULT_MODEL, ModelOption("gpt-5", "GPT-5")),
        aliases=("cursor_agent",),
    ),
    AgentDef(
        agent_id="trae",
        label="Trae",
        adapter_factory=_trae_adapter,
        fallback_models=(_DEFAULT_MODEL,),
        primary_bin="traecli",
        binary_aliases=("trae",),
    ),
    AgentDef(
        agent_id="antigravity",
        label="Antigravity",
        adapter_factory=_antigravity_adapter,
        fallback_models=(_DEFAULT_MODEL,),
        primary_bin="agy",
    ),
)


def get_agent_catalog() -> list[AgentDef]:
    return list(_CATALOG)


def get_agent_def(agent_id: str) -> AgentDef | None:
    normalized = _normalize_agent_id(agent_id)
    for agent in _CATALOG:
        if agent.agent_id == normalized:
            return agent
    return None


def fallback_models_for(agent_id: str) -> list[ModelOption]:
    agent = get_agent_def(agent_id)
    return list(agent.fallback_models) if agent else []


def resolve_adapter(agent_id: str, model: str | None = None) -> AgentAdapter | None:
    agent = get_agent_def(agent_id)
    if agent is None or agent.adapter_factory is None:
        return None
    normalized_model = _normalize_model(model)
    return agent.adapter_factory(model=normalized_model)


def _normalize_agent_id(agent_id: str) -> str:
    raw = (agent_id or "").strip()
    for agent in _CATALOG:
        if raw == agent.agent_id or raw in agent.aliases:
            return agent.agent_id
    return raw


def _normalize_model(model: str | None) -> str | None:
    raw = (model or "").strip()
    if not raw or raw == DEFAULT_MODEL_ID:
        return None
    return raw
