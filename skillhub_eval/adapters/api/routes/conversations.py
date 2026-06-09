"""
Conversation routes:
  POST /conversations/start — create conversation, stage bundle, scan, sanitize,
                              propagate cases if needed, kick off degraded eval run
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.bundle_resolver import BundleResolver
from skillhub_eval.core.case_sanitizer import CaseSanitizer
from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.core.ports import Repository
from skillhub_eval.core.propagator import CasePropagator
from skillhub_eval.core.schemas.enums import BundleState, EvaluationMode
from skillhub_eval.core.security_scan import SecurityScanResult, security_scan
from skillhub_eval.core.taxonomy import Taxonomy
from skillhub_eval.providers.base import BaseLLMProvider

router = APIRouter()


# ── request / response models ─────────────────────────────────────────────────


class ConversationStartRequest(BaseModel):
    skill_id: str
    skill_bundle_path: str
    source: str = "local_ref"  # "local_ref" | "upload"


class ConversationStartResponse(BaseModel):
    conversation_id: str
    run_id: str | None
    security_status: str          # "passed" | "warning" | "blocked"
    security_findings: list[dict] = []
    propagator_used: bool = False
    propagator_fallback: bool = False


def _bundle_scan_text(bundle: dict) -> str:
    cases_text = " ".join(str(c) for c in bundle.get("eval_cases", []))
    return bundle.get("skill_md_text", "") + "\n" + cases_text


def _enforce_security_gate(
    conversation_id: str,
    bundle: dict,
    repo: Repository,
) -> SecurityScanResult:
    """Run security scan; raise 422 and mark conversation blocked on hard violations."""
    scan_result = security_scan(_bundle_scan_text(bundle))
    if scan_result.status == "blocked":
        repo.update_conversation_status(conversation_id, "security_blocked")
        raise HTTPException(
            status_code=422,
            detail={
                "security_status": "blocked",
                "security_findings": scan_result.to_report_dict()["findings"],
                "conversation_id": conversation_id,
            },
        )
    return scan_result


# ── endpoint ──────────────────────────────────────────────────────────────────


@router.post("/start", response_model=ConversationStartResponse, status_code=202)
async def start_conversation(
    req: ConversationStartRequest,
    background_tasks: BackgroundTasks,
    repo: Annotated[Repository, Depends(get_repo)],
    ds: Annotated[BaseLLMProvider, Depends(get_ds_provider)],
    gemini: Annotated[BaseLLMProvider, Depends(get_gemini_provider)],
) -> ConversationStartResponse:
    """
    Start a conversation for a Skill bundle:
      1. Create conversation DB record
      2. Stage bundle from local_ref or upload
      3. Ingest + security scan (blocks on hard violation)
      4. Sanitize cases (move malformed to _broken/)
      5. Propagate missing cases via LLM (fallback to placeholders)
      6. Re-ingest + re-scan propagated cases
      7. Create degraded evaluation run
    """
    # ── 1. Create conversation record ─────────────────────────────────────────
    conversation_id = repo.create_conversation(
        skill_id=req.skill_id,
        source=req.source,
    )

    # ── 2. Mount staging ──────────────────────────────────────────────────────
    resolver = BundleResolver.from_settings(
        conversation_id=conversation_id,
        source=req.source,
        source_path=req.skill_bundle_path,
    )
    resolver.ensure_staging()
    staging_path = resolver.ref.staging_path

    # ── 3. Ingest + pre-propagator security scan ──────────────────────────────
    bundle = ingest_bundle(str(staging_path))
    skill_md_text: str = bundle["skill_md_text"]
    risk_level: str = bundle.get("risk_level_declared") or "low"
    category_slug: str = bundle.get("skill_meta", {}).get("category", "")

    _enforce_security_gate(conversation_id, bundle, repo)

    # ── 4. Sanitize cases ─────────────────────────────────────────────────────
    sanitizer = CaseSanitizer(risk_level=risk_level, staging_path=staging_path)
    sanitizer_result = sanitizer.run()

    # ── 5. Propagate if needed ────────────────────────────────────────────────
    propagator_used = False
    propagator_fallback = False
    if sanitizer_result.needs_propagation:
        taxonomy = Taxonomy()
        propagator = CasePropagator(ds_provider=ds, taxonomy=taxonomy)
        prop_result = await propagator.propagate(
            skill_md_text=skill_md_text,
            risk_level=risk_level,
            category_slug=category_slug,
            staging_path=staging_path,
            gap_by_type=sanitizer_result.gap_by_type,
        )
        propagator_used = True
        propagator_fallback = prop_result.used_fallback

    # ── 6. Re-ingest + post-propagator security scan ──────────────────────────
    bundle = ingest_bundle(str(staging_path))
    scan_result = _enforce_security_gate(conversation_id, bundle, repo)

    # ── 7. Create evaluation run ──────────────────────────────────────────────
    n_cases: int = bundle.get("n_cases", 0)
    bundle_state_str = "minimal" if n_cases < 3 else "draft_enriched"
    bundle_state_enum = BundleState(bundle_state_str)

    run_id = repo.create_run(
        skill_id=req.skill_id,
        skill_bundle_path=str(staging_path),
        bundle_state=bundle_state_str,
        evaluation_mode="degraded",
        conversation_id=conversation_id,
    )

    # ── 8. Start R_101 degraded evaluation in background ─────────────────────
    engine = EvaluationEngine(repo=repo, ds_provider=ds, wb_provider=gemini)
    background_tasks.add_task(
        engine.run_async,
        run_id=run_id,
        skill_bundle_path=str(staging_path),
        bundle_state=bundle_state_enum,
        evaluation_mode=EvaluationMode.degraded,
    )

    return ConversationStartResponse(
        conversation_id=conversation_id,
        run_id=run_id,
        security_status=scan_result.status,
        security_findings=scan_result.to_report_dict()["findings"],
        propagator_used=propagator_used,
        propagator_fallback=propagator_fallback,
    )
