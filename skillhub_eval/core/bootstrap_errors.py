"""User-facing bootstrap failure messages (security gate, upload errors)."""

from __future__ import annotations

from typing import Any

from skillhub_eval.core.bundle_security import (
    BundleSecurityScanResult,
    security_block_reason_zh,
)
from skillhub_eval.core.ports import Repository


def is_security_blocked_detail(detail: Any) -> bool:
    return isinstance(detail, dict) and detail.get("security_status") == "blocked"


def security_blocked_gate_payload(detail: dict[str, Any]) -> dict[str, Any]:
    findings = detail.get("security_findings") or []
    scan = BundleSecurityScanResult(intake_status="blocked", intake_findings=findings)
    return {
        "security_status": "blocked",
        "security_status_zh": "已拦截",
        "security_findings": findings,
        "security_case_findings": detail.get("security_case_findings") or [],
        "security_block_reason_zh": (
            detail.get("security_block_reason_zh") or security_block_reason_zh(scan)
        ),
    }


def format_bootstrap_failure_reply(detail: Any) -> str:
    """Short reply for ChatResponse / toast — avoids raw dict dumps."""
    if is_security_blocked_detail(detail):
        payload = security_blocked_gate_payload(detail)
        reason = payload.get("security_block_reason_zh") or "安全门禁未通过。"
        return (
            f"评估未能启动：{reason} "
            "请查看对话中的具体问题说明，修改 Skill 正文或 scripts/ 后重新上传。"
        )
    if isinstance(detail, dict):
        for key in ("message", "detail", "error"):
            if detail.get(key):
                return f"评估启动失败：{detail[key]}"
        return "评估启动失败，请检查上传的 Skill 包后重试。"
    return f"评估启动失败：{detail}"


def append_bootstrap_failure(
    repo: Repository,
    conversation_id: str,
    detail: Any,
    *,
    role: str = "agent",
) -> None:
    """Persist a bootstrap failure in chat — structured card for security blocks."""
    if is_security_blocked_detail(detail):
        payload = security_blocked_gate_payload(detail)
        repo.append_lui_message(
            conversation_id,
            role=role,
            content=(
                "评估未能启动：安全门禁未通过，Skill 正文或脚本存在不合规内容。"
                "详见下方说明。"
            ),
            message_type="security_blocked",
            payload_json=payload,
        )
        return
    repo.append_lui_message(
        conversation_id,
        role="system",
        content=format_bootstrap_failure_reply(detail),
    )
