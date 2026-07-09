"""Harness prompt for forced local skill execution."""

from __future__ import annotations


def _is_preflight_case(case: dict) -> bool:
    return bool(case.get("safe_preflight")) or case.get("type") == "preflight"


def build_harness_prompt(case: dict, bundle: dict) -> str:
    """Build a prompt that forces the agent to use the skill and call entrypoint."""
    case_id = case.get("id", "?")
    user_intent = case.get("user_intent", "")
    input_template = case.get("input_template", "")
    skill_id = bundle.get("skill_id", "?")
    entrypoint = bundle.get("entrypoint")
    has_scripts = bundle.get("has_scripts")

    if _is_preflight_case(case):
        lines = [
            "你是 SkillHub 本地执行环境检查器。你必须使用当前工作目录（cwd）中的 skill 做轻量 preflight。",
            f"skill_id: {skill_id}",
            f"case_id: {case_id}",
            f"user_intent: {user_intent}",
        ]
        if input_template:
            lines.append(f"input_template: {input_template}")

        lines.extend([
            "",
            "【preflight 专用要求】",
            "- 必须读取或确认 SKILL.md 可访问，但不要按 SKILL.md 执行正式业务流程",
            "- 只检查本地执行环境、当前工作目录、必要文件是否可见，并返回最小结构化结果",
            "- 禁止执行正式取数、诊断、投研分析、报告生成、外部业务查询或完整 pipeline",
        ])
        if has_scripts and entrypoint:
            lines.extend([
                f"- 声明入口文件：{entrypoint}",
                "- 只需通过轻量文件/路径检查证明入口文件存在或可见；不要调用入口处理业务输入",
                "- 如需使用 shell，请优先用相对路径检查入口文件，不要先 cd 到绝对路径",
            ])

        lines.extend([
            "",
            "完成后在回复末尾打印一个 fenced JSON 代码块（```json ... ```），",
            "内容至少包含 preflight、skill_readable，并在适用时包含 entrypoint_visible。",
        ])
        return "\n".join(lines)

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
