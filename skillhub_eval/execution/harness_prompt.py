"""Harness prompt for forced local skill execution."""

from __future__ import annotations


def build_harness_prompt(case: dict, bundle: dict) -> str:
    """Build a prompt that forces the agent to use the skill and call entrypoint."""
    case_id = case.get("id", "?")
    user_intent = case.get("user_intent", "")
    input_template = case.get("input_template", "")
    skill_id = bundle.get("skill_id", "?")
    entrypoint = bundle.get("entrypoint")
    has_scripts = bundle.get("has_scripts")

    lines = [
        "你是 SkillHub 评估执行器。你必须使用当前工作目录（cwd）中的 skill 完成本 case。",
        f"skill_id: {skill_id}",
        f"case_id: {case_id}",
        f"user_intent: {user_intent}",
    ]
    if input_template:
        lines.append(f"input_template: {input_template}")

    if has_scripts and entrypoint:
        lines.extend([
            "",
            "【强制要求】",
            f"- 必须阅读并遵循 SKILL.md",
            f"- 必须调用声明的 entrypoint 处理本输入：{entrypoint}",
            "- 禁止绕过 pipeline、禁止手编与 returns_schema 不符的结果",
            "- 你的 shell 已经处于正确的工作目录（cwd），直接用相对路径运行"
            f"（例如 {entrypoint}），不要先 cd 到绝对路径——本机路径含空格与中文，"
            "对绝对路径加引号后 cd 在 Windows cmd 下会报路径语法错误",
        ])
    else:
        lines.extend([
            "",
            "【要求】",
            "- 必须阅读并遵循 SKILL.md，按技能说明完成本 case",
        ])

    lines.extend([
        "",
        "完成后在回复末尾打印一个 fenced JSON 代码块（```json ... ```），",
        "内容为符合 returns_schema 的结构化产出。",
    ])
    return "\n".join(lines)
