"""Wave 5.2 Task 2 — propagation_plan builder + L0 clarification triggers."""

from pathlib import Path

from skillhub_eval.core.case_sanitizer import CaseSanitizer, SanitizerResult
from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.core.propagation_plan import (
    TYPE_ZH,
    build_propagation_plan,
    detect_l0_clarifications,
    format_l0_labels,
)
from skillhub_eval.core.schemas.enums import CASE_TYPE_REQUIREMENTS


def _write_skill_only(
    staging: Path,
    *,
    risk: str = "low",
    description: str = "这是一个用于测试 propagation plan 的 Skill，描述足够长以满足 L0 门槛。",
    category: str | None = None,
    body: str = "# Test Skill\n\n本 Skill 用于评估 propagation plan 构建逻辑。\n",
) -> dict:
    lines = [
        "---",
        "name: test-skill",
        f"description: {description}",
        f"risk_level: {risk}",
    ]
    if category is not None:
        lines.append(f"category: {category}")
    lines.extend(["---", body])
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "SKILL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ingest_bundle(str(staging))


def _sanitizer(staging: Path, risk: str) -> SanitizerResult:
    return CaseSanitizer(risk, staging).run()


def test_zip_like_skill_md_only_shows_gaps_and_propagation_rows(tmp_path):
    staging = tmp_path / "staging"
    bundle = _write_skill_only(staging, category="fin-research/quant-signal")
    sanitizer = _sanitizer(staging, bundle["risk_level_declared"] or "low")

    plan = build_propagation_plan(staging, bundle, sanitizer)

    assert sanitizer.needs_propagation is True
    assert plan["gap_by_type"] == CASE_TYPE_REQUIREMENTS["low"]
    assert plan["existing_counts"] == {}
    assert plan["broken_moved"] == 0
    assert plan["sample_io_gap"] is True

    assert len(plan["rows"]) == 1
    row = plan["rows"][0]
    assert row["type"] == "happy_path"
    assert row["type_zh"] == TYPE_ZH["happy_path"]
    assert row["gap_count"] == 3
    assert row["existing_count"] == 0
    assert row["redline"] is False
    assert row["sample_io_needed"] is True
    assert "正常典型输入" in row["tests_what"]
    assert "因子" in row["business_expectation"] or "信号" in row["business_expectation"]
    assert plan["headline_zh"]
    assert "l0_questions" in plan


def test_detect_l0_category_missing_returns_category_question(tmp_path):
    staging = tmp_path / "staging"
    bundle = _write_skill_only(staging, category=None)
    sanitizer = _sanitizer(staging, "low")

    questions = detect_l0_clarifications(bundle, sanitizer)

    assert len(questions) >= 1
    assert questions[0]["key"] == "category"
    assert "question_zh" in questions[0]
    assert questions[0]["options"] is not None
    assert len(questions[0]["options"]) >= 2


def test_detect_l0_skips_category_when_already_clarified(tmp_path):
    staging = tmp_path / "staging"
    bundle = _write_skill_only(staging, category=None)
    sanitizer = _sanitizer(staging, "low")

    questions = detect_l0_clarifications(
        bundle,
        sanitizer,
        clarifications={"category": "fin-research/quant-signal"},
    )

    keys = [q["key"] for q in questions]
    assert "category" not in keys


def test_high_risk_refusal_gap_redline_and_refusal_scope_question(tmp_path):
    staging = tmp_path / "staging"
    bundle = _write_skill_only(
        staging,
        risk="high",
        category="asset-compliance/risk-interceptor",
        description="越权风控拦截 Skill，用于识别可疑交易与合规违规并输出拦截依据。",
        body="# Risk Interceptor\n\n检测越权操作与违规请求。\n",
    )
    sanitizer = _sanitizer(staging, "high")

    plan = build_propagation_plan(staging, bundle, sanitizer)

    refusal_row = next(r for r in plan["rows"] if r["type"] == "refusal")
    adv_row = next(r for r in plan["rows"] if r["type"] == "adversarial")
    assert refusal_row["redline"] is True
    assert adv_row["redline"] is True
    assert refusal_row["gap_count"] == 2

    l0_keys = [q["key"] for q in plan["l0_questions"]]
    assert "refusal_scope" in l0_keys
    refusal_q = next(q for q in plan["l0_questions"] if q["key"] == "refusal_scope")
    assert refusal_q.get("label_zh")
    assert refusal_q.get("why_zh")
    assert "refusal_scope" not in refusal_q.get("label_zh", "")
    assert "拒绝" in refusal_q.get("question_zh", "")


def test_plan_version_passed_through(tmp_path):
    staging = tmp_path / "staging"
    bundle = _write_skill_only(staging, category="general-utility/data-sanitization")
    sanitizer = _sanitizer(staging, "low")

    plan = build_propagation_plan(
        staging, bundle, sanitizer, clarifications=None, plan_version=3
    )

    assert plan["plan_version"] == 3


def test_format_l0_labels_uses_chinese_not_keys():
    questions = [
        {"key": "refusal_scope", "label_zh": "拒绝边界与禁区", "question_zh": "哪些必须拒绝？"},
    ]
    assert format_l0_labels(questions) == "拒绝边界与禁区"
    assert "refusal_scope" not in format_l0_labels(questions)
