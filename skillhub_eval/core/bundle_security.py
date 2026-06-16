"""
Layered bundle security scan — intake (author bundle) vs eval_cases.

Gate / bootstrap blocking uses **intake** only (SKILL.md + scripts).
Propagator-generated eval_cases may contain adversarial phrasing for tests;
those findings are informational and do not block can_enter_formal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skillhub_eval.core.security_scan import SecurityFinding, security_scan

PROPAGATOR_ORIGINS: frozenset[str] = frozenset(
    {"staging_propagator", "staging_propagator_fallback"}
)

FINDING_HINT_ZH: dict[str, str] = {
    "PROMPT_INJECTION": (
        "正文或脚本含提示注入/越狱类表述。"
        "若为 Skill 能力描述，请改为「拒绝此类请求」；"
        "若为评测题且为系统自动生成，可忽略此项。"
    ),
    "DANGEROUS_COMMAND": (
        "含危险命令或 eval/exec/subprocess 等高风险调用。"
        "请改用安全 API，或把示例改为抽象描述。"
    ),
    "HARDCODED_SECRET": "疑似硬编码密钥或 Token，请改为环境变量或配置引用。",
    "UNAUTHORIZED_ACCESS_DESCRIPTION": "描述可能暗示绕过权限或审批，请补充 permission_scope。",
    "NETWORK_REQUEST": "含外呼网络请求描述，请确认数据范围并在 security_notes 中说明。",
}

FINDING_TYPE_ZH: dict[str, str] = {
    "PROMPT_INJECTION": "提示注入风险",
    "DANGEROUS_COMMAND": "危险命令",
    "HARDCODED_SECRET": "硬编码密钥",
    "UNAUTHORIZED_ACCESS_DESCRIPTION": "越权描述",
    "NETWORK_REQUEST": "网络外呼",
}


@dataclass
class BundleSecurityScanResult:
    """Layered scan: intake drives gate; case findings are informational."""

    intake_status: str
    intake_findings: list[dict[str, Any]] = field(default_factory=list)
    case_findings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def security_status(self) -> str:
        """Gate decision — intake only."""
        return self.intake_status

    @property
    def security_findings(self) -> list[dict[str, Any]]:
        """Blocking / warning findings on author bundle (for UI alert)."""
        return list(self.intake_findings)

    def to_gate_dict(self) -> dict[str, Any]:
        return {
            "security_status": self.intake_status,
            "security_findings": self.intake_findings,
            "security_case_findings": self.case_findings,
            "security_block_reason_zh": security_block_reason_zh(self),
        }


def _intake_text(bundle: dict, staging_path: Path) -> str:
    parts: list[str] = [str(bundle.get("skill_md_text") or "")]
    scripts_dir = staging_path / "scripts"
    if scripts_dir.is_dir():
        for path in sorted(scripts_dir.rglob("*.py")):
            try:
                parts.append(path.read_text(encoding="utf-8"))
            except OSError:
                continue
    return "\n".join(parts)


def _case_scan_text(case: dict) -> str:
    return " ".join(
        str(case.get(key, ""))
        for key in ("user_intent", "input_template", "expected_behavior", "type")
    )


def _finding_to_dict(
    finding: SecurityFinding,
    *,
    source: str,
    case_id: str | None = None,
    origin: str | None = None,
    downgraded: bool = False,
) -> dict[str, Any]:
    hint = FINDING_HINT_ZH.get(finding.finding_type, "请检查并修改相关内容后重试。")
    label = FINDING_TYPE_ZH.get(finding.finding_type, finding.finding_type)
    entry: dict[str, Any] = {
        "group_id": finding.group_id,
        "finding_type": finding.finding_type,
        "finding_type_zh": label,
        "result_status": finding.result_status,
        "matched_text": finding.matched_text,
        "source": source,
        "hint_zh": hint,
    }
    if case_id:
        entry["case_id"] = case_id
    if origin:
        entry["origin"] = origin
    if downgraded:
        entry["downgraded"] = True
        entry["result_status"] = "info"
        entry["note_zh"] = "系统自动生成的评测题攻击描述，不阻断正式评估。"
    return entry


def _scan_eval_cases(bundle: dict) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for case in bundle.get("eval_cases") or []:
        if not isinstance(case, dict):
            continue
        text = _case_scan_text(case)
        if not text.strip():
            continue
        case_id = str(case.get("id") or "unknown")
        origin = str(case.get("origin") or "")
        result = security_scan(text)
        if not result.findings:
            continue
        is_propagator = origin in PROPAGATOR_ORIGINS
        for finding in result.findings:
            downgraded = is_propagator and finding.result_status == "blocked"
            findings.append(
                _finding_to_dict(
                    finding,
                    source=f"eval_cases/{case_id}",
                    case_id=case_id,
                    origin=origin or None,
                    downgraded=downgraded,
                )
            )
    return findings


def scan_bundle_security(bundle: dict, staging_path: Path) -> BundleSecurityScanResult:
    """Scan author intake (SKILL + scripts) and eval_cases separately."""
    intake = security_scan(_intake_text(bundle, staging_path))
    intake_findings = [
        _finding_to_dict(f, source="skill_bundle") for f in intake.findings
    ]
    case_findings = _scan_eval_cases(bundle)
    return BundleSecurityScanResult(
        intake_status=intake.status,
        intake_findings=intake_findings,
        case_findings=case_findings,
    )


def gate_security_kwargs(scan: BundleSecurityScanResult) -> dict[str, Any]:
    """Keyword args for build_assessment_gate_payload from a layered scan."""
    data = scan.to_gate_dict()
    return {
        "security_status": data["security_status"],
        "security_findings": data["security_findings"],
        "security_case_findings": data["security_case_findings"],
        "security_block_reason_zh": data["security_block_reason_zh"],
    }


def security_block_reason_zh(scan: BundleSecurityScanResult) -> str | None:
    if scan.intake_status != "blocked":
        return None
    n = len(scan.intake_findings)
    if n == 0:
        return "安全门禁未通过：Skill 正文或脚本命中安全规则，无法自动开始正式评估。"
    types = "、".join(
        dict.fromkeys(
            f.get("finding_type_zh") or f.get("finding_type", "")
            for f in scan.intake_findings
        )
    )
    return (
        f"安全门禁未通过（{n} 项：{types}）。"
        "请修改 Skill 正文或 scripts/ 后重试；评测题中的攻击描述不会单独阻断开评。"
    )
