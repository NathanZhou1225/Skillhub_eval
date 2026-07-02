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


def test_harness_prompt_tells_agent_not_to_cd_to_absolute_path():
    """Real-machine finding (2026-07-02, Trae/GLM-5.2): the local agent's shell
    already starts in the correct cwd, but without guidance the model tries
    `cd "<absolute path>"` first — on Windows, an absolute path containing both
    spaces and non-ASCII characters (this repo's path has both) breaks cmd.exe's
    nested-quote parsing ("The filename, directory name, or volume label syntax
    is incorrect."), burning the whole turn budget on retries before the
    entrypoint is ever invoked. Telling the model to use the relative path
    directly avoids the whole class of failure."""
    case = {"id": "h01", "user_intent": "run it"}
    bundle = {"skill_id": "exec.fixture.minimal", "entrypoint": "scripts/run.py", "has_scripts": True}
    prompt = build_harness_prompt(case, bundle)
    assert "已" in prompt and ("工作目录" in prompt or "cwd" in prompt.lower())
    assert "cd" in prompt.lower()
