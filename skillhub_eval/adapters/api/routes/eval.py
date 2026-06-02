"""
Eval routes:
  POST /eval/run        — trigger async evaluation job
  GET  /eval/report/{run_id} — poll report / status
  GET  /eval/history    — list runs
  POST /eval/review/{run_id} — expert approve / reject
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.core.ports import Repository
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
    return {
        "run_id": run_id,
        "status": run["status"],
        "review_status": run.get("review_status"),
        "score_total": run.get("score_total"),
        "human_review_required": bool(run.get("human_review_required")),
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
    repo.update_status(run_id, "completed", review_status=new_status)

    return {
        "run_id": run_id,
        "action": body.action,
        "review_status": new_status,
        "message": f"Review recorded by {body.operator}.",
    }
