"""
Propagation plan builder — Wave 5.2.

Deterministic payload for propagation_plan LUI messages and L0 clarification
triggers before deferred CasePropagator execution.
"""

from __future__ import annotations

from pathlib import Path

from skillhub_eval.core.case_sanitizer import SanitizerResult
from skillhub_eval.core.propagator import TYPE_DESCRIPTIONS
from skillhub_eval.core.schemas.enums import CASE_TYPE_REQUIREMENTS, VALID_CASE_TYPES
from skillhub_eval.core.taxonomy import Taxonomy

TYPE_ZH: dict[str, str] = {
    "happy_path": "正常场景",
    "edge": "边界场景",
    "refusal": "拒绝场景",
    "adversarial": "对抗场景",
}

_HIGH_RISK_KEYWORDS = frozenset(
    {"越权", "攻击", "注入", "恶意", "违规", "渗透", "钓鱼", "洗钱", "拦截"}
)
_LOW_RISK_KEYWORDS = frozenset({"简单", "日常", "辅助", "格式化", "排版", "润色"})

_CONTRADICTION_PAIRS: tuple[tuple[str, str], ...] = (
    ("财务", "营销"),
    ("投研", "客服"),
    ("量化", "文案"),
)

_L0_PRIORITY: tuple[str, ...] = (
    "category",
    "purpose",
    "risk_level",
    "success_output_shape",
    "intent_source",
    "refusal_scope",
)

_taxonomy: Taxonomy | None = None


def _get_taxonomy() -> Taxonomy:
    global _taxonomy
    if _taxonomy is None:
        _taxonomy = Taxonomy()
    return _taxonomy


def _category_slug(bundle: dict) -> str | None:
    meta = bundle.get("skill_meta") or {}
    slug = meta.get("category")
    if slug is None or not str(slug).strip():
        return None
    return str(slug).strip()


def _description(bundle: dict) -> str:
    meta = bundle.get("skill_meta") or {}
    return str(meta.get("description") or "").strip()


def _skill_body(bundle: dict) -> str:
    return str(bundle.get("skill_md_text") or "")


def _risk_declared(bundle: dict) -> str:
    risk = bundle.get("risk_level_declared")
    if risk is None:
        meta = bundle.get("skill_meta") or {}
        risk = meta.get("risk_level")
    return str(risk or "low").strip().lower()


def _compute_sample_io_gap(staging_path: Path, bundle: dict) -> bool:
    if bundle.get("has_scripts"):
        return False
    has_sample_io = bool(bundle.get("has_sample_io")) or (
        staging_path / "sample_io"
    ).exists()
    return not has_sample_io


def _category_question() -> dict:
    taxonomy = _get_taxonomy()
    options = [
        f"{leaf.full_slug}（{leaf.name_zh}）"
        for leaf in taxonomy.list_leaves()[:6]
    ]
    return {
        "key": "category",
        "label_zh": "业务场景分类",
        "question_zh": "这个 Skill 属于哪类业务场景？请从下列分类中选择最接近的一项。",
        "why_zh": "场景分类决定补题时用什么业务语境出题，也影响集市里的检索归类。",
        "options": options,
    }


def _purpose_question() -> dict:
    return {
        "key": "purpose",
        "label_zh": "Skill 用途说明",
        "question_zh": "请用一句话说明这个 Skill 主要解决什么问题？",
        "why_zh": "描述过短时系统无法判断「正常输出」长什么样，补题和评估容易偏离你的真实意图。",
        "options": None,
    }


def _risk_level_question(declared: str) -> dict:
    return {
        "key": "risk_level",
        "label_zh": "风险等级确认",
        "question_zh": (
            f"你在元数据中标注了风险等级为「{declared}」，"
            "但正文关键词与标注不太一致。实际风险更接近哪一档？"
        ),
        "why_zh": "风险等级决定需要多少道边界/拒绝/对抗类题目，以及是否走更严格的安全检查。",
        "options": ["low（低）", "medium（中）", "high（高）"],
    }


def _success_output_shape_question() -> dict:
    return {
        "key": "success_output_shape",
        "label_zh": "成功输出样例",
        "question_zh": "成功输出通常长什么样？请描述格式或贴一个简短示例。",
        "why_zh": "没有样例时，系统只能按通用模板出题，难以验证你的 Skill 是否按预期格式作答。",
        "options": None,
    }


def _intent_source_question(skill_hint: str, user_hint: str) -> dict:
    return {
        "key": "intent_source",
        "label_zh": "以哪份描述为准",
        "question_zh": (
            f"你描述的是「{user_hint}」，但 SKILL.md 写的是「{skill_hint}」。"
            "后续补题和评估以哪个为准？"
        ),
        "why_zh": "两处描述不一致时，需要先锁定权威来源，避免补题和评估各说各话。",
        "options": ["以 SKILL.md 为准", "以刚才的描述为准", "两者都要覆盖"],
    }


def _refusal_scope_question() -> dict:
    return {
        "key": "refusal_scope",
        "label_zh": "拒绝边界与禁区",
        "question_zh": (
            "哪些用户请求必须拒绝？有哪些不能说、不能做的业务红线？"
            "请用自然语言说明（可多条）。"
        ),
        "why_zh": (
            "高风险 Skill 将自动生成「拒绝类」和「对抗类」评估题，"
            "需要你的业务红线来校准：什么该拒、什么不能答、哪些表述绝对禁止。"
        ),
        "example_zh": "例：不做买卖推荐；不使用「必涨」「稳赚」等绝对化表述；仅做分析不下单",
        "options": ["覆盖常见越权即可", "需额外覆盖特定禁区", "暂无特殊要求"],
    }


def l0_question_label_zh(question: dict) -> str:
    """User-facing short title for an L0 clarification item."""
    label = str(question.get("label_zh") or "").strip()
    if label:
        return label
    text = str(question.get("question_zh") or "").strip()
    if text:
        return text[:40] + ("…" if len(text) > 40 else "")
    return str(question.get("key") or "待澄清项")


def format_l0_labels(questions: list[dict], *, limit: int = 3) -> str:
    if not questions:
        return ""
    return "、".join(l0_question_label_zh(q) for q in questions[:limit])


def _risk_keywords_mismatch(bundle: dict) -> bool:
    declared = _risk_declared(bundle)
    body = _skill_body(bundle)
    has_high = any(kw in body for kw in _HIGH_RISK_KEYWORDS)
    has_low = any(kw in body for kw in _LOW_RISK_KEYWORDS)

    if declared in ("low", "medium") and has_high:
        return True
    if declared == "high" and not has_high and has_low:
        return True
    return False


def _intent_contradiction(bundle: dict, user_message: str | None) -> tuple[str, str] | None:
    if not user_message or not user_message.strip():
        return None
    body = _skill_body(bundle)
    user = user_message.strip()
    for skill_kw, user_kw in _CONTRADICTION_PAIRS:
        if skill_kw in body and user_kw in user and user_kw not in body:
            return skill_kw, user_kw
    return None


def _needs_refusal_scope(risk: str, gap_by_type: dict[str, int]) -> bool:
    if risk != "high":
        return False
    return gap_by_type.get("refusal", 0) > 0 or gap_by_type.get("adversarial", 0) > 0


def detect_l0_clarifications(
    bundle: dict,
    sanitizer_result: SanitizerResult,
    user_message: str | None = None,
    clarifications: dict | None = None,
) -> list[dict]:
    """Return up to 3 L0 clarification questions (deterministic heuristics)."""
    answered = clarifications or {}
    candidates: dict[str, dict] = {}

    slug = _category_slug(bundle)
    taxonomy = _get_taxonomy()
    if not slug or not taxonomy.is_valid_slug(slug):
        candidates["category"] = _category_question()

    desc = _description(bundle)
    if len(desc) < 30:
        candidates["purpose"] = _purpose_question()

    declared = _risk_declared(bundle)
    if _risk_keywords_mismatch(bundle):
        candidates["risk_level"] = _risk_level_question(declared)

    eval_cases = bundle.get("eval_cases") or []
    if len(eval_cases) == 0 and len(_skill_body(bundle)) < 200:
        candidates["success_output_shape"] = _success_output_shape_question()

    contradiction = _intent_contradiction(bundle, user_message)
    if contradiction is not None:
        skill_hint, user_hint = contradiction
        candidates["intent_source"] = _intent_source_question(skill_hint, user_hint)

    if _needs_refusal_scope(declared, sanitizer_result.gap_by_type):
        candidates["refusal_scope"] = _refusal_scope_question()

    questions: list[dict] = []
    for key in _L0_PRIORITY:
        if key in answered:
            continue
        if key in candidates:
            questions.append(candidates[key])
        if len(questions) >= 3:
            break
    return questions


def _business_expectation(category_slug: str | None) -> str:
    if not category_slug:
        return ""
    leaf = _get_taxonomy().get_leaf(category_slug)
    if leaf is None:
        return ""
    return leaf.case_template_hint


def _build_headline_zh(gap_by_type: dict[str, int], risk: str) -> str:
    total_gap = sum(gap_by_type.values())
    if total_gap <= 0:
        return "评估题型已齐全，无需自动补题。"
    parts = [
        f"{TYPE_ZH.get(t, t)} {gap_by_type[t]} 道"
        for t in sorted(gap_by_type)
        if gap_by_type[t] > 0
    ]
    type_summary = "、".join(parts)
    return (
        f"本 Skill（risk={risk}）尚缺 {total_gap} 道评估题"
        f"（{type_summary}），确认后将按表自动出题。"
    )


def build_propagation_plan(
    staging_path: Path,
    bundle: dict,
    sanitizer_result: SanitizerResult,
    clarifications: dict | None = None,
    plan_version: int = 1,
) -> dict:
    """Build deterministic propagation_plan payload — no LLM."""
    risk = _risk_declared(bundle)
    category_slug = _category_slug(bundle)
    sample_io_gap = _compute_sample_io_gap(staging_path, bundle)
    requirements = CASE_TYPE_REQUIREMENTS.get(risk, CASE_TYPE_REQUIREMENTS["low"])

    rows: list[dict] = []
    for case_type in sorted(requirements):
        existing = sanitizer_result.existing_counts.get(case_type, 0)
        gap = sanitizer_result.gap_by_type.get(case_type, 0)
        if gap <= 0 and existing <= 0:
            continue
        rows.append(
            {
                "type": case_type,
                "type_zh": TYPE_ZH.get(case_type, case_type),
                "gap_count": gap,
                "gap": gap,
                "existing_count": existing,
                "tests_what": TYPE_DESCRIPTIONS.get(case_type, case_type),
                "business_expectation": _business_expectation(category_slug),
                "redline": case_type in ("refusal", "adversarial"),
                "sample_io_needed": sample_io_gap and not bundle.get("has_scripts"),
                "enrichment_source": "deterministic",
            }
        )

    # Include any existing valid types outside current risk requirements.
    for case_type, existing in sorted(sanitizer_result.existing_counts.items()):
        if case_type not in requirements and case_type in VALID_CASE_TYPES:
            gap = sanitizer_result.gap_by_type.get(case_type, 0)
            if gap <= 0 and existing <= 0:
                continue
            rows.append(
                {
                    "type": case_type,
                    "type_zh": TYPE_ZH.get(case_type, case_type),
                    "gap_count": gap,
                    "gap": gap,
                    "existing_count": existing,
                    "tests_what": TYPE_DESCRIPTIONS.get(case_type, case_type),
                    "business_expectation": _business_expectation(category_slug),
                    "redline": case_type in ("refusal", "adversarial"),
                    "sample_io_needed": sample_io_gap and not bundle.get("has_scripts"),
                    "enrichment_source": "deterministic",
                }
            )

    l0_questions = detect_l0_clarifications(
        bundle, sanitizer_result, clarifications=clarifications
    )

    return {
        "risk_level_declared": risk,
        "existing_counts": dict(sanitizer_result.existing_counts),
        "gap_by_type": dict(sanitizer_result.gap_by_type),
        "broken_moved": sanitizer_result.broken_moved,
        "sample_io_gap": sample_io_gap,
        "plan_version": plan_version,
        "rows": rows,
        "l0_questions": l0_questions,
        "headline_zh": _build_headline_zh(sanitizer_result.gap_by_type, risk),
        "clarifications_applied": dict(clarifications or {}),
        "enrichment_status": "pending",
    }
