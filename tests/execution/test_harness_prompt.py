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


def test_preflight_harness_prompt_does_not_run_formal_skill_flow():
    case = {
        "id": "runtime_preflight_01",
        "type": "preflight",
        "safe_preflight": True,
        "user_intent": "检查本地执行环境",
        "input_template": "请仅进行本地执行环境检查，返回最小结构化结果。",
    }
    bundle = {"skill_id": "stock-radar", "has_scripts": False}

    prompt = build_harness_prompt(case, bundle)

    assert "SKILL.md" in prompt
    assert "本地执行环境" in prompt
    assert "按技能说明完成本 case" not in prompt
    assert "正式业务流程" in prompt
    assert "取数" in prompt
    assert "诊断" in prompt


def test_preflight_harness_prompt_with_entrypoint_checks_visibility_only():
    case = {
        "id": "runtime_preflight_01",
        "type": "preflight",
        "safe_preflight": True,
        "user_intent": "检查本地执行环境",
    }
    bundle = {
        "skill_id": "stock-radar",
        "entrypoint": "scripts/run.py",
        "has_scripts": True,
    }

    prompt = build_harness_prompt(case, bundle)

    assert "scripts/run.py" in prompt
    assert "入口文件" in prompt
    assert "完整 pipeline" in prompt or "pipeline" in prompt
    assert "必须调用声明的 entrypoint 处理本输入" not in prompt
