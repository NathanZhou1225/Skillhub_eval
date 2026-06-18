from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.core.schemas import BundleState, EvaluationMode
from skillhub_eval.core.schemas.report import ExecResult


def test_build_prompt_execution_mode_contains_execution_rubric():
    engine = EvaluationEngine(repo=None, ds_provider=None, wb_provider=None)
    engine._case_exec_results = {
        "h01": ExecResult(
            actual_output={"ok": True},
            source="local_agent",
            status="ok",
        ),
    }
    prompt = engine._build_prompt(
        {"id": "h01", "type": "happy_path", "user_intent": "test"},
        {"skill_id": "s", "skill_md_text": "# Skill", "bundle_path": "/tmp"},
        BundleState.confirmed,
        EvaluationMode.capability_full,
    )
    assert "真实执行产出" in prompt
    assert "prompt_mode: execution" in prompt
    assert "标准输出（sample_io）" not in prompt
