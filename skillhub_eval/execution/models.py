"""Hybrid model discovery: generic model_probe + fallback + custom retention (D3/G4)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

from skillhub_eval.execution.agent_registry import AgentDef, DEFAULT_MODEL_ID
from skillhub_eval.execution.detection import resolve_agent_binary
from skillhub_eval.settings import settings


@dataclass(frozen=True)
class ModelDiscovery:
    models: list[dict] = field(default_factory=list)  # {id,label,source}
    models_source: str = "none"  # "live" | "fallback" | "none"


def _fallback_models(agent: AgentDef) -> list[dict]:
    return [{"id": m.id, "label": m.label, "source": "fallback"} for m in agent.fallback_models]


def _run_probe(agent: AgentDef) -> str | None:
    """Run `<bin> <model_probe...>` and return stdout, or None on failure."""
    if not agent.model_probe:
        return None
    bin_path = resolve_agent_binary(agent)
    if not bin_path:
        return None
    try:
        proc = subprocess.run(
            [bin_path, *agent.model_probe],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=float(settings.model_discovery_timeout_s), check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _parse_model_lines(stdout: str) -> list[str]:
    ids: list[str] = []
    for raw in stdout.splitlines():
        line = raw.strip()
        if line and not line.startswith(("=", "-", "#")):
            ids.append(line)
    return ids


def discover_models(agent: AgentDef, *, stored_model: str | None = None) -> ModelDiscovery:
    live_ids = _parse_model_lines(_run_probe(agent) or "") if agent.model_probe else []
    if live_ids:
        models = [{"id": DEFAULT_MODEL_ID, "label": "默认模型", "source": "live"}]
        models += [{"id": mid, "label": mid, "source": "live"} for mid in live_ids]
        source = "live"
    else:
        models = _fallback_models(agent)
        source = "fallback" if agent.fallback_models else "none"

    sm = (stored_model or "").strip()
    if sm and sm != DEFAULT_MODEL_ID and sm not in {m["id"] for m in models}:
        models = [*models, {"id": sm, "label": sm, "source": "stale" if source == "live" else "custom"}]

    return ModelDiscovery(models=models, models_source=source)
