from skillhub_eval.core.judge_prompt import build_case_judge_prompt
from skillhub_eval.core.schemas.report import ExecResult


def test_build_case_judge_prompt_uses_sample_io_loader():
    prompt = build_case_judge_prompt(
        case={"id": "h01", "type": "happy_path", "user_intent": "检查摘要"},
        bundle={
            "skill_id": "demo",
            "skill_md_text": "Skill body",
            "bundle_path": "/tmp/demo",
        },
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        exec_results={},
        actual_output_loader=lambda _bundle_path, _case_id, **_kwargs: {"ok": True},
    )

    assert "prompt_mode: sample_io" in prompt
    assert "【本 case 标准输出（sample_io）】" in prompt
    assert '"ok": true' in prompt


def test_build_case_judge_prompt_prefers_local_execution_output():
    prompt = build_case_judge_prompt(
        case={"id": "r01", "type": "refusal_case", "user_intent": "索要密钥"},
        bundle={
            "skill_id": "demo",
            "skill_md_text": "Skill body",
            "bundle_path": "/tmp/demo",
        },
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        exec_results={
            "r01": ExecResult(
                actual_output={"refused": True},
                source="local_agent",
                status="ok",
            )
        },
        actual_output_loader=lambda *_args, **_kwargs: {"sample": True},
    )

    assert "prompt_mode: execution" in prompt
    assert "【本 case 真实执行产出】" in prompt
    assert '"refused": true' in prompt
    assert '"sample": true' not in prompt
