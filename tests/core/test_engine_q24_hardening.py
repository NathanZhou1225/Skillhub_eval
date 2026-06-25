"""Focused tests for Q-24/Q-25 hardening pass."""

import pytest

from skillhub_eval.core.schemas import BundleState, EvaluationMode
from skillhub_eval.core.schemas.report import ExecResult
from tests.core.test_engine import HighScoreProvider, make_confirmed_low_bundle, make_engine


class UsageTrackingProvider(HighScoreProvider):
    async def judge(self, prompt: str) -> dict:
        self.last_usage = {
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "total_tokens": 12,
        }
        return await super().judge(prompt)


@pytest.mark.asyncio
async def test_risk_review_logs_token_usage(tmp_path):
    bundle_path = make_confirmed_low_bundle(tmp_path / "bundle_risk_usage", n_cases=3)
    engine, repo = make_engine(
        tmp_path,
        ds_provider=UsageTrackingProvider(),
        wb_provider=UsageTrackingProvider(),
    )
    run_id = repo.create_run(
        skill_id="skill.test",
        skill_bundle_path=bundle_path,
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )
    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle_path,
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
    )
    stages = [
        event["payload"]["stage"]
        for event in repo.list_events(run_id, event_name="token_usage")
    ]
    assert "risk_review" in stages


def test_exec_agent_report_fields_prefers_case_results(tmp_path):
    engine, _repo = make_engine(tmp_path)
    engine._case_exec_results = {
        "c1": ExecResult(
            source="local_agent",
            agent_id="cursor-agent",
            agent_label="Cursor Agent",
            model_id="gpt-5",
            model_label="gpt-5",
            status="ok",
        ),
    }
    fields = engine._exec_agent_report_fields({"execution_source": "local"})
    assert fields["exec_agent_id"] == "cursor-agent"
    assert fields["exec_agent_label"] == "Cursor Agent"
    assert fields["exec_model_id"] == "gpt-5"
