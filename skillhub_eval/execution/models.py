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


def _run_probe(agent: AgentDef, probe: tuple[str, ...] | None = None) -> str | None:
    """Run `<bin> <model_probe...>` and return stdout, or None on failure."""
    argv = probe or agent.model_probe
    if not argv:
        return None
    bin_path = resolve_agent_binary(agent)
    if not bin_path:
        return None
    try:
        proc = subprocess.run(
            [bin_path, *argv],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=float(settings.model_discovery_timeout_s), check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _parse_model_lines(stdout: str) -> list[tuple[str, str]]:
    """Parse probe stdout into (model_id, label) pairs.

    Supports plain one-id-per-line (trae) and ``id - Label`` rows (cursor-agent).
    """
    entries: list[tuple[str, str]] = []
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        lower = line.lower()
        if any(token in lower for token in ("no models", "sign in", "login", "not logged", "unauth")):
            continue
        if lower == "available models" or lower.startswith("tip:"):
            continue
        if line.startswith(("=", "#")):
            continue
        if " - " in line:
            model_id, _, label = line.partition(" - ")
            model_id = model_id.strip()
            label = label.strip()
            if model_id and not model_id.startswith("-"):
                entries.append((model_id, label or model_id))
            continue
        if line.startswith("-"):
            continue
        if any(ch.isspace() for ch in line):
            continue
        entries.append((line, line))
    return entries


def discover_models(agent: AgentDef, *, stored_model: str | None = None) -> ModelDiscovery:
    parsed: list[tuple[str, str]] = []
    probes = tuple(p for p in (agent.model_probe, *agent.fallback_model_probes) if p)
    for probe in probes:
        parsed = _parse_model_lines(_run_probe(agent, probe) or "")
        if parsed:
            break
    if parsed:
        models = [{"id": DEFAULT_MODEL_ID, "label": "默认模型", "source": "live"}]
        models += [{"id": mid, "label": lbl, "source": "live"} for mid, lbl in parsed]
        source = "live"
    else:
        models = _fallback_models(agent)
        source = "fallback" if agent.fallback_models else "none"

    sm = (stored_model or "").strip()
    if sm and sm != DEFAULT_MODEL_ID and sm not in {m["id"] for m in models}:
        models = [*models, {"id": sm, "label": sm, "source": "stale" if source == "live" else "custom"}]

    return ModelDiscovery(models=models, models_source=source)
