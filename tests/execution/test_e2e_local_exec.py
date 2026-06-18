"""E2E local agent runs against exec-fixture-minimal (manual / CI optional)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.execution.consent import grant_exec_consent
from skillhub_eval.execution.local_agent_source import LocalAgentSource
from skillhub_eval.settings import settings

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2] / "testskills" / "exec-fixture-minimal"
)

pytestmark = pytest.mark.requires_local_agent


@pytest.mark.parametrize("agent_id", ["claude", "codex", "cursor-agent"])
def test_e2e_local_agent_runs_fixture(agent_id, monkeypatch):
    monkeypatch.setattr(settings, "exec_agent", agent_id)
    bundle = ingest_bundle(str(FIXTURE_ROOT))
    grant_exec_consent(bundle["skill_id"])
    case = bundle["eval_cases"][0]
    src = LocalAgentSource()
    result = src.get_actual_output(
        str(FIXTURE_ROOT),
        case["id"],
        case=case,
        bundle=bundle,
    )
    if result.degrade_reason == "agent_unavailable":
        pytest.skip(f"{agent_id} CLI not available")
    assert result.source == "local_agent"
    assert result.status == "ok", result.degrade_reason
    assert result.actual_output is not None
