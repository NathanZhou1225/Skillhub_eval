from skillhub_eval.execution.harness_prompt import build_harness_prompt


def test_harness_prompt_forces_skill_and_entrypoint():
    case = {"id": "h01", "user_intent": "诊断 600519", "input_template": "600519"}
    bundle = {
        "skill_id": "stock-radar",
        "entrypoint": "scripts/run.py",
        "has_scripts": True,
    }
    prompt = build_harness_prompt(case, bundle)
    assert "600519" in prompt
    assert "scripts/run.py" in prompt
    assert "必须" in prompt or "MUST" in prompt.upper()
    assert "fenced JSON" in prompt or "```json" in prompt


def test_harness_prompt_without_scripts_omits_entrypoint_block():
    case = {"id": "h01", "user_intent": "hello"}
    bundle = {"skill_id": "prompt-only", "has_scripts": False}
    prompt = build_harness_prompt(case, bundle)
    assert "entrypoint" not in prompt.lower() or "scripts/" not in prompt
