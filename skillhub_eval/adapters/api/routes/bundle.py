"""
Bundle routes:
  POST /bundle/{skill_id}/confirm — author confirms gap fields
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from skillhub_eval.adapters.api.deps import get_repo
from skillhub_eval.core.ports import Repository
from skillhub_eval.core.schemas import ConfirmRequest

router = APIRouter(prefix="/bundle", tags=["bundle"])


@router.post("/{skill_id}/confirm")
async def confirm_bundle(
    skill_id: str,
    body: ConfirmRequest,
    repo: Annotated[Repository, Depends(get_repo)],
) -> dict:
    """
    Author confirms the AI-generated gap-fill draft.
    Persists each confirmed field so the next run (mode D) can proceed with
    bundle_state=confirmed.

    Returns the list of persisted field confirmations.
    """
    if not body.confirmed_fields:
        raise HTTPException(
            status_code=422,
            detail="confirmed_fields must not be empty.",
        )

    persisted = []
    for field_path, value in body.confirmed_fields.items():
        repo.save_confirmation(
            skill_id=skill_id,
            field_path=field_path,
            confirmed_value=value,
            operator=body.operator,
        )
        persisted.append({"field_path": field_path, "confirmed_value": value})

    return {
        "skill_id": skill_id,
        "operator": body.operator,
        "confirmed_count": len(persisted),
        "confirmed_fields": persisted,
        "next_step": (
            f"Submit a new evaluation run for skill '{skill_id}' with "
            "bundle_state='confirmed' and evaluation_mode='capability_full' "
            "to complete the full review (Mode D)."
        ),
    }
