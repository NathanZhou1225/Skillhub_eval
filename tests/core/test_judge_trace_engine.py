"""Wave 5.4 — engine prompt v0.5 + judge trace persistence."""

from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.core.schemas import BundleState, EvaluationMode
from skillhub_eval.persistence.sqlite import SqliteRepository


def test_build_prompt_v0_5_includes_analysis_fields():
    engine = EvaluationEngine(
        repo=SqliteRepository(":memory:"),
        ds_provider=None,
        wb_provider=None,
    )
    prompt = engine._build_prompt(
        case={"id": "c1", "type": "happy_path", "user_intent": "test"},
        bundle={"skill_id": "skill.x", "skill_md_text": "# Skill"},
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
    )
    assert "review-agent-v0.5" in prompt
    assert "analysis" in prompt
    assert "evidence_quotes" in prompt
    assert "deductions" in prompt
    assert "先写每维 analysis" in prompt


def test_judge_case_saves_judge_trace(tmp_path):
    repo = SqliteRepository(str(tmp_path / "judge.db"))
    repo.init_db()
    run_id = repo.create_run(
        skill_id="skill.t",
        skill_bundle_path="/b",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )

    class _Provider:
        async def judge(self, prompt: str) -> dict:
            return {
                "sub_scores": {
                    "instruction_following": {"score": 80, "pass": True, "reason": "ok"},
                    "output_compliance": {"score": 80, "pass": True, "reason": "ok"},
                    "business_resolution": {"score": 80, "pass": True, "reason": "ok"},
                },
                "confidence": "high",
                "dimension_notes": "good",
            }

    engine = EvaluationEngine(repo=repo, ds_provider=_Provider(), wb_provider=_Provider())
    import asyncio

    votes = asyncio.run(
        engine._judge_case(
            run_id,
            {"id": "case-1", "type": "happy_path"},
            {"skill_id": "skill.t", "skill_md_text": "body"},
            BundleState.confirmed,
            EvaluationMode.capability_full,
        )
    )
    assert len(votes) == 2
    assert repo.has_judge_traces(run_id)
    traces = repo.get_judge_traces(run_id)
    assert traces[0]["case_id"] == "case-1"
    assert "review-agent-v0.5" in traces[0]["prompt_text"]
