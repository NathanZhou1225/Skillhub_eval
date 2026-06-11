from fastapi import HTTPException

from skillhub_eval.core.ports import Repository
from skillhub_eval.core.schemas.enums import RUNNING_STATUSES


def check_session_gate(conversation_id: str, repo: Repository) -> None:
    conv = repo.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conv.get("status") == "frozen":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "CONVERSATION_FROZEN",
                "message": "当前 Skill 正在等待专家审核，暂时无法修改。专家驳回后将自动解冻。",
            },
        )

    if conv.get("status") in (
        "awaiting_draft_confirm",
        "awaiting_propagation_clarify",
        "awaiting_propagation_confirm",
        "awaiting_propagation_dialogue",
        "awaiting_propagation_scene_choice",
        "awaiting_manual_upload",
        "awaiting_clarify",
        "awaiting_readiness_choice",
    ):
        return

    active_run_id = conv.get("active_run_id")
    if active_run_id:
        run = repo.get_run(active_run_id)
        if run and run.get("status") in RUNNING_STATUSES:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "SESSION_LOCKED",
                    "message": "评估引擎正在运行，请稍候再试。",
                    "active_run_id": active_run_id,
                },
            )
