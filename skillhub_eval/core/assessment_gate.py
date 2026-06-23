"""
Synchronous assessment requirement gate — Wave 5.3.2.

Replaces author-path degraded run for readiness; runs before补题 plan.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillhub_eval.core.case_sanitizer import SanitizerResult
from skillhub_eval.core.chat_notifications import (
    compute_case_gate,
    compute_gap_zero,
    split_gaps_by_severity,
)

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
from skillhub_eval.core.gaps import scan_gaps
from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.core.ports import Repository
from skillhub_eval.core.propagation_plan import detect_l0_clarifications
from skillhub_eval.core.risk_lock import scan_risk
from skillhub_eval.core.schemas import BundleState, RiskLevel


def calc_completeness_score(bundle: dict) -> float:
    score = 100.0
    if not bundle.get("has_sample_io"):
        score -= 15.0
    if not (bundle.get("skill_meta") or {}).get("description"):
        score -= 10.0
    return max(0.0, score)


def build_assessment_gate_payload(
    *,
    staging_path: Path,
    bundle: dict,
    sanitizer_result: SanitizerResult | None = None,
    security_status: str = "unknown",
    security_findings: list[dict] | None = None,
    security_case_findings: list[dict] | None = None,
    security_block_reason_zh: str | None = None,
    gate_version: int = 1,
    run_id: str | None = None,
    clarifications: dict | None = None,
) -> dict[str, Any]:
    gaps_data = scan_gaps(bundle, BundleState.draft_enriched)
    gaps = list(gaps_data.get("gaps") or [])
    required_actions = list(gaps_data.get("required_actions") or [])
    blocking_gaps, optional_gaps = split_gaps_by_severity(gaps)

    gap_zero = compute_gap_zero(staging_path)
    gate = compute_case_gate(staging_path)
    case_gate = {
        "passed": bool(gate.get("passed")),
        "type_coverage": gate.get("type_coverage") or {},
    }

    declared = str(bundle.get("risk_level_declared") or "low")
    try:
        risk_locked = scan_risk(
            str(bundle.get("skill_md_text") or ""),
            RiskLevel(declared),
        )
        risk_level_locked = risk_locked.value
    except (ValueError, KeyError):
        risk_level_locked = declared

    needs_case_propagation = bool(
        sanitizer_result.needs_propagation if sanitizer_result else False
    )
    l0_questions = (
        detect_l0_clarifications(
            bundle,
            sanitizer_result,
            clarifications=clarifications,
        )
        if sanitizer_result
        else []
    )
    has_l0_pending = bool(l0_questions)

    can_enter_formal = bool(
        gap_zero
        and case_gate.get("passed")
        and not needs_case_propagation
        and not has_l0_pending
        and security_status != "blocked"
    )

    security_zh = _SECURITY_STATUS_ZH.get(str(security_status), str(security_status))
    risk_zh = _RISK_LEVEL_ZH.get(str(risk_level_locked), str(risk_level_locked))
    intake_findings = list(security_findings or [])
    case_findings = list(security_case_findings or [])
    block_reason = security_block_reason_zh
    if block_reason is None and security_status == "blocked":
        from skillhub_eval.core.bundle_security import (
            BundleSecurityScanResult,
            security_block_reason_zh as _block_reason_fn,
        )

        block_reason = _block_reason_fn(
            BundleSecurityScanResult(
                intake_status=security_status,
                intake_findings=intake_findings,
                case_findings=case_findings,
            )
        )

    return {
        "run_id": run_id,
        "gate_version": gate_version,
        "execution_source": bundle.get("execution_source"),
        "gaps": gaps,
        "blocking_gaps": blocking_gaps,
        "optional_gaps": optional_gaps,
        "required_actions": required_actions,
        "security_status": security_status,
        "security_status_zh": security_zh,
        "security_findings": intake_findings,
        "security_case_findings": case_findings,
        "security_block_reason_zh": block_reason,
        "risk_level_locked": risk_level_locked,
        "risk_level_locked_zh": risk_zh,
        "case_gate": case_gate,
        "completeness_score": calc_completeness_score(bundle),
        "gap_zero": gap_zero,
        "can_enter_formal": can_enter_formal,
        "needs_case_propagation": needs_case_propagation,
        "has_l0_pending": has_l0_pending,
        "needs_readiness_choice": False,
        "headline_zh": "评估条件检查",
    }


def gate_content_message(payload: dict[str, Any]) -> str:
    if payload.get("security_status") == "blocked":
        reason = payload.get("security_block_reason_zh")
        if reason:
            return reason
        n = len(payload.get("security_findings") or [])
        return (
            f"安全门禁未通过（{n} 项），无法自动开始正式评估。"
            "请查看下方红色说明并修改 Skill 正文或脚本。"
        )
    if payload.get("can_enter_formal"):
        optional = payload.get("optional_gaps") or []
        if optional:
            return (
                "评估需求已满足，正式评估即将开始。"
                f"（另有 {len(optional)} 项可选改进，不阻断本次评估。）"
            )
        return "评估需求已满足，正式评估即将开始，请稍候…"
    if payload.get("needs_case_propagation"):
        return (
            "当前不满足正式评估的题型要求，需补充评测案例。"
            "请查看下方「评估材料补充」并选择补全方式。"
        )
    if payload.get("has_l0_pending"):
        return "尚有评估需求待澄清，请先在下方回复后再继续。"
    blocking = payload.get("blocking_gaps") or []
    if blocking:
        return "尚有必须补齐的评估条件，请按下方说明处理后再继续。"
    return "评估条件检查完成，请按下方说明继续。"


def append_assessment_gate_message(
    conversation_id: str,
    repo: Repository,
    payload: dict[str, Any],
    *,
    gate_version: int | None = None,
) -> None:
    version = int(gate_version or payload.get("gate_version") or 1)
    payload = {**payload, "gate_version": version}
    repo.append_lui_message(
        conversation_id,
        role="agent",
        content=gate_content_message(payload),
        run_id=payload.get("run_id"),
        message_type="assessment_gate_result",
        payload_json=payload,
    )


def next_gate_version(repo: Repository, conversation_id: str) -> int:
    messages = repo.get_lui_messages(conversation_id)
    versions = [
        int((m.get("payload_json") or {}).get("gate_version") or 0)
        for m in messages
        if m.get("message_type") in ("assessment_gate_result", "readiness_result")
    ]
    return max(versions, default=0) + 1
