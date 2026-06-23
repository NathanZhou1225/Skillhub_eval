"""
Conversation routes:
  GET  /conversations           — list sessions (Wave 5)
  POST /conversations/new       — empty session + welcome (Wave 5)
  POST /conversations/{id}/bootstrap — start eval on existing session (Wave 5)
  POST /conversations/start     — create conversation, stage bundle, scan, sanitize,
                                  propagate cases if needed, kick off degraded eval run
"""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, ValidationError
from starlette.datastructures import UploadFile as StarletteUploadFile

from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.assessment_gate import (
    append_assessment_gate_message,
    build_assessment_gate_payload,
    next_gate_version,
)
from skillhub_eval.core.bootstrap_errors import append_bootstrap_failure, format_bootstrap_failure_reply
from skillhub_eval.core.bundle_resolver import BundleResolver
from skillhub_eval.core.chat_notifications import start_capability_full_eval
from skillhub_eval.core.case_sanitizer import CaseSanitizer, SanitizerResult
from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.core.ports import Repository
from skillhub_eval.core.propagation_plan import build_propagation_plan
from skillhub_eval.core.propagation_plan_enricher import enrich_propagation_plan
from skillhub_eval.core.propagator import CasePropagator
from skillhub_eval.core.schemas.enums import BundleState, EvaluationMode, RUNNING_STATUSES
from skillhub_eval.core.bundle_security import (
    BundleSecurityScanResult,
    gate_security_kwargs,
    scan_bundle_security,
)
from skillhub_eval.core.skill_id_resolver import (
    needs_user_confirm,
    resolve_skill_id,
    source_label,
)
from skillhub_eval.core.taxonomy import Taxonomy
from skillhub_eval.providers.base import BaseLLMProvider
from skillhub_eval.settings import settings

router = APIRouter()

WELCOME_CONTENT = (
    "欢迎使用 SkillHub 评估助手。\n"
    "请上传 Skill 压缩包（ZIP），或在消息中说明 Skill ID 后上传。"
)
WELCOME_PAYLOAD = {"expected_inputs": ["skill_id", "bundle"]}


# ── request / response models ─────────────────────────────────────────────────


class ConversationStartRequest(BaseModel):
    skill_id: str
    skill_bundle_path: str
    source: str = "local_ref"  # "local_ref" | "upload"


class BootstrapRequest(BaseModel):
    skill_id: str = ""
    skill_bundle_path: str = ""
    source: Literal["local_ref", "upload"] = "upload"
    user_message: str = ""


class ConversationStartResponse(BaseModel):
    conversation_id: str
    run_id: str | None
    security_status: str          # "passed" | "warning" | "blocked"
    security_findings: list[dict] = []
    propagator_used: bool = False
    propagator_fallback: bool = False
    propagation_deferred: bool = False


class BootstrapResponse(BaseModel):
    conversation_id: str
    run_id: str | None = None
    status: str
    skill_id: str | None = None
    skill_id_source: str | None = None
    security_status: str | None = None
    security_findings: list[dict] = []
    propagator_used: bool = False
    propagator_fallback: bool = False
    propagation_deferred: bool = False


class NewConversationResponse(BaseModel):
    conversation_id: str


class ConversationListResponse(BaseModel):
    conversations: list[dict]


def _resolve_start_request(
    *,
    req: ConversationStartRequest | None,
    skill_id: str | None,
    source: str | None,
    skill_bundle_path: str | None,
    bundle_zip: UploadFile | None,
) -> ConversationStartRequest:
    if bundle_zip is not None:
        if not skill_id:
            raise HTTPException(status_code=422, detail="skill_id is required for zip upload")
        return ConversationStartRequest(
            skill_id=skill_id,
            skill_bundle_path=skill_bundle_path or "",
            source="upload",
        )

    if req is not None:
        return req

    if not skill_id:
        raise HTTPException(status_code=422, detail="skill_id is required")

    resolved_source = source or "local_ref"
    resolved_bundle_path = skill_bundle_path or ""
    if resolved_source == "upload":
        raise HTTPException(status_code=422, detail="bundle_zip is required when source=upload")
    if not resolved_bundle_path:
        raise HTTPException(status_code=422, detail="skill_bundle_path is required for local_ref")

    return ConversationStartRequest(
        skill_id=skill_id,
        skill_bundle_path=resolved_bundle_path,
        source=resolved_source,
    )


def _resolve_bootstrap_request(
    *,
    req: BootstrapRequest | None,
    skill_id: str | None,
    source: str | None,
    skill_bundle_path: str | None,
    user_message: str | None,
    bundle_zip: UploadFile | None,
) -> BootstrapRequest:
    if bundle_zip is not None:
        return BootstrapRequest(
            skill_id=skill_id or "",
            skill_bundle_path=skill_bundle_path or "",
            source="upload",
            user_message=user_message or "",
        )

    if req is not None:
        return req

    resolved_source = source or "upload"
    if resolved_source not in ("upload", "local_ref"):
        raise HTTPException(status_code=422, detail="source must be 'upload' or 'local_ref'")
    if resolved_source == "upload" and not bundle_zip:
        raise HTTPException(status_code=422, detail="bundle_zip is required when source=upload")
    if resolved_source == "local_ref" and not (skill_bundle_path or "").strip():
        raise HTTPException(status_code=422, detail="skill_bundle_path is required for local_ref")

    return BootstrapRequest(
        skill_id=skill_id or "",
        skill_bundle_path=skill_bundle_path or "",
        source=resolved_source,  # type: ignore[arg-type]
        user_message=user_message or "",
    )


async def _parse_start_http_payload(
    request: Request,
) -> tuple[ConversationStartRequest, UploadFile | None]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        bundle_file = form.get("bundle_zip")
        bundle_zip = bundle_file if isinstance(bundle_file, StarletteUploadFile) else None
        req = _resolve_start_request(
            req=None,
            skill_id=str(form.get("skill_id") or ""),
            source=str(form.get("source") or ""),
            skill_bundle_path=str(form.get("skill_bundle_path") or ""),
            bundle_zip=bundle_zip,
        )
        return req, bundle_zip

    try:
        payload = await request.json()
        req = ConversationStartRequest.model_validate(payload)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid request payload") from exc
    return req, None


async def _parse_bootstrap_http_payload(
    request: Request,
) -> tuple[BootstrapRequest, UploadFile | None]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        bundle_file = form.get("bundle_zip")
        bundle_zip = bundle_file if isinstance(bundle_file, StarletteUploadFile) else None
        req = _resolve_bootstrap_request(
            req=None,
            skill_id=str(form.get("skill_id") or "") or None,
            source=str(form.get("source") or "") or None,
            skill_bundle_path=str(form.get("skill_bundle_path") or "") or None,
            user_message=str(form.get("user_message") or "") or None,
            bundle_zip=bundle_zip,
        )
        return req, bundle_zip

    try:
        payload = await request.json()
        req = BootstrapRequest.model_validate(payload)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid request payload") from exc
    if req.source == "upload":
        raise HTTPException(status_code=422, detail="bundle_zip is required when source=upload")
    return req, None


def _cleanup_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def _set_conversation_source_path(
    repo: Repository,
    conversation_id: str,
    source_path: Path,
) -> None:
    repo.set_conversation_source_path(conversation_id, str(source_path))


def _set_conversation_source(
    repo: Repository,
    conversation_id: str,
    source: str,
) -> None:
    repo.set_conversation_source(conversation_id, source)


def _hoist_single_wrapper_dir(extract_dir: Path) -> None:
    """Windows/macOS zips often wrap the bundle in one top-level folder.

    Accept ``grill-me/SKILL.md`` by hoisting that folder's contents to *extract_dir*.
    """
    if (extract_dir / "SKILL.md").is_file():
        return
    entries = [
        p
        for p in extract_dir.iterdir()
        if p.name not in ("__MACOSX",) and not p.name.startswith(".")
    ]
    if len(entries) != 1 or not entries[0].is_dir():
        return
    nested = entries[0]
    if not (nested / "SKILL.md").is_file():
        return
    for child in nested.iterdir():
        dest = extract_dir / child.name
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        shutil.move(str(child), str(dest))
    nested.rmdir()


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    file_type = (info.external_attr >> 16) & 0o170000
    return file_type == 0o120000


def _validate_zip_members(zf: zipfile.ZipFile) -> None:
    for info in zf.infolist():
        raw_name = info.filename
        normalized = raw_name.replace("\\", "/")
        posix = PurePosixPath(normalized)
        windows = PureWindowsPath(raw_name)
        if (
            not normalized
            or normalized.startswith("/")
            or windows.is_absolute()
            or windows.drive
            or ".." in posix.parts
            or _is_zip_symlink(info)
        ):
            raise HTTPException(
                status_code=422,
                detail=f"Unsafe zip entry: {raw_name}",
            )


async def _prepare_uploaded_bundle(
    conversation_id: str,
    bundle_zip: UploadFile,
) -> tuple[Path, Path, str]:
    staging_root = Path(settings.staging_root)
    originals_path = staging_root.parent / "originals" / conversation_id
    staging_path = staging_root / conversation_id

    _cleanup_dir(originals_path)
    _cleanup_dir(staging_path)
    originals_path.mkdir(parents=True, exist_ok=True)

    zip_bytes = await bundle_zip.read()
    zip_stem = Path(bundle_zip.filename or "bundle").stem
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            _validate_zip_members(zf)
            zf.extractall(originals_path)
    except zipfile.BadZipFile as exc:
        _cleanup_dir(originals_path)
        raise HTTPException(status_code=422, detail="Invalid zip file") from exc
    except HTTPException:
        _cleanup_dir(originals_path)
        _cleanup_dir(staging_path)
        raise

    _hoist_single_wrapper_dir(originals_path)

    if not (originals_path / "SKILL.md").is_file():
        _cleanup_dir(originals_path)
        raise HTTPException(status_code=422, detail="zip must contain SKILL.md at root")

    shutil.copytree(originals_path, staging_path, dirs_exist_ok=True)
    return originals_path, staging_path, zip_stem


def _enforce_security_gate(
    conversation_id: str,
    bundle: dict,
    repo: Repository,
) -> BundleSecurityScanResult:
    """Block bootstrap on intake (SKILL + scripts) security violations only."""
    staging_path = Path(str(bundle.get("bundle_path") or ""))
    scan_result = scan_bundle_security(bundle, staging_path)
    if scan_result.intake_status == "blocked":
        repo.update_conversation_status(conversation_id, "security_blocked")
        detail = scan_result.to_gate_dict()
        detail["conversation_id"] = conversation_id
        raise HTTPException(status_code=422, detail=detail)
    return scan_result


async def _mount_staging_for_bootstrap(
    conversation_id: str,
    req: BootstrapRequest,
    bundle_zip: UploadFile | None,
    repo: Repository,
) -> tuple[Path, str | None]:
    zip_stem: str | None = None
    if bundle_zip is not None:
        originals_path, staging_path, zip_stem = await _prepare_uploaded_bundle(
            conversation_id, bundle_zip
        )
        _set_conversation_source_path(repo, conversation_id, originals_path)
        _set_conversation_source(repo, conversation_id, "upload")
        return staging_path, zip_stem

    if req.source == "local_ref":
        if not settings.demo_allow_local_ref:
            raise HTTPException(
                status_code=403,
                detail="local_ref bootstrap is disabled outside demo mode",
            )
        resolver = BundleResolver.from_settings(
            conversation_id=conversation_id,
            source=req.source,
            source_path=req.skill_bundle_path,
        )
        resolver.ensure_staging()
        _set_conversation_source(repo, conversation_id, "local_ref")
        return resolver.ref.staging_path, None

    raise HTTPException(status_code=422, detail="bundle_zip is required when source=upload")


async def _build_and_enrich_plan(
    *,
    conversation_id: str,
    staging_path: Path,
    bundle: dict,
    sanitizer_result: SanitizerResult,
    repo: Repository,
    ds: BaseLLMProvider,
    plan_version: int = 1,
) -> dict:
    clarifications = repo.get_clarifications(conversation_id)
    if not isinstance(clarifications, dict):
        clarifications = None
    plan = build_propagation_plan(
        staging_path,
        bundle,
        sanitizer_result,
        clarifications=clarifications,
        plan_version=plan_version,
    )
    conv = repo.get_conversation(conversation_id) or {}
    skill_id = str(bundle.get("skill_id") or conv.get("skill_id") or "")
    category_slug = str(bundle.get("skill_meta", {}).get("category") or "")
    plan = await enrich_propagation_plan(
        plan,
        skill_md_text=str(bundle.get("skill_md_text") or ""),
        skill_id=skill_id,
        category_slug=category_slug,
        clarifications=clarifications,
        ds_provider=ds,
    )
    snapshot = plan.get("enrichment_snapshot")
    if isinstance(snapshot, dict):
        repo.set_plan_enrichment(conversation_id, snapshot)
    return plan


def _defer_with_propagation_plan(
    *,
    conversation_id: str,
    plan: dict,
    sanitizer_result: SanitizerResult,
    repo: Repository,
    gate_snapshot: dict | None = None,
) -> str | None:
    """Append propagation_plan and pause bootstrap when gaps or L0 clarifications remain."""
    l0_questions = plan.get("l0_questions") or []
    if not sanitizer_result.needs_propagation and not l0_questions:
        return None

    status = (
        "awaiting_propagation_clarify"
        if l0_questions
        else "awaiting_propagation_confirm"
    )
    intro = (
        "当前不满足正式评估要求，请查看下方「评估材料补充」并选择补全方式。"
    )
    payload = dict(plan)
    if gate_snapshot and not payload.get("gate_snapshot"):
        payload["gate_snapshot"] = gate_snapshot
    repo.append_lui_message(
        conversation_id,
        role="agent",
        content=intro,
        message_type="propagation_plan",
        payload_json=payload,
    )
    repo.update_conversation_status(conversation_id, status)
    return status


def _maybe_defer_propagation(
    *,
    conversation_id: str,
    staging_path: Path,
    bundle: dict,
    sanitizer_result: SanitizerResult,
    repo: Repository,
    user_message: str | None = None,
    plan: dict | None = None,
) -> str | None:
    """Legacy sync entry — requires pre-enriched plan when deferring."""
    if plan is None:
        clarifications = repo.get_clarifications(conversation_id)
        plan = build_propagation_plan(
            staging_path,
            bundle,
            sanitizer_result,
            clarifications=clarifications,
        )
    return _defer_with_propagation_plan(
        conversation_id=conversation_id,
        plan=plan,
        sanitizer_result=sanitizer_result,
        repo=repo,
    )


async def _phase_eval(
    *,
    conversation_id: str,
    skill_id: str,
    staging_path: Path,
    repo: Repository,
    ds: BaseLLMProvider,
    gemini: BaseLLMProvider,
    background_tasks: BackgroundTasks,
    user_message: str | None = None,
) -> tuple[str | None, SecurityScanResult, bool, bool, bool, str | None]:
    repo.set_conversation_skill_id(conversation_id, skill_id)

    bundle = ingest_bundle(str(staging_path))
    skill_md_text: str = bundle["skill_md_text"]
    risk_level: str = bundle.get("risk_level_declared") or "low"
    category_slug: str = bundle.get("skill_meta", {}).get("category", "")

    scan_result = _enforce_security_gate(conversation_id, bundle, repo)

    sanitizer = CaseSanitizer(risk_level=risk_level, staging_path=staging_path)
    sanitizer_result = sanitizer.run()

    clarifications = repo.get_clarifications(conversation_id)
    if not isinstance(clarifications, dict):
        clarifications = None

    gate_version = next_gate_version(repo, conversation_id)
    gate_payload = build_assessment_gate_payload(
        staging_path=staging_path,
        bundle=bundle,
        sanitizer_result=sanitizer_result,
        gate_version=gate_version,
        clarifications=clarifications,
        **gate_security_kwargs(scan_result),
    )

    plan_sync = build_propagation_plan(
        staging_path,
        bundle,
        sanitizer_result,
        clarifications=clarifications,
    )
    l0_pending = bool(plan_sync.get("l0_questions"))
    if sanitizer_result.needs_propagation or l0_pending:
        plan = await _build_and_enrich_plan(
            conversation_id=conversation_id,
            staging_path=staging_path,
            bundle=bundle,
            sanitizer_result=sanitizer_result,
            repo=repo,
            ds=ds,
            plan_version=int(plan_sync.get("plan_version") or 1),
        )
        append_assessment_gate_message(
            conversation_id,
            repo,
            gate_payload,
            gate_version=gate_version,
        )
        defer_status = _defer_with_propagation_plan(
            conversation_id=conversation_id,
            plan=plan,
            sanitizer_result=sanitizer_result,
            repo=repo,
            gate_snapshot=gate_payload,
        )
        return None, scan_result, False, False, True, defer_status

    append_assessment_gate_message(
        conversation_id,
        repo,
        gate_payload,
        gate_version=gate_version,
    )
    run_id = await start_capability_full_eval(
        conv_id=conversation_id,
        skill_id=skill_id,
        staging_path=staging_path,
        repo=repo,
        ds_provider=ds,
        gemini_provider=gemini,
        background_tasks=background_tasks,
    )
    return run_id, scan_result, False, False, False, None


async def _create_degraded_run(
    *,
    conversation_id: str,
    skill_id: str,
    staging_path: Path,
    repo: Repository,
    ds: BaseLLMProvider,
    gemini: BaseLLMProvider,
    background_tasks: BackgroundTasks,
) -> str:
    """Create degraded eval run and schedule engine — tail of _phase_eval."""
    bundle = ingest_bundle(str(staging_path))
    n_cases: int = bundle.get("n_cases", 0)
    bundle_state_str = "minimal" if n_cases < 3 else "draft_enriched"
    bundle_state_enum = BundleState(bundle_state_str)

    run_id = repo.create_run(
        skill_id=skill_id,
        skill_bundle_path=str(staging_path),
        bundle_state=bundle_state_str,
        evaluation_mode="degraded",
        conversation_id=conversation_id,
    )

    engine = EvaluationEngine(repo=repo, ds_provider=ds, wb_provider=gemini)
    background_tasks.add_task(
        engine.run_async,
        run_id=run_id,
        skill_bundle_path=str(staging_path),
        bundle_state=bundle_state_enum,
        evaluation_mode=EvaluationMode.degraded,
    )
    repo.update_conversation_status(conversation_id, "active")
    return run_id


def _append_bootstrap_system(repo: Repository, conversation_id: str, content: str) -> None:
    repo.append_lui_message(conversation_id, role="system", content=content)


async def continue_eval_after_skill_id_confirmed(
    *,
    conversation_id: str,
    skill_id: str,
    repo: Repository,
    ds: BaseLLMProvider,
    gemini: BaseLLMProvider,
    background_tasks: BackgroundTasks,
) -> tuple[str | None, SecurityScanResult, bool, bool, bool, str | None]:
    """Resume phase_eval after user confirmed auto-identified skill_id (EQ2b)."""
    staging_path = Path(settings.staging_root) / conversation_id
    repo.update_conversation_status(conversation_id, "active")
    repo.append_lui_message(
        conversation_id,
        role="agent",
        content=f"好的，按 `{skill_id}` 开始评估。",
    )
    repo.append_lui_message(
        conversation_id,
        role="agent",
        content="正在分析 Skill、检查评估条件并生成材料补充计划，请稍候…",
    )
    (
        run_id,
        scan_result,
        propagator_used,
        propagator_fallback,
        propagation_deferred,
        defer_status,
    ) = await _phase_eval(
        conversation_id=conversation_id,
        skill_id=skill_id,
        staging_path=staging_path,
        repo=repo,
        ds=ds,
        gemini=gemini,
        background_tasks=background_tasks,
    )
    if propagation_deferred:
        return (
            run_id,
            scan_result,
            propagator_used,
            propagator_fallback,
            propagation_deferred,
            defer_status,
        )
    _append_bootstrap_system(
        repo,
        conversation_id,
        f"已开始评估 Skill `{skill_id}`，请稍候…",
    )
    return (
        run_id,
        scan_result,
        propagator_used,
        propagator_fallback,
        propagation_deferred,
        defer_status,
    )


# ── Wave 5 endpoints ──────────────────────────────────────────────────────────


def _assert_can_archive_conversation(
    conversation_id: str,
    repo: Repository,
    perspective: str,
) -> None:
    conv = repo.get_conversation(conversation_id)
    if conv is None or conv.get("status") == "archived":
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_expert = perspective == "expert"
    if conv.get("status") == "frozen" and not is_expert:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "CONVERSATION_FROZEN",
                "message": "会话已冻结，作者视角不可删除。请切换专家视角或等待驳回解冻。",
            },
        )

    active_run_id = conv.get("active_run_id")
    if not active_run_id:
        return

    run = repo.get_run(active_run_id)
    if not run:
        return

    if run.get("status") in RUNNING_STATUSES:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "SESSION_LOCKED",
                "message": "评估进行中，请稍后再删除。",
            },
        )

    if (
        not is_expert
        and run.get("human_review_required")
        and run.get("status") == "awaiting_human_review"
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "HUMAN_REVIEW_PENDING",
                "message": "待专家复核，作者视角不可删除。",
            },
        )


@router.delete("/{conversation_id}", status_code=204)
async def archive_conversation_route(
    conversation_id: str,
    repo: Annotated[Repository, Depends(get_repo)],
    perspective: Literal["author", "expert"] = Query("author"),
) -> None:
    _assert_can_archive_conversation(conversation_id, repo, perspective)
    if not repo.archive_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("", response_model=ConversationListResponse)
async def list_conversations_route(
    repo: Annotated[Repository, Depends(get_repo)],
    limit: int = Query(50, ge=1, le=200),
    pending_review: bool | None = Query(None),
) -> ConversationListResponse:
    conversations = repo.list_conversations(limit=limit, pending_review=pending_review)
    return ConversationListResponse(conversations=conversations)


@router.post("/new", response_model=NewConversationResponse, status_code=201)
async def create_new_conversation(
    repo: Annotated[Repository, Depends(get_repo)],
) -> NewConversationResponse:
    conversation_id = repo.create_conversation(skill_id="", source="upload")
    repo.append_lui_message(
        conversation_id,
        role="agent",
        content=WELCOME_CONTENT,
        message_type="welcome",
        payload_json=WELCOME_PAYLOAD,
    )
    return NewConversationResponse(conversation_id=conversation_id)


@router.post("/{conversation_id}/bootstrap", response_model=BootstrapResponse, status_code=202)
async def bootstrap_conversation(
    conversation_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    repo: Annotated[Repository, Depends(get_repo)],
    ds: Annotated[BaseLLMProvider, Depends(get_ds_provider)],
    gemini: Annotated[BaseLLMProvider, Depends(get_gemini_provider)],
) -> BootstrapResponse:
    conv = repo.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail=f"conversation_id '{conversation_id}' not found")

    resolved_req, bundle_zip = await _parse_bootstrap_http_payload(request)

    try:
        staging_path, zip_stem = await _mount_staging_for_bootstrap(
            conversation_id, resolved_req, bundle_zip, repo
        )
    except HTTPException as exc:
        append_bootstrap_failure(repo, conversation_id, exc.detail)
        raise

    bundle = ingest_bundle(str(staging_path))
    skill_id, source, warnings = resolve_skill_id(
        user_message=resolved_req.user_message or None,
        explicit_skill_id=resolved_req.skill_id or None,
        bundle=bundle,
        zip_stem=zip_stem,
    )

    for warning in warnings:
        _append_bootstrap_system(repo, conversation_id, warning)

    if not skill_id:
        msg = "无法识别 Skill ID。请在消息中说明 Skill ID，或确保 ZIP 内 SKILL.md 含 name/id 字段。"
        _append_bootstrap_system(repo, conversation_id, f"评估启动失败：{msg}")
        raise HTTPException(status_code=422, detail=msg)

    repo.set_conversation_skill_id(conversation_id, skill_id)

    if needs_user_confirm(source):
        label = source_label(source)
        repo.update_conversation_status(conversation_id, "awaiting_skill_id_confirm")
        confirm_text = (
            f"识别到你的 Skill 名称是 **{skill_id}**（来源：{label}）。"
            "请回复 **确认** 继续评估，或直接告诉我正确名称。"
        )
        repo.append_lui_message(conversation_id, role="agent", content=confirm_text)
        return BootstrapResponse(
            conversation_id=conversation_id,
            run_id=None,
            status="awaiting_skill_id_confirm",
            skill_id=skill_id,
            skill_id_source=source,
        )

    if source == "user_message":
        repo.append_lui_message(
            conversation_id,
            role="agent",
            content=f"好的，按 `{skill_id}` 开始评估。",
        )
    elif source == "explicit_request":
        repo.append_lui_message(
            conversation_id,
            role="agent",
            content=f"好的，按 `{skill_id}` 开始评估。",
        )

    try:
        (
            run_id,
            scan_result,
            propagator_used,
            propagator_fallback,
            propagation_deferred,
            defer_status,
        ) = await _phase_eval(
            conversation_id=conversation_id,
            skill_id=skill_id,
            staging_path=staging_path,
            repo=repo,
            ds=ds,
            gemini=gemini,
            background_tasks=background_tasks,
            user_message=resolved_req.user_message or None,
        )
    except HTTPException as exc:
        append_bootstrap_failure(repo, conversation_id, exc.detail)
        if isinstance(exc.detail, dict):
            raise HTTPException(status_code=422, detail=exc.detail) from exc
        raise

    if propagation_deferred:
        status = defer_status or (
            (repo.get_conversation(conversation_id) or {}).get("status")
        )
        return BootstrapResponse(
            conversation_id=conversation_id,
            run_id=None,
            status=str(status),
            skill_id=skill_id,
            skill_id_source=source,
            security_status=scan_result.security_status,
            security_findings=scan_result.security_findings,
            propagator_used=False,
            propagator_fallback=False,
            propagation_deferred=True,
        )

    _append_bootstrap_system(
        repo,
        conversation_id,
        f"已开始评估 Skill `{skill_id}`，请稍候…",
    )
    return BootstrapResponse(
        conversation_id=conversation_id,
        run_id=run_id,
        status="accepted",
        skill_id=skill_id,
        skill_id_source=source,
        security_status=scan_result.security_status,
        security_findings=scan_result.security_findings,
        propagator_used=propagator_used,
        propagator_fallback=propagator_fallback,
        propagation_deferred=False,
    )


# ── legacy start endpoint ─────────────────────────────────────────────────────


@router.post("/start", response_model=ConversationStartResponse, status_code=202)
async def start_conversation(
    request: Request,
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
    resolved_req, bundle_zip = await _parse_start_http_payload(request)

    conversation_id = repo.create_conversation(
        skill_id=resolved_req.skill_id,
        source=resolved_req.source,
        source_path=resolved_req.skill_bundle_path if resolved_req.source == "local_ref" else "",
    )

    if bundle_zip is not None:
        originals_path, staging_path, _zip_stem = await _prepare_uploaded_bundle(
            conversation_id, bundle_zip
        )
        _set_conversation_source_path(repo, conversation_id, originals_path)
    else:
        resolver = BundleResolver.from_settings(
            conversation_id=conversation_id,
            source=resolved_req.source,
            source_path=resolved_req.skill_bundle_path,
        )
        resolver.ensure_staging()
        staging_path = resolver.ref.staging_path

    try:
        (
            run_id,
            scan_result,
            propagator_used,
            propagator_fallback,
            propagation_deferred,
            _defer_status,
        ) = await _phase_eval(
            conversation_id=conversation_id,
            skill_id=resolved_req.skill_id,
            staging_path=staging_path,
            repo=repo,
            ds=ds,
            gemini=gemini,
            background_tasks=background_tasks,
        )
    except HTTPException as exc:
        if isinstance(exc.detail, dict) and exc.detail.get("security_status") == "blocked":
            raise
        raise

    return ConversationStartResponse(
        conversation_id=conversation_id,
        run_id=run_id,
        security_status=scan_result.security_status,
        security_findings=scan_result.security_findings,
        propagator_used=propagator_used,
        propagator_fallback=propagator_fallback,
        propagation_deferred=propagation_deferred,
    )
