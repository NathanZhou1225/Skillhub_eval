"""Rich Report chat notifications — Wave 5 / 5.1."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from skillhub_eval.core.gaps import scan_gaps
from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.core.level0 import Level0Checker
from skillhub_eval.core.ports import Repository
from skillhub_eval.core.schemas import BundleState, EvaluationMode
from skillhub_eval.core.stage_timing import summarize_stage_timings
from skillhub_eval.settings import settings

_STATUS_SUMMARY: dict[str, str] = {
    "awaiting_confirm": "初评暂停，待补全",
    "completed": "评估完成",
    "awaiting_human_review": "正式评估完成，待专家复核",
    "failed": "评估失败",
}

_TERMINAL_FOR_NARRATIVE = frozenset(
    {"completed", "awaiting_human_review", "awaiting_confirm", "failed"}
)
_TERMINAL_OK_FOR_AUTO_FORMAL = frozenset({"completed", "awaiting_human_review"})


def _parse_reason_codes(run: dict) -> list:
    raw = run.get("reason_codes")
    if not raw:
        return []
    try:
        return json.loads(raw) if isinstance(raw, str) else list(raw)
    except (TypeError, json.JSONDecodeError):
        return []


def _resolve_staging_path(conversation_id: str, conv: dict, run: dict) -> Path:
    run_path = run.get("skill_bundle_path")
    if run_path:
        return Path(str(run_path))
    return Path(settings.staging_root) / conversation_id


_BLOCKING_GAP_SEVERITIES = frozenset({"required", "block"})
_OPTIONAL_GAP_SEVERITIES = frozenset({"warn", "info"})

_SECURITY_STATUS_ZH = {
    "passed": "通过",
    "warning": "警告",
    "blocked": "已拦截",
    "unknown": "未知",
}

_RISK_LEVEL_ZH = {
    "low": "低",
    "medium": "中",
    "high": "高",
}


def split_gaps_by_severity(gaps: list[dict]) -> tuple[list[dict], list[dict]]:
    blocking: list[dict] = []
    optional: list[dict] = []
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        severity = str(gap.get("severity", ""))
        if severity in _BLOCKING_GAP_SEVERITIES:
            blocking.append(gap)
        elif severity in _OPTIONAL_GAP_SEVERITIES:
            optional.append(gap)
    return blocking, optional


def compute_gap_zero(staging_path: Path) -> bool:
    bundle = ingest_bundle(str(staging_path))
    gaps = scan_gaps(bundle, BundleState.draft_enriched)
    return not any(
        g.get("severity") in _BLOCKING_GAP_SEVERITIES for g in gaps.get("gaps", [])
    )


def has_optional_improvement_gaps(staging_path: Path) -> bool:
    bundle = ingest_bundle(str(staging_path))
    gaps = scan_gaps(bundle, BundleState.draft_enriched)
    return any(
        g.get("severity") in _OPTIONAL_GAP_SEVERITIES for g in gaps.get("gaps", [])
    )


def compute_case_gate(staging_path: Path) -> dict:
    bundle = ingest_bundle(str(staging_path))
    return Level0Checker().check_case_gate(bundle)


def _resolve_report_phase(run: dict, status: str) -> str:
    mode = str(run.get("evaluation_mode", ""))
    if mode == "degraded":
        return "initial"
    if status == "awaiting_human_review":
        return "formal_pending_review"
    if mode == "capability_full":
        return "formal"
    return "initial"


def _headline_for_phase(phase: str) -> str:
    return {
        "initial": "初评结果",
        "formal": "正式评估结果",
        "formal_pending_review": "正式评估·待专家复核",
    }.get(phase, "评估结果")


def _summary_one_liner(report: dict | None) -> str:
    if not report:
        return "评估已完成，可查看完整报告了解详情。"
    summary = report.get("skill_summary") or {}
    verdict = summary.get("overall_verdict")
    if isinstance(verdict, str) and verdict.strip():
        return verdict.strip()[:200]
    strengths = summary.get("strengths")
    if isinstance(strengths, list) and strengths:
        first = strengths[0]
        if isinstance(first, str) and first.strip():
            return first.strip()[:200]
    legacy = summary.get("highlights")
    if isinstance(legacy, str) and legacy.strip():
        return legacy.strip()[:200]
    narrative = report.get("narrative") or {}
    headline = narrative.get("headline_zh") or narrative.get("headline")
    if isinstance(headline, str) and headline.strip():
        return headline.strip()[:200]
    return "评估已完成，可查看完整报告了解详情。"


def _needs_human_review_gate(run: dict, conv: dict | None = None) -> bool:
    status = str(run.get("status", ""))
    if status == "awaiting_human_review":
        return True
    if conv and str(conv.get("status", "")) == "frozen":
        return True
    return False


def _resolve_verdict(
    run: dict,
    report: dict | None,
    *,
    conv: dict | None = None,
) -> tuple[str, str]:
    """Returns (verdict_zh, verdict_badge_class). GQ5 / GQ14 mapping."""
    if _needs_human_review_gate(run, conv):
        return "需人工复核", "warn"

    review_status = str(run.get("review_status") or (report or {}).get("review_status") or "")
    if review_status == "fail":
        return "未通过", "fail"
    if review_status == "pass":
        return "通过", "pass"
    if review_status == "warn":
        return "通过（有改进建议）", "pass_warn"
    return "通过（有改进建议）", "pass_warn"


def _resolve_next_action(
    run: dict,
    report: dict | None,
    verdict_zh: str,
    *,
    conv: dict | None = None,
) -> str:
    if _needs_human_review_gate(run, conv):
        return "请等待专家裁定；作者暂不可改包"
    if verdict_zh == "未通过":
        return "请按完整报告修改后重新评估"
    if verdict_zh == "通过":
        return "已达到上架标准，可进入后续上架流程"
    return "建议按报告优化后再次提交"


def _build_score_line_html(run: dict, report: dict | None, phase: str) -> str | None:
    if phase == "initial":
        return None
    score = run.get("score_total")
    source = (
        (report or {}).get("score_total_source")
        or run.get("score_total_source")
        or ""
    )
    if score is None:
        if source == "not_applicable":
            return "综合得分：本次不适用"
        return "综合得分：暂不可用"
    try:
        return f"综合得分：<strong>{float(score):.1f}</strong>"
    except (TypeError, ValueError):
        return "综合得分：暂不可用"


def _build_actions(
    *,
    human_review_required: bool,
    run_status: str,
    report_phase: str,
) -> list[dict]:
    actions: list[dict] = []
    if report_phase in ("formal", "formal_pending_review"):
        actions.append(
            {
                "id": "openRunDetail",
                "label": "查看完整报告 →",
                "visible_in": "author",
                "enabled": True,
            }
        )
    if report_phase != "formal_pending_review":
        return actions
    expert_enabled = bool(human_review_required) and run_status == "awaiting_human_review"
    actions.extend(
        [
            {
                "id": "expert_approve",
                "label": "批准",
                "visible_in": "expert",
                "enabled": expert_enabled,
            },
            {
                "id": "expert_reject",
                "label": "驳回",
                "visible_in": "expert",
                "enabled": expert_enabled,
            },
        ]
    )
    return actions


def build_rich_report_payload(run_id: str, repo: Repository) -> dict:
    """Assemble rich_report payload aligned with GET /eval/report/{run_id}."""
    run = repo.get_run(run_id)
    if run is None:
        raise ValueError(f"run_id '{run_id}' not found")

    report = repo.get_report(run_id)
    reason_codes = _parse_reason_codes(run)
    status = str(run["status"])

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

    report_phase = _resolve_report_phase(run, status)
    headline_zh = _headline_for_phase(report_phase)
    summary_one_liner = _summary_one_liner(report)
    score_line_html = _build_score_line_html(run, report, report_phase)

    conv_id = run.get("conversation_id")
    conv: dict = {}
    gap_zero = False
    case_gate_passed = False
    auto_confirmed = False
    if conv_id:
        conv = repo.get_conversation(str(conv_id)) or {}
        staging_path = _resolve_staging_path(str(conv_id), conv, run)
        try:
            gap_zero = compute_gap_zero(staging_path)
            case_gate = compute_case_gate(staging_path)
            case_gate_passed = bool(case_gate.get("passed"))
        except Exception:
            gap_zero = False
            case_gate_passed = False
        auto_confirmed = bool(conv.get("auto_confirmed"))

    payload: dict = {
        "run_id": run_id,
        "conversation_id": conv_id,
        "status": status,
        "review_status": run.get("review_status"),
        "evaluation_mode": run.get("evaluation_mode"),
        "report_phase": report_phase,
        "headline_zh": headline_zh,
        "summary_one_liner": summary_one_liner,
        "score_line_html": score_line_html,
        "score_total": run.get("score_total"),
        "score_total_source": (
            report.get("score_total_source") if report else run.get("score_total_source")
        ),
        "reason_codes": reason_codes,
        "human_review_required": bool(run.get("human_review_required")),
        "gap_zero": gap_zero,
        "case_gate_passed": case_gate_passed,
        "auto_confirmed": auto_confirmed,
        "provider_summary": provider_summary,
        "provider_errors": provider_errors,
        "stage_timings": stage_timings,
        "timing_summary": timing_summary,
        "stage_progress": stage_progress,
        "report": report,
        "actions": _build_actions(
            human_review_required=bool(run.get("human_review_required")),
            run_status=status,
            report_phase=report_phase,
        ),
    }
    if report_phase in ("formal", "formal_pending_review"):
        verdict_zh, verdict_badge_class = _resolve_verdict(run, report, conv=conv)
        payload["verdict_zh"] = verdict_zh
        payload["verdict_badge_class"] = verdict_badge_class
        payload["next_action_zh"] = _resolve_next_action(
            run, report, verdict_zh, conv=conv
        )
    return payload


def _rich_report_summary(status: str, review_status: str | None, report_phase: str) -> str:
    if report_phase == "initial":
        base = "初评完成"
    elif report_phase == "formal_pending_review":
        base = _STATUS_SUMMARY.get("awaiting_human_review", "正式评估完成，待专家复核")
    elif report_phase == "formal":
        base = _STATUS_SUMMARY.get("completed", "正式评估完成")
    else:
        base = _STATUS_SUMMARY.get(status, f"评估状态：{status}")
    if review_status and status in ("completed", "awaiting_human_review"):
        return f"{base}（{review_status}）"
    return base


def append_rich_report_message(
    conversation_id: str,
    run_id: str,
    repo: Repository,
) -> None:
    """Append rich_report agent bubble; idempotent per (conversation_id, run_id)."""
    if repo.has_rich_report_for_run(conversation_id, run_id):
        return

    payload = build_rich_report_payload(run_id, repo)
    content = _rich_report_summary(
        str(payload.get("status", "")),
        payload.get("review_status"),
        str(payload.get("report_phase", "")),
    )
    repo.append_lui_message(
        conversation_id,
        role="agent",
        content=content,
        run_id=run_id,
        message_type="rich_report",
        payload_json=payload,
    )


def _has_message_type_for_run(
    conversation_id: str,
    run_id: str,
    message_type: str,
    repo: Repository,
) -> bool:
    messages = repo.get_lui_messages(conversation_id)
    return any(
        str(msg.get("run_id")) == run_id and msg.get("message_type") == message_type
        for msg in messages
    )


def append_readiness_result_message(
    conversation_id: str,
    run_id: str,
    repo: Repository,
) -> None:
    """Append degraded readiness_result bubble; idempotent per run."""
    if _has_message_type_for_run(conversation_id, run_id, "readiness_result", repo):
        return
    run = repo.get_run(run_id)
    if not run:
        return
    report = repo.get_report(run_id) or {}
    conv = repo.get_conversation(conversation_id) or {}
    staging_path = _resolve_staging_path(conversation_id, conv, run)

    gaps = list(report.get("gaps") or [])
    required_actions = list(report.get("required_actions") or [])
    try:
        bundle = ingest_bundle(str(staging_path))
        from skillhub_eval.core.gaps import scan_gaps

        scanned = scan_gaps(bundle, BundleState.draft_enriched)
        gaps = list(scanned.get("gaps") or gaps)
        required_actions = list(scanned.get("required_actions") or required_actions)
    except Exception:
        pass
    completeness_score = report.get("completeness_score")
    security_status = report.get("security_status") or run.get("security_status") or "unknown"
    risk_level_locked = (
        report.get("risk_level_locked")
        or run.get("risk_level_locked")
        or "low"
    )

    case_gate: dict[str, Any] = {"passed": False, "type_coverage": {}}
    gap_zero = False
    try:
        gap_zero = compute_gap_zero(staging_path)
        gate = compute_case_gate(staging_path)
        case_gate = {
            "passed": bool(gate.get("passed")),
            "type_coverage": gate.get("type_coverage") or {},
        }
    except Exception:
        case_gate = {
            "passed": False,
            "type_coverage": report.get("case_type_coverage") or {},
        }
        blocking = {"required", "block"}
        gap_zero = not any(g.get("severity") in blocking for g in gaps)

    can_enter_formal = bool(gap_zero and case_gate.get("passed"))
    blocking_gaps, optional_gaps = split_gaps_by_severity(gaps)
    needs_readiness_choice = bool(can_enter_formal and optional_gaps)
    security_zh = _SECURITY_STATUS_ZH.get(str(security_status), str(security_status))
    risk_zh = _RISK_LEVEL_ZH.get(str(risk_level_locked), str(risk_level_locked))
    headline_zh = "初评就绪结果"
    body_sections = [
        {
            "key": "security",
            "title": "安全与风险",
            "lines": [
                f"security_status: {security_status}",
                f"risk_level_locked: {risk_level_locked}",
            ],
        },
        {
            "key": "readiness",
            "title": "完整性与门槛",
            "lines": [
                f"completeness_score: {completeness_score}",
                f"gap_zero: {gap_zero}",
                f"case_gate_passed: {bool(case_gate.get('passed'))}",
                f"can_enter_formal: {can_enter_formal}",
            ],
        },
        {
            "key": "actions",
            "title": "下一步建议",
            "lines": required_actions,
        },
    ]
    payload = {
        "run_id": run_id,
        "gaps": gaps,
        "blocking_gaps": blocking_gaps,
        "optional_gaps": optional_gaps,
        "required_actions": required_actions,
        "security_status": security_status,
        "security_status_zh": security_zh,
        "risk_level_locked": risk_level_locked,
        "risk_level_locked_zh": risk_zh,
        "case_gate": case_gate,
        "completeness_score": completeness_score,
        "gap_zero": gap_zero,
        "can_enter_formal": can_enter_formal,
        "needs_readiness_choice": needs_readiness_choice,
        "headline_zh": headline_zh,
        "body_sections": body_sections,
    }
    content = (
        "初评已完成。评估条件已达标；下方有可选改进项，你可先补充说明文档，或直接进入正式评估。"
        if needs_readiness_choice
        else "初评体检已完成，请按建议补齐后进入正式评估。"
    )
    repo.append_lui_message(
        conversation_id,
        role="agent",
        content=content,
        run_id=run_id,
        message_type="readiness_result",
        payload_json=payload,
    )


class _InlineBackgroundTasks:
    """Schedule engine.run_async from within an active asyncio loop."""

    def add_task(self, fn: Any, *args: Any, **kwargs: Any) -> None:
        asyncio.create_task(fn(*args, **kwargs))


async def start_capability_full_eval(
    conv_id: str,
    skill_id: str,
    staging_path: Path,
    repo: Repository,
    ds_provider: Any,
    gemini_provider: Any,
    background_tasks: Any,
    *,
    parent_run_id: str | None = None,
) -> str | None:
    """Start capability_full directly (Wave 5.3.2 — no degraded parent required)."""
    conv = repo.get_conversation(conv_id) or {}
    if conv.get("status") == "frozen":
        return None

    auto_run_count = int(conv.get("auto_run_count", 0))
    max_auto_runs = int(conv.get("max_auto_runs", 5))
    if auto_run_count >= max_auto_runs:
        active = str(conv.get("active_run_id") or parent_run_id or "")
        if active:
            from skillhub_eval.core.staging_writer import StagingWriter

            StagingWriter(repo)._freeze_and_escalate(conv_id, active)
        return None

    repo.set_conversation_auto_confirmed(conv_id, True)
    repo.update_conversation_status(conv_id, "active")
    repo.increment_auto_run_count(conv_id)

    new_run_id = repo.create_run(
        skill_id=skill_id,
        skill_bundle_path=str(staging_path),
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
        parent_run_id=parent_run_id,
    )
    if parent_run_id:
        repo.supersede_run(parent_run_id, new_run_id)

    from skillhub_eval.core.engine import EvaluationEngine

    engine = EvaluationEngine(
        repo=repo,
        ds_provider=ds_provider,
        wb_provider=gemini_provider,
    )
    background_tasks.add_task(
        engine.run_async,
        run_id=new_run_id,
        skill_bundle_path=str(staging_path),
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
    )
    repo.append_lui_message(
        conv_id,
        role="agent",
        content="评估需求已满足，正在开始正式双模型评估，请稍候…",
    )
    return new_run_id


async def start_formal_eval_from_readiness(
    conv_id: str,
    run_id: str,
    repo: Repository,
    ds_provider: Any,
    gemini_provider: Any,
    *,
    background_tasks: Any | None = None,
) -> str | None:
    """Trigger capability_full after user skips optional improvements or auto path."""
    run = repo.get_run(run_id)
    if not run:
        return None
    conv = repo.get_conversation(conv_id) or {}
    staging_path = _resolve_staging_path(conv_id, conv, run)
    repo.set_conversation_auto_confirmed(conv_id, True)
    repo.update_conversation_status(conv_id, "active")
    from skillhub_eval.core.staging_writer import StagingWriter

    writer = StagingWriter(repo=repo)
    tasks = background_tasks or _InlineBackgroundTasks()
    return await writer.trigger_next_run(
        conv_id=conv_id,
        old_run_id=run_id,
        staging_path=staging_path,
        skill_id=str(run.get("skill_id", conv.get("skill_id", ""))),
        ds_provider=ds_provider,
        gemini_provider=gemini_provider,
        background_tasks=tasks,
    )


async def maybe_auto_start_formal_eval(
    conv_id: str,
    run_id: str,
    repo: Repository,
    ds_provider: Any,
    gemini_provider: Any,
) -> str | None:
    """Auto-trigger capability_full when initial (degraded) review passes structure gates."""
    run = repo.get_run(run_id)
    if not run or run.get("evaluation_mode") != "degraded":
        return None
    if run.get("status") not in _TERMINAL_OK_FOR_AUTO_FORMAL:
        return None

    conv = repo.get_conversation(conv_id) or {}
    if conv.get("auto_confirmed"):
        return None
    if conv.get("status") == "frozen":
        return None

    staging_path = _resolve_staging_path(conv_id, conv, run)
    try:
        if not (compute_gap_zero(staging_path) and compute_case_gate(staging_path).get("passed")):
            return None
    except Exception:
        return None

    return await start_formal_eval_from_readiness(
        conv_id,
        run_id,
        repo,
        ds_provider,
        gemini_provider,
    )


async def on_run_terminal_chat_notifications(
    run_id: str,
    repo: Repository,
    ds_provider: Any = None,
    gemini_provider: Any = None,
) -> None:
    """GQ4: narrative first, then rich_report; auto formal eval after initial pass."""
    run = repo.get_run(run_id)
    if not run or not run.get("conversation_id"):
        return

    conv_id = str(run["conversation_id"])
    status = str(run.get("status", ""))
    eval_mode = str(run.get("evaluation_mode", ""))

    if status not in _TERMINAL_FOR_NARRATIVE:
        return

    from skillhub_eval.core.lui_agent import LuiAgent

    agent = LuiAgent(ds_provider=ds_provider) if ds_provider else None

    if eval_mode == "degraded":
        if agent is not None:
            await agent.handle_post_initial_review(
                conversation_id=conv_id,
                run_id=run_id,
                repo=repo,
            )
        else:
            LuiAgent.compose_post_initial_narrative_template(
                conversation_id=conv_id,
                run_id=run_id,
                repo=repo,
            )
    elif eval_mode == "capability_full" and status in _TERMINAL_OK_FOR_AUTO_FORMAL:
        narrative = (
            await agent.compose_post_formal_narrative(run_id, repo)
            if agent is not None
            else LuiAgent.compose_post_formal_narrative_template(run_id, repo)
        )
        if narrative:
            repo.append_lui_message(conv_id, role="agent", content=narrative)

    if eval_mode == "degraded":
        append_readiness_result_message(conv_id, run_id, repo)
    else:
        append_rich_report_message(conv_id, run_id, repo)

    if eval_mode == "degraded" and ds_provider and gemini_provider:
        await maybe_auto_start_formal_eval(
            conv_id, run_id, repo, ds_provider, gemini_provider
        )
