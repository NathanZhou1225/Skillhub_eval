"""User-facing chat notices for formal evaluation stage transitions (Wave 5.5 / plan B)."""

from __future__ import annotations

from typing import Literal

from skillhub_eval.core.ports import Repository

FormalEvalStage = Literal["case_executing", "model_judging"]

FORMAL_EVAL_STARTED_NEUTRAL = "评估需求已满足，正式评估已启动，请稍候…"
FORMAL_EVAL_STARTED_FROM_READINESS = "好的，正式评估已启动，请稍候…"


def case_executing_message(*, uses_local_execution: bool) -> str:
    if uses_local_execution:
        return "正在通过本地 Agent 执行评测案例，每个案例约需 30–60 秒，请稍候…"
    return "正在读取样例输出并执行规则校验，请稍候…"


def model_judging_message(*, uses_local_execution: bool) -> str:
    if uses_local_execution:
        return "本地 Agent 执行已完成，正在进行双模型质量评审，请稍候…"
    return "样例校验完成，正在进行双模型质量评审，请稍候…"


def message_for_formal_eval_stage(
    stage: FormalEvalStage,
    *,
    uses_local_execution: bool,
) -> str:
    if stage == "case_executing":
        return case_executing_message(uses_local_execution=uses_local_execution)
    return model_judging_message(uses_local_execution=uses_local_execution)


def maybe_append_formal_eval_stage_notice(
    repo: Repository,
    run_id: str,
    stage: FormalEvalStage,
    *,
    uses_local_execution: bool,
) -> None:
    """Persist a chat bubble when formal eval enters case exec or model judging."""
    run = repo.get_run(run_id) or {}
    conv_id = run.get("conversation_id")
    if not conv_id:
        return
    if run.get("evaluation_mode") != "capability_full":
        return
    content = message_for_formal_eval_stage(stage, uses_local_execution=uses_local_execution)
    repo.append_lui_message(
        str(conv_id),
        role="agent",
        content=content,
        run_id=run_id,
    )
