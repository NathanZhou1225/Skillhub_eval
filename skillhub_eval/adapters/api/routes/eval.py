"""
Eval routes:
  POST /eval/run        — trigger async evaluation job
  GET  /eval/report/{run_id} — poll report / status
  GET  /eval/history    — list runs
  POST /eval/review/{run_id} — expert approve / reject
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.core.ports import Repository
from skillhub_eval.core.report_narrative import build_report_narrative
from skillhub_eval.core.stage_timing import summarize_stage_timings
from skillhub_eval.core.schemas import BundleState, EvalRunRequest, EvaluationMode
from skillhub_eval.providers.base import BaseLLMProvider

router = APIRouter(prefix="/eval", tags=["eval"])


# ── request / response models ─────────────────────────────────────────────────

from pydantic import BaseModel


class RunResponse(BaseModel):
    run_id: str
    status: str
    message: str


class ReviewRequest(BaseModel):
    action: str          # "approve" | "reject"
    operator: str
    comment: str = ""


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post("/run", response_model=RunResponse, status_code=202)
async def trigger_run(
    req: EvalRunRequest,
    background_tasks: BackgroundTasks,
    repo: Annotated[Repository, Depends(get_repo)],
    ds: Annotated[BaseLLMProvider, Depends(get_ds_provider)],
    gemini: Annotated[BaseLLMProvider, Depends(get_gemini_provider)],
) -> RunResponse:
    """
    Trigger an async evaluation.  Returns run_id immediately (202).
    Poll GET /eval/report/{run_id} for status.
    """
    run_id = repo.create_run(
        skill_id=req.skill_id,
        skill_bundle_path=req.skill_bundle_path,
        bundle_state=req.bundle_state.value,
        evaluation_mode=req.evaluation_mode.value,
    )
    engine = EvaluationEngine(repo=repo, ds_provider=ds, wb_provider=gemini)
    background_tasks.add_task(
        engine.run_async,
        run_id=run_id,
        skill_bundle_path=req.skill_bundle_path,
        bundle_state=req.bundle_state,
        evaluation_mode=req.evaluation_mode,
    )
    return RunResponse(
        run_id=run_id,
        status="pending",
        message="Evaluation job accepted. Poll GET /eval/report/{run_id} for status.",
    )


@router.get("/report/{run_id}")
async def get_report(
    run_id: str,
    repo: Annotated[Repository, Depends(get_repo)],
) -> dict:
    """Poll evaluation status and report."""
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run_id '{run_id}' not found")
    report = repo.get_report(run_id)
    reason_codes_raw = run.get("reason_codes")
    try:
        reason_codes = json.loads(reason_codes_raw) if reason_codes_raw else []
    except (TypeError, json.JSONDecodeError):
        reason_codes = []

    provider_summary = None
    if report and report.get("provider_summary"):
        provider_summary = report["provider_summary"]

    stage_timings = repo.get_stage_timings(run_id)
    provider_errors = repo.get_provider_errors(run_id)
    timing_summary = summarize_stage_timings(stage_timings) if stage_timings else {}
    stage_progress = (
        report.get("stage_progress")
        if report and report.get("stage_progress")
        else repo.get_stage_progress(run_id)
    )

    return {
        "run_id": run_id,
        "conversation_id": run.get("conversation_id"),
        "status": run["status"],
        "review_status": run.get("review_status"),
        "score_total": run.get("score_total"),
        "score_total_source": (
            report.get("score_total_source") if report else run.get("score_total_source")
        ),
        "reason_codes": reason_codes,
        "human_review_required": bool(run.get("human_review_required")),
        "provider_summary": provider_summary,
        "provider_errors": provider_errors,
        "stage_timings": stage_timings,
        "timing_summary": timing_summary,
        "stage_progress": stage_progress,
        "report": report,
    }


@router.get("/history")
async def list_history(
    limit: int = 50,
    human_review_only: bool = False,
    repo: Annotated[Repository, Depends(get_repo)] = None,
) -> dict:
    """List evaluation history. Pass ?human_review_only=true for expert queue."""
    runs = repo.list_history(
        limit=limit,
        human_review_required=True if human_review_only else None,
    )
    return {"total": len(runs), "runs": runs}


@router.get("/history/{run_id}/conversation")
async def get_history_conversation(
    run_id: str,
    repo: Annotated[Repository, Depends(get_repo)],
) -> dict:
    """Return full conversation messages linked to a run (D7)."""
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run_id '{run_id}' not found")
    conversation_id = run.get("conversation_id")
    if not conversation_id:
        raise HTTPException(
            status_code=404,
            detail="This run has no linked conversation archive.",
        )
    messages = repo.get_lui_messages(conversation_id)
    return {
        "conversation_id": conversation_id,
        "messages": messages,
        "message_count": len(messages),
    }


@router.post("/review/{run_id}")
async def submit_review(
    run_id: str,
    body: ReviewRequest,
    repo: Annotated[Repository, Depends(get_repo)],
) -> dict:
    """
    Expert approve / reject a run flagged for human review (R5, R7 warn).
    action must be 'approve' or 'reject'.
    """
    if body.action not in ("approve", "reject"):
        raise HTTPException(
            status_code=422,
            detail="action must be 'approve' or 'reject'",
        )
    run = repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run_id '{run_id}' not found")
    if not run.get("human_review_required"):
        raise HTTPException(
            status_code=409,
            detail="This run does not require human review.",
        )

    votes = repo.get_votes_for_run(run_id)
    repo.save_human_review(
        run_id=run_id,
        action=body.action,
        operator=body.operator,
        comment=body.comment,
        preserved_votes=votes,
    )
    new_status = "pass" if body.action == "approve" else "fail"
    narrative_override = None
    if body.action == "approve":
        report_data = repo.get_report(run_id) or {}
        ps = report_data.get("provider_summary") or {}
        nar = build_report_narrative({
            "review_status": "pass",
            "reason_codes": [],
            "required_actions": [],
            "score_total": run.get("score_total"),
        })
        if ps.get("deepseek_score") is not None:
            score_str = f"DS 参考分 {ps['deepseek_score']}"
            if ps.get("gemini_score") is not None:
                score_str += f" / GM 参考分 {ps['gemini_score']}"
            nar = nar.model_copy(update={"score_display_zh": score_str})
        narrative_override = nar
    repo.patch_report_after_human_review(
        run_id=run_id,
        action=body.action,
        operator=body.operator,
        comment=body.comment,
        review_status=new_status,
        narrative_override=narrative_override,
    )
    repo.update_status(run_id, "completed", review_status=new_status)
    conv_id = run.get("conversation_id")
    if conv_id:
        repo.reset_auto_run_count(conv_id)
        if body.action == "approve":
            repo.append_lui_message(
                conv_id,
                role="system",
                content=(
                    f"专家已批准本次评估。review_status: {new_status}"
                    + (f"（操作者：{body.operator}）" if body.operator else "")
                ),
            )
        elif body.action == "reject":
            repo.update_conversation_status(conv_id, "active")
            repo.set_conversation_auto_confirmed(conv_id, False)
            repo.append_lui_message(
                conv_id,
                role="system",
                content=(
                    f"专家已驳回本次评估。\n驳回意见：{body.comment or '（无）'}\n"
                    "你已获得新的 5 次修改机会，可继续改进 Skill。"
                ),
            )

    return {
        "run_id": run_id,
        "action": body.action,
        "review_status": new_status,
        "message": f"Review recorded by {body.operator}.",
    }
