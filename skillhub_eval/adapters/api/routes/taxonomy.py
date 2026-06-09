"""
Taxonomy routes:
  GET /taxonomy/categories — Q-08 business scenario category tree
"""

from __future__ import annotations

from fastapi import APIRouter

from skillhub_eval.core.taxonomy import Taxonomy

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])


@router.get("/categories")
async def get_taxonomy_categories() -> dict:
    """Return the full category taxonomy as a nested JSON tree."""
    return Taxonomy().to_tree_json()
