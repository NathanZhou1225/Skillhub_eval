"""Wave 5.3.2 — synchronous assessment gate."""

from pathlib import Path

from skillhub_eval.core.assessment_gate import build_assessment_gate_payload, gate_content_message
from skillhub_eval.core.case_sanitizer import CaseSanitizer
from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.core.propagation_plan import format_l0_labels


def test_gate_payload_flags_case_propagation_gap(tmp_path):
    staging = tmp_path / "staging"
    eval_dir = staging / "eval_cases"
    eval_dir.mkdir(parents=True)
    skill_md = staging / "SKILL.md"
    skill_md.write_text(
        "---\nname: t\nrisk_level: high\ncategory: fin-research/quant-signal\n---\n# T\n",
        encoding="utf-8",
    )
    bundle = ingest_bundle(str(staging))
    sanitizer = CaseSanitizer(risk_level="high", staging_path=staging).run()
    payload = build_assessment_gate_payload(
        staging_path=staging,
        bundle=bundle,
        sanitizer_result=sanitizer,
        security_status="passed",
        gate_version=1,
    )
    assert payload["needs_case_propagation"] is True
    assert payload["can_enter_formal"] is False
    assert "不满足" in gate_content_message(payload) or "题型" in gate_content_message(payload)


def test_format_l0_labels_helper():
    assert format_l0_labels([{"label_zh": "拒绝边界"}]) == "拒绝边界"


def test_gate_security_blocked_message_and_payload(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "SKILL.md").write_text("---\nname: t\n---\n# x\n", encoding="utf-8")
    bundle = ingest_bundle(str(staging))
    payload = build_assessment_gate_payload(
        staging_path=staging,
        bundle=bundle,
        security_status="blocked",
        security_findings=[
            {
                "finding_type": "PROMPT_INJECTION",
                "finding_type_zh": "提示注入风险",
                "matched_text": "...test...",
                "hint_zh": "请修改正文",
                "source": "skill_bundle",
            }
        ],
        gate_version=1,
    )
    assert payload["can_enter_formal"] is False
    assert payload["security_block_reason_zh"]
    msg = gate_content_message(payload)
    assert "安全门禁未通过" in msg
    assert len(payload["security_findings"]) == 1
