"""
Gaps scanner — structured gap checklist for awaiting_confirm / author补全.

T2: detects structural and metadata gaps without embedding copy-paste templates
(templates live in testskills/_templates/ and UI — Task 3).
"""

from __future__ import annotations

from pathlib import Path

from .schemas.enums import CASE_COUNT_GATES, BundleState, RiskLevel

SECURITY_FIELDS: tuple[str, ...] = (
    "negative_prompts",
    "error_handling",
    "permission_scope",
    "security_notes",
)


def _gap(
    field_path: str,
    severity: str,
    message: str,
    *,
    draft_value: str | None = None,
    confirmed: bool = False,
) -> dict:
    return {
        "field_path": field_path,
        "severity": severity,
        "message": message,
        "draft_value": draft_value,
        "confirmed": confirmed,
    }


def scan_gaps(
    bundle: dict,
    bundle_state: BundleState,
    *,
    confirmed_field_paths: frozenset[str] | None = None,
) -> dict:
    """
    Scan a Skill bundle for gaps blocking full capability evaluation.

    Returns:
        dict with ``gaps`` (list of gap objects) and ``required_actions``
        (human-readable next steps). Does NOT include template file bodies.
    """
    confirmed = confirmed_field_paths or frozenset()
    gaps: list[dict] = []
    required_actions: list[str] = []

    meta = bundle.get("skill_meta") or {}
    bundle_path = Path(bundle.get("bundle_path", ""))
    eval_cases_dir = bundle_path / "eval_cases"
    has_eval_cases_dir = eval_cases_dir.is_dir()

    # ── description ───────────────────────────────────────────────────────────
    if not meta.get("description"):
        gaps.append(_gap(
            "description",
            "warn",
            "SKILL.md frontmatter 缺少 description，建议补充技能用途说明",
        ))
        required_actions.append("在 SKILL.md frontmatter 中填写 description 字段")

    # ── risk_level declaration ────────────────────────────────────────────────
    if not bundle.get("risk_level_declared"):
        gaps.append(_gap(
            "risk_level",
            "info",
            "未显式声明 risk_level，系统将默认按 low 处理；建议显式声明",
        ))
        required_actions.append("在 SKILL.md frontmatter 中添加 risk_level: low|medium|high")

    risk_raw = bundle.get("risk_level_declared")
    try:
        risk = RiskLevel(risk_raw) if risk_raw else RiskLevel.low
    except ValueError:
        risk = RiskLevel.low

    min_cases, ceiling = CASE_COUNT_GATES[risk]
    n_cases = bundle.get("n_cases", 0)

    # ── eval_cases directory ──────────────────────────────────────────────────
    if not has_eval_cases_dir:
        gaps.append(_gap(
            "eval_cases",
            "block",
            "缺少 eval_cases/ 目录，无法进行 Capability 评审",
        ))
        required_actions.append(
            f"创建 eval_cases/ 目录并添加至少 {min_cases} 个用例文件（risk={risk.value}）"
        )
    elif n_cases < min_cases:
        missing = min_cases - n_cases
        gaps.append(_gap(
            "eval_cases.count",
            "block",
            f"risk_level={risk.value} 需要 >= {min_cases} 个用例，当前 {n_cases} 个，"
            f"还需补充 {missing} 个",
        ))
        required_actions.append(
            f"在 eval_cases/ 中再添加 {missing} 个用例（当前 {n_cases}/{min_cases}）"
        )
    elif n_cases > ceiling:
        excess = n_cases - ceiling
        gaps.append(_gap(
            "eval_cases.count",
            "block",
            f"risk_level={risk.value} MVP 上限为 {ceiling} 个用例，当前 {n_cases} 个，"
            f"需移除 {excess} 个",
        ))
        required_actions.append(
            f"从 eval_cases/ 中移除 {excess} 个用例（当前 {n_cases}/{ceiling}）"
        )

    # ── sample_io for L1 path (no Python scripts) ─────────────────────────────
    if not bundle.get("has_scripts") and not bundle.get("has_sample_io"):
        gaps.append(_gap(
            "sample_io",
            "block",
            "无 Python 脚本时需 sample_io/ 目录提供 Level 1 样例输出",
        ))
        required_actions.append(
            "创建 sample_io/ 目录，为每个 eval case 添加对应 JSON 样例输出"
        )

    # ── security fields (confirmed via POST /bundle/{id}/confirm) ─────────────
    for field in SECURITY_FIELDS:
        if field in confirmed:
            continue
        gaps.append(_gap(
            field,
            "warn",
            f"安全敏感字段 {field} 尚未作者确认",
            confirmed=False,
        ))
        required_actions.append(f"在补全台确认或填写 {field} 字段")

    # bundle_state hint for authors upgrading from minimal
    if bundle_state == BundleState.minimal:
        required_actions.append(
            "结构文件保存至 Bundle 路径后，以 bundle_state=confirmed + "
            "evaluation_mode=capability_full 重新发起评估"
        )

    return {
        "gaps": gaps,
        "required_actions": required_actions,
    }
