from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, ValidationError
from starlette.datastructures import UploadFile as StarletteUploadFile

from skillhub_eval.adapters.api._session import check_session_gate
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.adapters.api.routes.conversations import (
    BootstrapRequest,
    _append_bootstrap_system,
    _build_and_enrich_plan,
    _create_degraded_run,
    _mount_staging_for_bootstrap,
    _phase_eval,
    continue_eval_after_skill_id_confirmed,
)
from skillhub_eval.core.bootstrap_errors import (
    append_bootstrap_failure,
    format_bootstrap_failure_reply,
)
from skillhub_eval.core.bundle_security import gate_security_kwargs, scan_bundle_security
from skillhub_eval.core.assessment_gate import (
    append_assessment_gate_message,
    build_assessment_gate_payload,
    gate_content_message,
    next_gate_version,
)
from skillhub_eval.core.chat_notifications import (
    start_capability_full_eval,
    start_formal_eval_from_readiness,
)
from skillhub_eval.core.case_sanitizer import CaseSanitizer
from skillhub_eval.core.clarification_parser import parse_clarification_message
from skillhub_eval.core.confirm_lexicon import is_confirm_message
from skillhub_eval.core.eval_stage_messages import (
    FORMAL_EVAL_STARTED_FROM_READINESS,
    FORMAL_EVAL_STARTED_NEUTRAL,
)
from skillhub_eval.core.gaps import scan_gaps
from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.core.level0 import Level0Checker
from skillhub_eval.core.intent_router import (
    ACTION_DRAFT_MODE,
    ACTION_DRAFT_REGENERATE,
    ACTION_DRAFT_WRITE_FILE,
    ACTION_MANUAL_UPLOAD,
    ACTION_PROPAGATE,
    CONFIDENCE_THRESHOLD,
    IntentRouter,
)
from skillhub_eval.core.lui_agent import LuiAgent
from skillhub_eval.core.ports import Repository
from skillhub_eval.core.propagation_plan import build_propagation_plan, format_l0_labels
from skillhub_eval.core.propagator import CasePropagator, PropagatorResult
from skillhub_eval.core.schemas import BundleState
from skillhub_eval.core.skill_id_resolver import (
    needs_user_confirm,
    parse_user_message_skill_id,
    resolve_skill_id,
    source_label,
)
from skillhub_eval.core.staging_writer import StagingWriter
from skillhub_eval.core.taxonomy import Taxonomy
from skillhub_eval.providers.base import BaseLLMProvider
from skillhub_eval.settings import settings

router = APIRouter()

_CONFIRM_ALL_MARKER = "__SYSTEM_ACTION_CONFIRM_ALL__"
_OPENING_MARKER = "__TRIGGER_AGENT_OPENING__"
_ACTION_CONFIRM_SKILL = "__ACTION_CONFIRM_SKILL__"
_ACTION_PROPAGATE = "__ACTION_PROPAGATE__"
_ACTION_MANUAL_UPLOAD = "__ACTION_MANUAL_UPLOAD__"
_ACTION_DRAFT_MODE = "__ACTION_DRAFT_MODE__"
_ACTION_DRAFT_CONFIRM = "__ACTION_DRAFT_CONFIRM__"
_ACTION_DRAFT_WRITE_FILE = "__ACTION_DRAFT_WRITE_FILE__"
_ACTION_SCENE_PROPAGATE = "__ACTION_SCENE_PROPAGATE__"
_ACTION_START_FORMAL = "__ACTION_START_FORMAL__"
_ACTION_READINESS_DRAFT = "__ACTION_READINESS_DRAFT__"
_INTERNAL_USER_PREFIXES = ("__ACTION_", "__SYSTEM_", "__TRIGGER_")
_START_FORMAL_PHRASES = ("跳过", "开始正式评估", "进入正式评估", "直接正式评估")
_SKILL_ID_CORRECTION_RE = re.compile(r"^[a-zA-Z0-9._-]{2,64}$")


def _is_internal_user_message(message: str) -> bool:
    text = message.strip()
    return any(text.startswith(prefix) for prefix in _INTERNAL_USER_PREFIXES)

_PROPAGATION_GATE_STATUSES = frozenset(
    {
        "awaiting_propagation_confirm",
        "awaiting_propagation_clarify",
        "awaiting_propagation_dialogue",
        "awaiting_propagation_scene_choice",
        "awaiting_manual_upload",
    }
)
_PROPAGATION_REUPLOAD_STATUSES = _PROPAGATION_GATE_STATUSES
_PROPAGATION_CONFIRM_PHRASES = ("允许自动出题", "按表出题", "自动出题")
_MANUAL_UPLOAD_PHRASES = ("我自己补", "自己补")
_DIALOG_DRAFT_PHRASES = ("帮我在对话里补", "对话里补")

_MANUAL_UPLOAD_TEMPLATE = (
    "好的，请自行补充 eval_cases 下的 YAML 文件。每道题建议包含：\n"
    "- `id`：唯一标识\n"
    "- `type`：happy_path / edge / refusal / adversarial\n"
    "- `user_intent`、`input_template`、`expected_behavior`\n\n"
    "若无脚本，可在 `sample_io/` 下放置与题目对应的 JSON 样例。\n"
    "补完后请重新上传 ZIP，我会刷新补题计划。"
)

_DIALOG_DRAFT_GUIDE = (
    "好的，我们改用对话协作补全评估条件。\n"
    "请先选择：你想 **系统自动出题**，还是 **先描述使用场景**？"
)

_SCENE_FORK_GUIDE = (
    "请再选一种方式：\n"
    "· **写进文件让我确认** — 我会给出草案预览，你确认后再写入\n"
    "· **理解后自动出整套题** — 我会根据你的描述自动出题"
)

_DIRECT_WRITE_PHRASES = (
    "你直接帮我",
    "直接帮我补充",
    "直接帮我写",
    "你帮我补充写",
    "你帮我写",
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    intent: str
    new_run_id: str | None = None
    auto_confirmed: bool = False
    gap_zero: bool = False
    bootstrap_status: str | None = None
    activity_phase: str | None = None
    staging_path: str | None = None


class ConfirmCasesRequest(BaseModel):
    case_ids: list[str]


def _resolve_staging_path(conversation_id: str, conv: dict, repo: Repository) -> Path:
    active_run_id = conv.get("active_run_id")
    if active_run_id:
        run = repo.get_run(active_run_id) or {}
        run_path = run.get("skill_bundle_path")
        if run_path:
            return Path(str(run_path))
    return Path(settings.staging_root) / conversation_id


def _compute_gap_zero(staging_path: Path) -> bool:
    if not staging_path.is_dir() or not (staging_path / "SKILL.md").is_file():
        return False
    bundle = ingest_bundle(str(staging_path))
    gaps = scan_gaps(bundle, BundleState.draft_enriched)
    blocking = {"required", "block"}
    return not any(g.get("severity") in blocking for g in gaps.get("gaps", []))


async def _parse_chat_payload(
    request: Request,
) -> tuple[str, UploadFile | None]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        message = str(form.get("message") or "")
        bundle_file = form.get("bundle_zip")
        bundle_zip = bundle_file if isinstance(bundle_file, StarletteUploadFile) else None
        return message, bundle_zip
    try:
        payload = await request.json()
        req = ChatRequest.model_validate(payload)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid chat payload") from exc
    return req.message, None


def _parse_skill_id_correction(message: str) -> str | None:
    parsed = parse_user_message_skill_id(message)
    if parsed:
        return parsed
    stripped = message.strip()
    if _SKILL_ID_CORRECTION_RE.match(stripped):
        return stripped.lower()
    return None


def _is_propagation_confirm_reply(message: str) -> bool:
    text = message.strip()
    if is_confirm_message(text):
        return True
    if text == _ACTION_PROPAGATE or text == _ACTION_DRAFT_CONFIRM:
        return True
    lower = text.lower()
    if lower == "manual":
        return False
    return any(phrase in text for phrase in _PROPAGATION_CONFIRM_PHRASES)


def _is_manual_upload_reply(message: str) -> bool:
    text = message.strip()
    if text == _ACTION_MANUAL_UPLOAD:
        return True
    if text.lower() == "manual":
        return True
    return any(phrase in text for phrase in _MANUAL_UPLOAD_PHRASES)


def _is_dialog_draft_reply(message: str) -> bool:
    if message.strip() == _ACTION_DRAFT_MODE:
        return True
    return any(phrase in message for phrase in _DIALOG_DRAFT_PHRASES)


def _is_direct_write_reply(message: str) -> bool:
    text = message.strip()
    return any(phrase in text for phrase in _DIRECT_WRITE_PHRASES)


def _fork_payload(
    *,
    fork: str,
    step: int,
    total: int,
    label: str,
    next_hint: str,
) -> dict:
    return {
        "fork": fork,
        "flow_step": {"current": step, "total": total, "label_zh": label},
        "next_hint_zh": next_hint,
    }


def _latest_propagation_plan(messages: list[dict]) -> dict | None:
    plans = [m for m in messages if m.get("message_type") == "propagation_plan"]
    if not plans:
        return None
    payload = plans[-1].get("payload_json")
    if payload is None:
        return None
    if isinstance(payload, str):
        return json.loads(payload)
    return payload


def _parse_l0_clarification_answer(message: str, l0_questions: list[dict]) -> dict[str, str]:
    text = message.strip()
    if not text:
        return {}
    for sep in ("：", ":"):
        if sep in text:
            key, _, value = text.partition(sep)
            key = key.strip()
            value = value.strip()
            if key and value:
                return {key: value}
    if len(l0_questions) == 1:
        return {str(l0_questions[0]["key"]): text}
    return {}


def _pending_clarification_keys(history: list[dict]) -> list[str]:
    for msg in reversed(history):
        if msg.get("role") != "agent" or msg.get("message_type") != "clarify":
            continue
        payload = msg.get("payload_json")
        if payload is None:
            return []
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                return []
        if not isinstance(payload, dict):
            return []
        keys = payload.get("clarification_keys")
        if not isinstance(keys, list):
            return []
        return [str(k).strip() for k in keys if str(k).strip()]
    return []


def _parse_clarification_answer(message: str, keys: list[str]) -> dict[str, str]:
    text = message.strip()
    if not text:
        return {}
    for sep in ("：", ":"):
        if sep in text:
            key, _, value = text.partition(sep)
            key = key.strip()
            value = value.strip()
            if key and value:
                return {key: value}
    if len(keys) == 1:
        return {keys[0]: text}
    return {}


def _raise_clarify_mutation_blocked() -> None:
    raise HTTPException(
        status_code=403,
        detail={
            "error": "CLARIFY_GATE_LOCKED",
            "message": "澄清确认阶段暂不支持直接修改，请先回答 Agent 的问题。",
        },
    )


def _plan_with_gate_snapshot(
    plan: dict,
    *,
    staging_path: Path,
    conv_id: str,
    repo: Repository,
) -> dict:
    if not staging_path.is_dir():
        return plan
    bundle = ingest_bundle(str(staging_path))
    risk_level = str(bundle.get("risk_level_declared") or "low")
    sanitizer = CaseSanitizer(risk_level=risk_level, staging_path=staging_path)
    sanitizer_result = sanitizer.run()
    clarifications = repo.get_clarifications(conv_id)
    layered = scan_bundle_security(bundle, staging_path)
    gate_payload = build_assessment_gate_payload(
        staging_path=staging_path,
        bundle=bundle,
        sanitizer_result=sanitizer_result,
        clarifications=clarifications if isinstance(clarifications, dict) else None,
        **gate_security_kwargs(layered),
    )
    return {**plan, "gate_snapshot": gate_payload}


def _append_propagation_plan_message(
    repo: Repository,
    conv_id: str,
    plan: dict,
    *,
    staging_path: Path | None = None,
) -> None:
    if staging_path is not None and staging_path.is_dir():
        plan = _plan_with_gate_snapshot(
            plan, staging_path=staging_path, conv_id=conv_id, repo=repo
        )
    repo.append_lui_message(
        conv_id,
        role="agent",
        content=str(plan.get("headline_zh") or "评估题型尚缺，请确认补题计划。"),
        message_type="propagation_plan",
        payload_json=plan,
    )


def _summarize_cases_by_type(case_ids: list[str]) -> list[dict[str, object]]:
    patterns: tuple[tuple[str, str], ...] = (
        ("happy", "正常场景"),
        ("edge", "边界场景"),
        ("refusal", "拒绝场景"),
        ("adv", "对抗场景"),
    )
    counts: dict[str, int] = {}
    for raw_id in case_ids:
        lower = str(raw_id).lower()
        label = "其他"
        for pat, zh in patterns:
            if pat in lower:
                label = zh
                break
        counts[label] = counts.get(label, 0) + 1
    return [{"type_zh": k, "count": v} for k, v in counts.items()]


def _append_propagation_summary(
    repo: Repository,
    conv_id: str,
    prop_result: PropagatorResult,
) -> None:
    n_added = len(prop_result.cases_written)
    cases_written = list(prop_result.cases_written)
    type_summary = _summarize_cases_by_type(cases_written)
    payload = {
        "cases_written": cases_written,
        "cases_failed": list(prop_result.cases_failed),
        "used_fallback": prop_result.used_fallback,
        "files": cases_written,
        "n_added": n_added,
        "type_summary": type_summary,
    }
    content = f"已按你的确认自动生成 {n_added} 道评估题。"
    if prop_result.used_fallback:
        content += "（部分题目使用了模板兜底。）"
    repo.append_lui_message(
        conv_id,
        role="agent",
        content=content,
        message_type="propagation_summary",
        payload_json=payload,
    )


def _build_gate_after_propagation(
    *,
    repo: Repository,
    conv_id: str,
    staging_path: Path,
    bundle: dict,
    risk_level: str,
    layered: Any,
) -> tuple[dict, int]:
    sanitizer = CaseSanitizer(risk_level=risk_level, staging_path=staging_path)
    sanitizer_result = sanitizer.run()
    clarifications = repo.get_clarifications(conv_id)
    gate_version = next_gate_version(repo, conv_id)
    gate_payload = build_assessment_gate_payload(
        staging_path=staging_path,
        bundle=bundle,
        sanitizer_result=sanitizer_result,
        gate_version=gate_version,
        clarifications=clarifications if isinstance(clarifications, dict) else None,
        **gate_security_kwargs(layered),
    )
    return gate_payload, gate_version


async def _refresh_propagation_plan_async(
    *,
    conv_id: str,
    staging_path: Path,
    repo: Repository,
    plan_version: int,
    ds: BaseLLMProvider,
) -> dict:
    bundle = ingest_bundle(str(staging_path))
    risk_level = str(bundle.get("risk_level_declared") or "low")
    sanitizer = CaseSanitizer(risk_level=risk_level, staging_path=staging_path)
    sanitizer_result = sanitizer.run()
    return await _build_and_enrich_plan(
        conversation_id=conv_id,
        staging_path=staging_path,
        bundle=bundle,
        sanitizer_result=sanitizer_result,
        repo=repo,
        ds=ds,
        plan_version=plan_version,
    )


async def _execute_propagate(
    *,
    conv_id: str,
    skill_id: str,
    staging_path: Path,
    repo: Repository,
    ds: BaseLLMProvider,
    gemini: BaseLLMProvider,
    background_tasks: BackgroundTasks,
) -> ChatResponse:
    if not staging_path.is_dir() or not skill_id:
        reply = "缺少 staging 或 Skill ID，请重新上传 ZIP。"
        repo.append_lui_message(conv_id, role="agent", content=reply)
        return ChatResponse(reply=reply, intent="explain_only", activity_phase="propagating")

    repo.append_lui_message(
        conv_id,
        role="agent",
        content="正在根据补题计划自动生成评估题目，请稍候…",
    )
    bundle = ingest_bundle(str(staging_path))
    skill_md_text: str = bundle["skill_md_text"]
    risk_level: str = bundle.get("risk_level_declared") or "low"
    category_slug: str = bundle.get("skill_meta", {}).get("category", "")
    sanitizer = CaseSanitizer(risk_level=risk_level, staging_path=staging_path)
    sanitizer_result = sanitizer.run()
    clarifications = repo.get_clarifications(conv_id)
    taxonomy = Taxonomy()
    propagator = CasePropagator(ds_provider=ds, taxonomy=taxonomy)
    prop_result = await propagator.propagate(
        skill_md_text=skill_md_text,
        risk_level=risk_level,
        category_slug=category_slug,
        staging_path=staging_path,
        gap_by_type=sanitizer_result.gap_by_type,
        clarifications=clarifications,
    )
    _append_propagation_summary(repo, conv_id, prop_result)
    bundle = ingest_bundle(str(staging_path))
    layered = scan_bundle_security(bundle, staging_path)
    gate_payload, gate_version = _build_gate_after_propagation(
        repo=repo,
        conv_id=conv_id,
        staging_path=staging_path,
        bundle=bundle,
        risk_level=risk_level,
        layered=layered,
    )
    append_assessment_gate_message(
        conv_id,
        repo,
        gate_payload,
        gate_version=gate_version,
    )
    if not gate_payload.get("can_enter_formal"):
        reply = gate_content_message(gate_payload)
        return ChatResponse(
            reply=reply,
            intent="explain_only",
            bootstrap_status=repo.get_conversation(conv_id).get("status"),
        )
    run_id = await start_capability_full_eval(
        conv_id=conv_id,
        skill_id=skill_id,
        staging_path=staging_path,
        repo=repo,
        ds_provider=ds,
        gemini_provider=gemini,
        background_tasks=background_tasks,
    )
    reply = FORMAL_EVAL_STARTED_NEUTRAL
    return ChatResponse(
        reply=reply,
        intent="system_action",
        new_run_id=run_id,
        bootstrap_status="active",
        activity_phase="formal_eval",
    )


def _raise_propagation_mutation_blocked() -> None:
    raise HTTPException(
        status_code=403,
        detail={
            "error": "PROPAGATION_GATE_LOCKED",
            "message": "补题确认阶段暂不支持直接修改，请先选择补题方式或完成澄清。",
        },
    )


async def _handle_propagation_gate_chat(
    conv_id: str,
    message: str,
    conv: dict,
    repo: Repository,
    ds: BaseLLMProvider,
    gemini: BaseLLMProvider,
    background_tasks: BackgroundTasks,
) -> ChatResponse | None:
    status = conv.get("status")
    if status not in _PROPAGATION_GATE_STATUSES:
        return None

    skill_id = str(conv.get("skill_id") or "")
    staging_path = Path(settings.staging_root) / conv_id
    history = repo.get_lui_messages(conv_id)
    latest_plan = _latest_propagation_plan(history)

    if status == "awaiting_propagation_clarify":
        l0_questions = (latest_plan or {}).get("l0_questions") or []
        keys = [str(q.get("key", "")) for q in l0_questions if q.get("key")]
        text = message.strip()

        if _is_propagation_confirm_reply(text):
            if l0_questions:
                keys_label = format_l0_labels(l0_questions)
                reply = f"仍有澄清项待回答：{keys_label}。请先在上方「待澄清」区回复，再点「自动出题」。"
                repo.append_lui_message(conv_id, role="agent", content=reply)
                return ChatResponse(
                    reply=reply,
                    intent="explain_only",
                    bootstrap_status=status,
                )
            repo.update_conversation_status(conv_id, "awaiting_propagation_confirm")
            return await _execute_propagate(
                conv_id=conv_id,
                skill_id=skill_id,
                staging_path=staging_path,
                repo=repo,
                ds=ds,
                gemini=gemini,
                background_tasks=background_tasks,
            )

        answers = await parse_clarification_message(message, keys, ds)
        if not answers:
            answers = _parse_l0_clarification_answer(message, l0_questions)
        if not answers:
            reply = "请按上方「待澄清」问题回复；补充后我会刷新补题计划。"
            repo.append_lui_message(conv_id, role="agent", content=reply)
            return ChatResponse(
                reply=reply,
                intent="explain_only",
                bootstrap_status=status,
            )

        repo.merge_clarifications(conv_id, answers)
        repo.append_lui_message(
            conv_id,
            role="agent",
            content="正在根据澄清刷新补题计划，请稍候…",
        )
        plan_version = int((latest_plan or {}).get("plan_version") or 1) + 1
        new_plan = await _refresh_propagation_plan_async(
            conv_id=conv_id,
            staging_path=staging_path,
            repo=repo,
            plan_version=plan_version,
            ds=ds,
        )
        _append_propagation_plan_message(
            repo, conv_id, new_plan, staging_path=staging_path
        )
        remaining_l0 = new_plan.get("l0_questions") or []
        if remaining_l0:
            repo.update_conversation_status(conv_id, "awaiting_propagation_clarify")
            keys_label = format_l0_labels(remaining_l0)
            reply = f"感谢回答。仍需澄清：{keys_label}。请继续回复。"
        else:
            repo.update_conversation_status(conv_id, "awaiting_propagation_confirm")
            reply = "澄清已记录，补题计划已更新。请点「自动出题」或选择其他补全方式。"
        repo.append_lui_message(conv_id, role="agent", content=reply)
        return ChatResponse(
            reply=reply,
            intent="explain_only",
            bootstrap_status=repo.get_conversation(conv_id).get("status"),
            activity_phase="enriching_plan",
        )

    if status == "awaiting_propagation_dialogue":
        text = message.strip()
        if (
            _is_propagation_confirm_reply(text)
            or "自动出题" in text
            or text == _ACTION_PROPAGATE
        ):
            return await _execute_propagate(
                conv_id=conv_id,
                skill_id=skill_id,
                staging_path=staging_path,
                repo=repo,
                ds=ds,
                gemini=gemini,
                background_tasks=background_tasks,
            )
        if "描述" in text or "场景" in text or text == _ACTION_DRAFT_MODE:
            repo.update_conversation_status(conv_id, "awaiting_propagation_scene_choice")
            fork = _fork_payload(
                fork="scene_choice",
                step=2,
                total=3,
                label="选择如何根据场景补全",
                next_hint="可选：写进文件确认，或理解后自动出题。",
            )
            repo.append_lui_message(
                conv_id,
                role="agent",
                content=_SCENE_FORK_GUIDE,
                message_type="propagation_fork",
                payload_json=fork,
            )
            return ChatResponse(
                reply=_SCENE_FORK_GUIDE,
                intent="explain_only",
                bootstrap_status="awaiting_propagation_scene_choice",
            )
        reply = "请选：点「自动出题」，或回复「我想描述使用场景」。"
        repo.append_lui_message(conv_id, role="agent", content=reply)
        return ChatResponse(reply=reply, intent="explain_only")

    if status == "awaiting_propagation_scene_choice":
        text = message.strip()
        if text == _ACTION_DRAFT_WRITE_FILE or "写进文件" in text or "草案" in text:
            repo.update_conversation_status(conv_id, "awaiting_draft_confirm")
            agent = LuiAgent(ds_provider=ds)
            staging = staging_path if staging_path.is_dir() else None
            draft = await agent.generate_draft_for_staging(staging, repo, conv_id)
            return ChatResponse(
                reply=str(draft.get("reply", _DIALOG_DRAFT_GUIDE)),
                intent="explain_only",
                bootstrap_status="awaiting_draft_confirm",
                activity_phase="writing_draft",
            )
        if text == _ACTION_SCENE_PROPAGATE or "自动出" in text or "整套" in text:
            if message.strip():
                repo.merge_clarifications(conv_id, {"scene_description": message.strip()})
            plan_version = int((latest_plan or {}).get("plan_version") or 1) + 1
            new_plan = await _refresh_propagation_plan_async(
                conv_id=conv_id,
                staging_path=staging_path,
                repo=repo,
                plan_version=plan_version,
                ds=ds,
            )
            _append_propagation_plan_message(
                repo, conv_id, new_plan, staging_path=staging_path
            )
            repo.update_conversation_status(conv_id, "awaiting_propagation_confirm")
            reply = "已记录你的场景描述并更新计划。请点「自动出题」开始生成题目。"
            repo.append_lui_message(conv_id, role="agent", content=reply)
            return ChatResponse(
                reply=reply,
                intent="explain_only",
                bootstrap_status="awaiting_propagation_confirm",
            )
        if message.strip():
            repo.merge_clarifications(conv_id, {"scene_description": message.strip()})
            reply = "已记录场景描述。请选「写进文件确认」或「理解后自动出题」。"
            repo.append_lui_message(conv_id, role="agent", content=reply)
            return ChatResponse(reply=reply, intent="explain_only")

    if _is_manual_upload_reply(message):
        repo.update_conversation_status(conv_id, "awaiting_manual_upload")
        repo.append_lui_message(conv_id, role="agent", content=_MANUAL_UPLOAD_TEMPLATE)
        return ChatResponse(
            reply=_MANUAL_UPLOAD_TEMPLATE,
            intent="explain_only",
            bootstrap_status="awaiting_manual_upload",
        )

    if _is_dialog_draft_reply(message) and status == "awaiting_propagation_confirm":
        repo.update_conversation_status(conv_id, "awaiting_propagation_dialogue")
        fork = _fork_payload(
            fork="mode_choice",
            step=1,
            total=3,
            label="选择补全方式",
            next_hint="可选：系统自动出题，或先描述使用场景。",
        )
        repo.append_lui_message(
            conv_id,
            role="agent",
            content=_DIALOG_DRAFT_GUIDE,
            message_type="propagation_fork",
            payload_json=fork,
        )
        return ChatResponse(
            reply=_DIALOG_DRAFT_GUIDE,
            intent="explain_only",
            bootstrap_status="awaiting_propagation_dialogue",
        )

    if status in (
        "awaiting_propagation_confirm",
        "awaiting_propagation_dialogue",
    ) and _is_propagation_confirm_reply(message):
        plan = latest_plan or {}
        l0_questions = plan.get("l0_questions") or []
        if l0_questions:
            _append_propagation_plan_message(
                repo, conv_id, plan, staging_path=staging_path
            )
            repo.update_conversation_status(conv_id, "awaiting_propagation_clarify")
            reply = "仍有信息需要先澄清，暂不能自动出题。请按上方问题回复。"
            repo.append_lui_message(conv_id, role="agent", content=reply)
            return ChatResponse(
                reply=reply,
                intent="explain_only",
                bootstrap_status="awaiting_propagation_clarify",
            )
        return await _execute_propagate(
            conv_id=conv_id,
            skill_id=skill_id,
            staging_path=staging_path,
            repo=repo,
            ds=ds,
            gemini=gemini,
            background_tasks=background_tasks,
        )

    if status in _PROPAGATION_GATE_STATUSES:
        router = IntentRouter(ds)
        intent = await router.classify(
            message,
            conversation_status=str(status),
            history_snippet=history,
        )
        if intent.action == ACTION_PROPAGATE and intent.confidence >= CONFIDENCE_THRESHOLD:
            return await _execute_propagate(
                conv_id=conv_id,
                skill_id=skill_id,
                staging_path=staging_path,
                repo=repo,
                ds=ds,
                gemini=gemini,
                background_tasks=background_tasks,
            )
        if intent.action == ACTION_MANUAL_UPLOAD and intent.confidence >= CONFIDENCE_THRESHOLD:
            repo.update_conversation_status(conv_id, "awaiting_manual_upload")
            repo.append_lui_message(conv_id, role="agent", content=_MANUAL_UPLOAD_TEMPLATE)
            return ChatResponse(
                reply=_MANUAL_UPLOAD_TEMPLATE,
                intent="explain_only",
                bootstrap_status="awaiting_manual_upload",
            )
        if (
            intent.action is None
            and intent.confidence >= CONFIDENCE_THRESHOLD
            and intent.reply
        ):
            repo.append_lui_message(conv_id, role="agent", content=intent.reply)
            return ChatResponse(reply=intent.reply, intent="explain_only")

    return None


async def _handle_readiness_choice_chat(
    conv_id: str,
    message: str,
    conv: dict,
    repo: Repository,
    ds: BaseLLMProvider,
    gemini: BaseLLMProvider,
    background_tasks: BackgroundTasks,
) -> ChatResponse | None:
    if conv.get("status") != "awaiting_readiness_choice":
        return None

    text = message.strip()
    run_id = str(conv.get("active_run_id") or "")

    if text == _ACTION_START_FORMAL or any(p in text for p in _START_FORMAL_PHRASES):
        if not run_id:
            reply = "尚未找到初评记录，请刷新后重试。"
            repo.append_lui_message(conv_id, role="agent", content=reply)
            return ChatResponse(reply=reply, intent="explain_only")
        new_run_id = await start_formal_eval_from_readiness(
            conv_id,
            run_id,
            repo,
            ds,
            gemini,
            background_tasks=background_tasks,
        )
        reply = FORMAL_EVAL_STARTED_FROM_READINESS
        return ChatResponse(
            reply=reply,
            intent="system_action",
            new_run_id=new_run_id,
            bootstrap_status="active",
            activity_phase="formal_eval",
        )

    if text == _ACTION_MANUAL_UPLOAD or _is_manual_upload_reply(text):
        repo.update_conversation_status(conv_id, "awaiting_manual_upload")
        repo.append_lui_message(conv_id, role="agent", content=_MANUAL_UPLOAD_TEMPLATE)
        return ChatResponse(
            reply=_MANUAL_UPLOAD_TEMPLATE,
            intent="explain_only",
            bootstrap_status="awaiting_manual_upload",
        )

    if (
        text == _ACTION_READINESS_DRAFT
        or text == _ACTION_DRAFT_MODE
        or any(p in text for p in _DIALOG_DRAFT_PHRASES)
    ):
        repo.update_conversation_status(conv_id, "active")
        reply = (
            "好的，请描述你想补充的说明文档内容（如禁止指令、权限范围、错误处理等）。"
            "我会起草修改方案，你确认后再写入。"
        )
        repo.append_lui_message(conv_id, role="agent", content=reply)
        return ChatResponse(reply=reply, intent="explain_only", bootstrap_status="active")

    reply = (
        "初评已通过评估条件门槛。你可：① 对话补充说明文档；② 重传 ZIP；"
        "③ 点「开始正式评估」跳过可选改进。"
    )
    repo.append_lui_message(conv_id, role="agent", content=reply)
    return ChatResponse(reply=reply, intent="explain_only")


async def _handle_skill_id_confirm_chat(
    conv_id: str,
    message: str,
    conv: dict,
    repo: Repository,
    ds: BaseLLMProvider,
    gemini: BaseLLMProvider,
    background_tasks: BackgroundTasks,
) -> ChatResponse | None:
    if conv.get("status") != "awaiting_skill_id_confirm":
        return None

    skill_id = str(conv.get("skill_id") or "")
    if not skill_id:
        reply = "尚未识别 Skill ID，请直接告诉我正确名称。"
        repo.append_lui_message(conv_id, role="agent", content=reply)
        return ChatResponse(reply=reply, intent="explain_only", bootstrap_status="awaiting_skill_id_confirm")

    if is_confirm_message(message) or message.strip() == _ACTION_CONFIRM_SKILL:
        try:
            (
                run_id,
                _,
                _,
                _,
                propagation_deferred,
                defer_status,
            ) = await continue_eval_after_skill_id_confirmed(
                conversation_id=conv_id,
                skill_id=skill_id,
                repo=repo,
                ds=ds,
                gemini=gemini,
                background_tasks=background_tasks,
            )
        except HTTPException as exc:
            append_bootstrap_failure(repo, conv_id, exc.detail)
            reply = format_bootstrap_failure_reply(exc.detail)
            return ChatResponse(reply=reply, intent="explain_only", bootstrap_status="failed")
        if propagation_deferred:
            status = defer_status or (repo.get_conversation(conv_id) or {}).get("status")
            staging = Path(settings.staging_root) / conv_id
            return ChatResponse(
                reply="评估材料补充计划已就绪，请查看下方卡片并选择补全方式。",
                intent="explain_only",
                new_run_id=None,
                bootstrap_status=str(status),
                staging_path=str(staging) if staging.is_dir() else None,
            )
        staging = Path(settings.staging_root) / conv_id
        return ChatResponse(
            reply=f"已开始评估 Skill `{skill_id}`。",
            intent="system_action",
            new_run_id=run_id,
            bootstrap_status="accepted",
            staging_path=str(staging) if staging.is_dir() else None,
        )

    corrected = _parse_skill_id_correction(message)
    if corrected:
        repo.set_conversation_skill_id(conv_id, corrected)
        repo.update_conversation_status(conv_id, "active")
        repo.append_lui_message(
            conv_id,
            role="agent",
            content=f"好的，按 `{corrected}` 开始评估。",
        )
        repo.append_lui_message(
            conv_id,
            role="agent",
            content="正在分析 Skill、检查评估条件并生成材料补充计划，请稍候…",
        )
        staging_path = Path(settings.staging_root) / conv_id
        try:
            (
                run_id,
                _,
                _,
                _,
                propagation_deferred,
                defer_status,
            ) = await _phase_eval(
                conversation_id=conv_id,
                skill_id=corrected,
                staging_path=staging_path,
                repo=repo,
                ds=ds,
                gemini=gemini,
                background_tasks=background_tasks,
            )
        except HTTPException as exc:
            append_bootstrap_failure(repo, conv_id, exc.detail)
            reply = format_bootstrap_failure_reply(exc.detail)
            return ChatResponse(reply=reply, intent="explain_only", bootstrap_status="failed")
        if propagation_deferred:
            status = defer_status or (repo.get_conversation(conv_id) or {}).get("status")
            return ChatResponse(
                reply="已生成补题计划，请先确认或补充信息后再开始初评。",
                intent="explain_only",
                new_run_id=None,
                bootstrap_status=str(status),
            )
        return ChatResponse(
            reply=f"已开始评估 Skill `{corrected}`。",
            intent="system_action",
            new_run_id=run_id,
            bootstrap_status="accepted",
        )

    reply = "请回复 **确认** 继续评估，或直接发送正确的 Skill ID。"
    repo.append_lui_message(conv_id, role="agent", content=reply)
    return ChatResponse(reply=reply, intent="explain_only", bootstrap_status="awaiting_skill_id_confirm")


async def _handle_chat_zip_bootstrap(
    conv_id: str,
    message: str,
    bundle_zip: StarletteUploadFile,
    repo: Repository,
    ds: BaseLLMProvider,
    gemini: BaseLLMProvider,
    background_tasks: BackgroundTasks,
) -> ChatResponse | None:
    conv = repo.get_conversation(conv_id) or {}
    is_propagation_reupload = conv.get("status") in _PROPAGATION_REUPLOAD_STATUSES

    req = BootstrapRequest(source="upload", user_message=message)
    try:
        staging_path, zip_stem = await _mount_staging_for_bootstrap(
            conv_id, req, bundle_zip, repo
        )
    except HTTPException as exc:
        append_bootstrap_failure(repo, conv_id, exc.detail)
        if isinstance(exc.detail, str):
            reply = f"上传失败：{exc.detail}"
        else:
            reply = format_bootstrap_failure_reply(exc.detail)
        return ChatResponse(reply=reply, intent="explain_only", bootstrap_status="failed")

    bundle = ingest_bundle(str(staging_path))
    skill_id, source, warnings = resolve_skill_id(
        user_message=message or None,
        explicit_skill_id=None,
        bundle=bundle,
        zip_stem=zip_stem,
    )
    for warning in warnings:
        _append_bootstrap_system(repo, conv_id, warning)

    if is_propagation_reupload and conv.get("skill_id"):
        skill_id = str(conv["skill_id"])
    elif not skill_id:
        msg = "无法识别 Skill ID。请在消息中说明 Skill ID，或确保 ZIP 内 SKILL.md 含 name/id 字段。"
        _append_bootstrap_system(repo, conv_id, f"评估启动失败：{msg}")
        return ChatResponse(reply=msg, intent="explain_only", bootstrap_status="failed")

    repo.set_conversation_skill_id(conv_id, skill_id)

    if needs_user_confirm(source) and not is_propagation_reupload:
        label = source_label(source)
        repo.update_conversation_status(conv_id, "awaiting_skill_id_confirm")
        confirm_text = (
            f"识别到你的 Skill 名称是 **{skill_id}**（来源：{label}）。"
            "请回复 **确认** 继续评估，或直接告诉我正确名称。"
        )
        repo.append_lui_message(conv_id, role="agent", content=confirm_text)
        return ChatResponse(
            reply=confirm_text,
            intent="explain_only",
            bootstrap_status="awaiting_skill_id_confirm",
            staging_path=str(staging_path),
        )

    if source == "user_message":
        repo.append_lui_message(
            conv_id, role="agent", content=f"好的，按 `{skill_id}` 开始评估。"
        )

    try:
        (
            run_id,
            _,
            _,
            _,
            propagation_deferred,
            defer_status,
        ) = await _phase_eval(
            conversation_id=conv_id,
            skill_id=skill_id,
            staging_path=staging_path,
            repo=repo,
            ds=ds,
            gemini=gemini,
            background_tasks=background_tasks,
            user_message=message or None,
        )
    except HTTPException as exc:
        append_bootstrap_failure(repo, conv_id, exc.detail)
        reply = format_bootstrap_failure_reply(exc.detail)
        return ChatResponse(reply=reply, intent="explain_only", bootstrap_status="failed")

    if propagation_deferred:
        status = defer_status or (repo.get_conversation(conv_id) or {}).get("status")
        return ChatResponse(
            reply="已生成补题计划，请先确认或补充信息后再开始初评。",
            intent="explain_only",
            new_run_id=None,
            bootstrap_status=str(status),
            staging_path=str(staging_path),
        )

    _append_bootstrap_system(
        repo, conv_id, f"已开始评估 Skill `{skill_id}`，请稍候…"
    )
    return ChatResponse(
        reply=f"已开始评估 Skill `{skill_id}`。",
        intent="system_action",
        new_run_id=run_id,
        bootstrap_status="accepted",
        staging_path=str(staging_path),
    )


@router.post("/{conv_id}/chat", response_model=ChatResponse)
async def chat(
    conv_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    repo: Annotated[Repository, Depends(get_repo)],
    ds: Annotated[BaseLLMProvider, Depends(get_ds_provider)],
    gemini: Annotated[BaseLLMProvider, Depends(get_gemini_provider)],
) -> ChatResponse:
    message, bundle_zip = await _parse_chat_payload(request)
    conv = repo.get_conversation(conv_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if message.strip() and not _is_internal_user_message(message):
        repo.append_lui_message(conv_id, role="user", content=message)

    conv = repo.get_conversation(conv_id) or {}
    # While awaiting skill-id confirm, never remount ZIP — a lingering attachment
    # would re-enter awaiting_skill_id_confirm and loop the confirm card.
    awaiting_skill_confirm = conv.get("status") == "awaiting_skill_id_confirm"
    confirm_action = (
        is_confirm_message(message) or message.strip() == _ACTION_CONFIRM_SKILL
    )
    if bundle_zip is not None and not (awaiting_skill_confirm and confirm_action):
        zip_resp = await _handle_chat_zip_bootstrap(
            conv_id, message, bundle_zip, repo, ds, gemini, background_tasks
        )
        if zip_resp is not None:
            return zip_resp

    conv = repo.get_conversation(conv_id) or {}
    confirm_resp = await _handle_skill_id_confirm_chat(
        conv_id, message, conv, repo, ds, gemini, background_tasks
    )
    if confirm_resp is not None:
        return confirm_resp

    conv = repo.get_conversation(conv_id) or {}
    propagation_resp = await _handle_propagation_gate_chat(
        conv_id, message, conv, repo, ds, gemini, background_tasks
    )
    if propagation_resp is not None:
        return propagation_resp

    conv = repo.get_conversation(conv_id) or {}
    readiness_resp = await _handle_readiness_choice_chat(
        conv_id, message, conv, repo, ds, gemini, background_tasks
    )
    if readiness_resp is not None:
        return readiness_resp

    conv = repo.get_conversation(conv_id) or {}
    history = repo.get_lui_messages(conv_id)
    was_awaiting_clarify = conv.get("status") == "awaiting_clarify"
    if was_awaiting_clarify and message.strip():
        keys = _pending_clarification_keys(history)
        answers = await parse_clarification_message(message, keys, ds)
        if not answers:
            answers = _parse_clarification_answer(message, keys)
        if answers:
            repo.merge_clarifications(conv_id, answers)
        repo.update_conversation_status(conv_id, "active")
        conv = repo.get_conversation(conv_id) or conv

    check_session_gate(conv_id, repo)
    conv = repo.get_conversation(conv_id) or {}
    active_run_id = conv.get("active_run_id")
    report = repo.get_report(str(active_run_id)) if active_run_id else None
    staging_path = _resolve_staging_path(conv_id, conv, repo)

    lui_agent = LuiAgent(ds_provider=ds)
    lui_resp = await lui_agent.respond(
        conversation_id=conv_id,
        user_message=message,
        history=history,
        report=report,
        conv=conv,
        repo=repo,
        staging_path=staging_path,
    )

    if lui_resp.reply and message != _OPENING_MARKER:
        if lui_resp.intent == "clarify":
            repo.append_lui_message(
                conv_id,
                role="agent",
                content=lui_resp.reply,
                message_type="clarify",
                payload_json={
                    "clarification_keys": lui_resp.clarification_keys or [],
                },
            )
        else:
            repo.append_lui_message(conv_id, role="agent", content=lui_resp.reply)

    writer = StagingWriter(repo=repo)
    new_run_id: str | None = None
    conv_status = conv.get("status")

    if lui_resp.intent == "clarify":
        repo.update_conversation_status(conv_id, "awaiting_clarify")

    if conv_status == "awaiting_clarify" and lui_resp.intent in (
        "mutation",
        "system_action",
    ):
        _raise_clarify_mutation_blocked()

    if conv_status in _PROPAGATION_GATE_STATUSES and lui_resp.intent in (
        "mutation",
        "system_action",
    ):
        _raise_propagation_mutation_blocked()

    if (
        conv.get("status") == "awaiting_draft_confirm"
        and lui_resp.intent == "mutation"
        and not LuiAgent.is_draft_confirmation(message)
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "DRAFT_NOT_CONFIRMED",
                "message": "请先确认修改草案后再写入。可回复「确认」或说明修改意见。",
            },
        )

    if lui_resp.intent == "mutation" and conv_status == "awaiting_clarify":
        _raise_clarify_mutation_blocked()

    if lui_resp.intent == "mutation" and isinstance(lui_resp.patch, dict):
        if conv.get("status") == "awaiting_draft_confirm":
            repo.clear_pending_patch(conv_id)
        result = writer.apply_patch(staging_path=staging_path, patch=lui_resp.patch)
        if result.hash_changed:
            repo.set_conversation_auto_confirmed(conv_id, False)
            new_run_id = await writer.trigger_next_run(
                conv_id=conv_id,
                old_run_id=str(active_run_id or ""),
                staging_path=staging_path,
                skill_id=str(conv.get("skill_id", "")),
                ds_provider=ds,
                gemini_provider=gemini,
                background_tasks=background_tasks,
            )

    if lui_resp.intent == "system_action":
        if message == _CONFIRM_ALL_MARKER and _compute_gap_zero(staging_path):
            repo.set_conversation_auto_confirmed(conv_id, True)
        new_run_id = await writer.trigger_next_run(
            conv_id=conv_id,
            old_run_id=str(active_run_id or ""),
            staging_path=staging_path,
            skill_id=str(conv.get("skill_id", "")),
            ds_provider=ds,
            gemini_provider=gemini,
            background_tasks=background_tasks,
        )

    conv_post = repo.get_conversation(conv_id) or conv
    gap_zero = _compute_gap_zero(staging_path)
    return ChatResponse(
        reply=lui_resp.reply,
        intent=lui_resp.intent,
        new_run_id=new_run_id,
        auto_confirmed=bool(conv_post.get("auto_confirmed")),
        gap_zero=gap_zero,
        bootstrap_status=str(conv_post.get("status") or ""),
    )


@router.post("/{conv_id}/confirm-cases")
async def confirm_cases(
    conv_id: str,
    req: ConfirmCasesRequest,
    repo: Annotated[Repository, Depends(get_repo)],
) -> dict:
    check_session_gate(conv_id, repo)
    conv = repo.get_conversation(conv_id) or {}
    staging_path = _resolve_staging_path(conv_id, conv, repo)
    eval_dir = staging_path / "eval_cases"

    updated: list[str] = []
    for case_id in req.case_ids:
        path = eval_dir / f"{case_id}.yaml"
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            continue
        data["confirmed"] = True
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        updated.append(case_id)

    return {"updated": updated}


@router.get("/{conv_id}/messages")
async def get_messages(
    conv_id: str,
    repo: Annotated[Repository, Depends(get_repo)],
) -> dict:
    return {
        "conversation_id": conv_id,
        "messages": repo.get_lui_messages(conv_id),
    }


@router.get("/{conv_id}/status")
async def get_status(
    conv_id: str,
    repo: Annotated[Repository, Depends(get_repo)],
) -> dict:
    conv = repo.get_conversation(conv_id) or {}
    active_run_id = conv.get("active_run_id")
    active_run = repo.get_run(str(active_run_id)) if active_run_id else None
    lui_count = len(repo.get_lui_messages(conv_id))

    staging_path = _resolve_staging_path(conv_id, conv, repo)
    gap_zero = False
    case_gate_passed = False
    type_coverage: dict = {}
    stage_progress: list[str] = []
    if active_run_id:
        stage_progress = repo.get_stage_progress(str(active_run_id))
    if staging_path.is_dir() and (staging_path / "SKILL.md").is_file():
        bundle = ingest_bundle(str(staging_path))
        gap_zero = _compute_gap_zero(staging_path)
        gate = Level0Checker().check_case_gate(bundle)
        case_gate_passed = bool(gate.get("passed"))
        type_coverage = gate.get("type_coverage", {})

    return {
        "conversation_id": conv_id,
        "status": conv.get("status"),
        "active_run_id": active_run_id,
        "run_status": active_run.get("status") if active_run else None,
        "run_started_at": active_run.get("started_at") if active_run else None,
        "stage_progress": stage_progress,
        "auto_run_count": int(conv.get("auto_run_count", 0)),
        "max_auto_runs": int(conv.get("max_auto_runs", 5)),
        "auto_confirmed": bool(conv.get("auto_confirmed")),
        "lui_messages_count": lui_count,
        "gap_zero": gap_zero,
        "case_gate_passed": case_gate_passed,
        "case_type_coverage": type_coverage,
    }
