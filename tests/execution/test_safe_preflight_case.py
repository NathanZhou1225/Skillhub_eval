"""Tests for automatic safe local execution check case generation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from skillhub_eval.core.gaps import scan_gaps
from skillhub_eval.core.ingest import ingest_bundle, is_preflight_case
from skillhub_eval.core.level0 import Level0Checker
from skillhub_eval.core.schemas import BundleState
from skillhub_eval.execution.safe_preflight_case import (
    build_safe_preflight_case,
    ensure_safe_preflight_case,
    ensure_safe_preflight_case_with_provider,
    fallback_safe_preflight_case,
    formal_eval_cases,
    validate_safe_preflight_candidate,
)


def _high_risk_bundle_root(tmp_path: Path) -> Path:
    root = tmp_path / "stock-radar-like"
    root.mkdir()
    (root / "SKILL.md").write_text(
        "---\nname: stock-radar\nid: skill.stock-radar\nrisk_level: high\n"
        "entrypoint: scripts/run.py\n---\n# Stock radar\n",
        encoding="utf-8",
    )
    scripts = root / "scripts"
    scripts.mkdir()
    (scripts / "run.py").write_text("print('ok')\n", encoding="utf-8")
    ec = root / "eval_cases"
    ec.mkdir()
    spec = [
        ("h01", "happy_path"), ("h02", "happy_path"), ("h03", "happy_path"),
        ("e01", "edge"), ("e02", "edge"),
        ("r01", "refusal"), ("r02", "refusal"),
        ("a01", "adversarial"), ("a02", "adversarial"),
    ]
    for cid, ctype in spec:
        (ec / f"{cid}.yaml").write_text(
            f"id: {cid}\ntype: {ctype}\nuser_intent: test\ninput_template: x\n"
            f"expected_behavior: y\n",
            encoding="utf-8",
        )
    return root


def test_high_risk_without_safe_case_generates_runtime_preflight_01(tmp_path):
    root = _high_risk_bundle_root(tmp_path)
    before = ingest_bundle(str(root))
    assert before["n_cases"] == 9

    created = ensure_safe_preflight_case(root)
    assert created is not None
    assert created["id"] == "runtime_preflight_01"
    assert created["type"] == "preflight"
    assert created["safe_preflight"] is True

    path = root / "eval_cases" / "runtime_preflight_01.yaml"
    assert path.is_file()

    after = ingest_bundle(str(root))
    assert len(after["eval_cases"]) == 10
    assert after["n_cases"] == 9
    assert any(is_preflight_case(c) for c in after["eval_cases"])


def test_authored_safe_preflight_left_unchanged(tmp_path):
    root = _high_risk_bundle_root(tmp_path)
    authored = root / "eval_cases" / "author_preflight.yaml"
    authored.write_text(
        yaml.safe_dump(
            {
                "id": "author_preflight",
                "type": "preflight",
                "safe_preflight": True,
                "origin": "author",
                "user_intent": "作者提供的安全检查",
                "input_template": "仅做环境检查，不执行真实业务动作。",
                "expected_behavior": "返回最小结构化结果。",
            },
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    created = ensure_safe_preflight_case(root)
    assert created is None
    assert not (root / "eval_cases" / "runtime_preflight_01.yaml").exists()


def test_unsafe_llm_candidate_rejected():
    bad = {
        "type": "preflight",
        "safe_preflight": True,
        "id": "x",
        "user_intent": "请买入该股票并下单",
        "input_template": "执行真实交易",
        "expected_behavior": "给出投资建议",
    }
    ok, reasons = validate_safe_preflight_candidate(bad)
    assert ok is False
    assert reasons


def test_invalid_llm_candidate_falls_back_to_template(tmp_path):
    root = _high_risk_bundle_root(tmp_path)
    bundle = ingest_bundle(str(root))

    case = build_safe_preflight_case(bundle)
    assert case is not None
    assert case["origin"] == "runtime_platform_template"
    assert case["id"] == "runtime_preflight_01"


def test_heavy_llm_candidate_rejected():
    heavy = {
        "type": "preflight",
        "safe_preflight": True,
        "id": "runtime_preflight_01",
        "user_intent": "本地执行环境检查，仅验证流程。",
        "input_template": "诊断 000001 平安银行（本地测试，仅验证流程）",
        "expected_behavior": "成功输出 diagnosis_bundle.json，包含六维诊断指标。",
    }
    ok, reasons = validate_safe_preflight_candidate(heavy)
    assert ok is False
    assert "heavy_business_scope" in reasons


class _ProviderACandidate:
    def __init__(self, payload):
        self.payload = payload
        self.prompts: list[str] = []

    async def judge(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        return self.payload


@pytest.mark.asyncio
async def test_provider_a_not_called_when_preflight_generation_not_needed(tmp_path):
    root = _high_risk_bundle_root(tmp_path)
    (root / "SKILL.md").write_text(
        "---\nname: low-risk\nid: skill.low\nrisk_level: low\n---\n# Low\n",
        encoding="utf-8",
    )
    provider = _ProviderACandidate(
        {
            "user_intent": "仅验证本地执行环境，不生成真实业务结论。",
            "input_template": "请仅进行本地执行环境检查。",
            "expected_behavior": "返回最小可评估结果。",
        }
    )

    created = await ensure_safe_preflight_case_with_provider(root, provider=provider)

    assert created is None
    assert provider.prompts == []


@pytest.mark.asyncio
async def test_default_high_risk_uses_template_without_calling_provider(tmp_path):
    root = _high_risk_bundle_root(tmp_path)
    provider = _ProviderACandidate(
        {
            "user_intent": "仅验证本地执行环境，不生成真实业务结论。",
            "input_template": "请仅进行本地执行环境检查，返回最小结构化结果，不输出买卖建议。",
            "expected_behavior": "能读取 Skill 指令并返回最小可评估结果。",
        }
    )

    created = await ensure_safe_preflight_case_with_provider(root, provider=provider)

    assert created is not None
    assert created["origin"] == "runtime_platform_template"
    assert provider.prompts == []
    persisted = yaml.safe_load((root / "eval_cases" / "runtime_preflight_01.yaml").read_text(encoding="utf-8"))
    assert persisted["origin"] == "runtime_platform_template"


@pytest.mark.asyncio
async def test_provider_a_unsafe_candidate_falls_back_to_template(tmp_path):
    root = _high_risk_bundle_root(tmp_path)
    provider = _ProviderACandidate(
        {
            "user_intent": "请买入该股票并下单",
            "input_template": "执行真实交易",
            "expected_behavior": "输出买卖建议",
        }
    )

    created = await ensure_safe_preflight_case_with_provider(root, provider=provider)

    assert created is not None
    assert created["origin"] == "runtime_platform_template"


def test_preflight_excluded_from_level0_case_gate(tmp_path):
    root = _high_risk_bundle_root(tmp_path)
    ensure_safe_preflight_case(root)
    bundle = ingest_bundle(str(root))
    result = Level0Checker().check_case_gate(bundle)
    assert result["passed"] is True
    assert result["n_cases"] == 9


def test_preflight_excluded_from_gaps_count(tmp_path):
    root = _high_risk_bundle_root(tmp_path)
    ensure_safe_preflight_case(root)
    bundle = ingest_bundle(str(root))
    gaps = scan_gaps(bundle, BundleState.confirmed)
    count_gaps = [g for g in gaps["gaps"] if g.get("field_path") == "eval_cases.count"]
    assert not count_gaps


def test_force_regenerate_replaces_only_generated_file(tmp_path):
    root = _high_risk_bundle_root(tmp_path)
    ensure_safe_preflight_case(root)
    path = root / "eval_cases" / "runtime_preflight_01.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["user_intent"] = "old generated intent"
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    regen = ensure_safe_preflight_case(root, force=True)
    assert regen is not None
    assert "仅验证" in regen["user_intent"]


def test_existing_llm_generated_heavy_preflight_auto_migrates_to_template(tmp_path):
    root = _high_risk_bundle_root(tmp_path)
    path = root / "eval_cases" / "runtime_preflight_01.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "id": "runtime_preflight_01",
                "type": "preflight",
                "safe_preflight": True,
                "origin": "runtime_platform_llm",
                "user_intent": "本地执行环境检查，仅验证流程。",
                "input_template": "诊断 000001 平安银行（本地测试，仅验证流程）",
                "expected_behavior": "成功输出 diagnosis_bundle.json，包含六维诊断指标。",
            },
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    migrated = ensure_safe_preflight_case(root)

    assert migrated is not None
    assert migrated["origin"] == "runtime_platform_template"
    persisted = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert persisted["origin"] == "runtime_platform_template"
    assert "diagnosis_bundle" not in persisted["expected_behavior"]


def test_fallback_template_for_entrypoint_skill_uses_entrypoint_check_framing(tmp_path):
    bundle = ingest_bundle(str(_high_risk_bundle_root(tmp_path)))

    case = fallback_safe_preflight_case(bundle)

    assert "入口" in case["input_template"]
    assert "文件存在" in case["input_template"]
    assert "不运行正式业务流程" in case["input_template"]


def test_force_regenerate_refuses_authored_safe_case(tmp_path):
    root = _high_risk_bundle_root(tmp_path)
    authored = root / "eval_cases" / "runtime_preflight_01.yaml"
    authored.write_text(
        yaml.safe_dump(
            {
                "id": "runtime_preflight_01",
                "type": "preflight",
                "safe_preflight": True,
                "origin": "author",
                "user_intent": "作者写的",
                "input_template": "仅环境检查，不做真实业务动作。",
                "expected_behavior": "最小结果。",
            },
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="authored"):
        ensure_safe_preflight_case(root, force=True)


def test_formal_eval_cases_excludes_preflight(tmp_path):
    root = _high_risk_bundle_root(tmp_path)
    ensure_safe_preflight_case(root)
    bundle = ingest_bundle(str(root))
    formal = formal_eval_cases(bundle)
    assert len(formal) == 9
    assert all(not is_preflight_case(c) for c in formal)


def test_fallback_template_has_environment_check_framing():
    case = fallback_safe_preflight_case({"skill_id": "demo"})
    ok, _ = validate_safe_preflight_candidate(case)
    assert ok is True
