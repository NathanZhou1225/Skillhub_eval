"""
Tests for CasePropagator (Wave 3, Task 3).
Uses MockProvider with async generate() — no real LLM calls.
"""

import json
import pytest

from skillhub_eval.core.propagator import CasePropagator, PropagatorResult


SAMPLE_SKILL_MD = """\
# 财务报表解析 Skill

## 功能描述
本 Skill 接受用户上传的财务报表（PDF / Excel），自动识别资产负债表、利润表、现金流量表，
提取关键财务指标，并生成结构化 JSON 输出。

## 适用场景
- 企业财务尽调
- 年报分析
- 投资研究

## 拒绝执行条件
- 文件格式不支持时应拒绝
- 涉及非法内容时应拒绝
"""


class MockProvider:
    """Duck-typed mock: only needs generate(prompt) -> str."""

    def __init__(self, response=None, raise_exc=None):
        self.response = response
        self.raise_exc = raise_exc
        self.calls: list[str] = []

    async def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        if self.raise_exc:
            raise self.raise_exc
        return self.response or "[]"


def _make_valid_cases(case_type: str, count: int, start: int = 1, *, include_id: bool = True) -> list[dict]:
    from skillhub_eval.core.propagator import TYPE_ABBR
    abbr = TYPE_ABBR.get(case_type, case_type)
    cases = []
    for i in range(1, count + 1):
        case = {
            "type": case_type,
            "user_intent": f"用户意图 {i}",
            "input_template": f"输入示例 {i}",
            "expected_behavior": f"期望行为 {i}",
        }
        if include_id:
            case["id"] = f"prop_{abbr}_{start + i - 1:02d}"
        cases.append(case)
    return cases


# ─── 1. Empty gap_by_type ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propagate_empty_gap_returns_empty_result(tmp_path):
    provider = MockProvider()
    propagator = CasePropagator(provider, taxonomy=None)
    result = await propagator.propagate(
        skill_md_text=SAMPLE_SKILL_MD,
        risk_level="low",
        category_slug="finance/report",
        staging_path=tmp_path,
        gap_by_type={},
    )
    assert isinstance(result, PropagatorResult)
    assert result.cases_written == []
    assert result.cases_failed == []
    assert result.used_fallback is False
    assert list(tmp_path.glob("**/*.yaml")) == []
    assert list(tmp_path.glob("**/*.json")) == []


# ─── 2. LLM success — low risk, 3 happy_path ──────────────────────────────────

@pytest.mark.asyncio
async def test_propagate_llm_success_writes_files(tmp_path):
    cases = _make_valid_cases("happy_path", 3)
    provider = MockProvider(response=json.dumps(cases))
    propagator = CasePropagator(provider, taxonomy=None)

    result = await propagator.propagate(
        skill_md_text=SAMPLE_SKILL_MD,
        risk_level="low",
        category_slug="finance/report",
        staging_path=tmp_path,
        gap_by_type={"happy_path": 3},
    )

    assert result.used_fallback is False
    assert len(result.cases_written) == 3
    assert result.cases_failed == []

    yaml_files = list((tmp_path / "eval_cases").glob("prop_happy_*.yaml"))
    json_files = list((tmp_path / "sample_io").glob("prop_happy_*.json"))
    assert len(yaml_files) == 3
    assert len(json_files) == 3


# ─── 3. LLM raises exception → fallback placeholders ─────────────────────────

@pytest.mark.asyncio
async def test_propagate_llm_exception_uses_fallback(tmp_path):
    provider = MockProvider(raise_exc=RuntimeError("API timeout"))
    propagator = CasePropagator(provider, taxonomy=None)

    result = await propagator.propagate(
        skill_md_text=SAMPLE_SKILL_MD,
        risk_level="low",
        category_slug="finance/report",
        staging_path=tmp_path,
        gap_by_type={"happy_path": 2},
    )

    assert result.used_fallback is True
    assert len(result.cases_failed) == 2
    assert result.cases_written == []

    yaml_files = list((tmp_path / "eval_cases").glob("*.yaml"))
    assert len(yaml_files) == 2
    import yaml
    content = yaml.safe_load(yaml_files[0].read_text(encoding="utf-8"))
    assert content["origin"] == "staging_propagator_fallback"
    assert "占位" in content["user_intent"]


# ─── 4. LLM returns invalid JSON → fallback ───────────────────────────────────

@pytest.mark.asyncio
async def test_propagate_invalid_json_uses_fallback(tmp_path):
    provider = MockProvider(response="this is not json {{{")
    propagator = CasePropagator(provider, taxonomy=None)

    result = await propagator.propagate(
        skill_md_text=SAMPLE_SKILL_MD,
        risk_level="low",
        category_slug="finance/report",
        staging_path=tmp_path,
        gap_by_type={"happy_path": 1},
    )

    assert result.used_fallback is True
    assert len(result.cases_failed) == 1


# ─── 5. LLM returns valid JSON but missing required field → fallback ──────────

@pytest.mark.asyncio
async def test_propagate_missing_field_uses_fallback(tmp_path):
    bad_cases = [
        {"type": "happy_path"}
        # missing user_intent, input_template, expected_behavior
    ]
    provider = MockProvider(response=json.dumps(bad_cases))
    propagator = CasePropagator(provider, taxonomy=None)

    result = await propagator.propagate(
        skill_md_text=SAMPLE_SKILL_MD,
        risk_level="low",
        category_slug="finance/report",
        staging_path=tmp_path,
        gap_by_type={"happy_path": 1},
    )

    assert result.used_fallback is True
    assert len(result.cases_failed) == 1


# ─── 6. category_slug with taxonomy — hint used in prompt ─────────────────────

@pytest.mark.asyncio
async def test_propagate_uses_category_hint_from_taxonomy(tmp_path):
    from unittest.mock import MagicMock
    from skillhub_eval.core.taxonomy import TaxonomyLeaf

    fake_leaf = TaxonomyLeaf(
        full_slug="finance/report",
        level1_slug="finance",
        level2_slug="report",
        name_zh="财务报表",
        definition="财务报表相关任务",
        case_template_hint="重点测试报表解析的准确性和完整性。",
    )
    mock_taxonomy = MagicMock()
    mock_taxonomy.get_leaf.return_value = fake_leaf

    cases = _make_valid_cases("happy_path", 1)
    provider = MockProvider(response=json.dumps(cases))
    propagator = CasePropagator(provider, taxonomy=mock_taxonomy)

    await propagator.propagate(
        skill_md_text=SAMPLE_SKILL_MD,
        risk_level="low",
        category_slug="finance/report",
        staging_path=tmp_path,
        gap_by_type={"happy_path": 1},
    )

    assert len(provider.calls) == 1
    assert "重点测试报表解析的准确性和完整性。" in provider.calls[0]


# ─── 7. category_slug not found in taxonomy → no error, hint="" ──────────────

@pytest.mark.asyncio
async def test_propagate_slug_not_found_no_error(tmp_path):
    from unittest.mock import MagicMock

    mock_taxonomy = MagicMock()
    mock_taxonomy.get_leaf.return_value = None  # slug not found

    cases = _make_valid_cases("happy_path", 1)
    provider = MockProvider(response=json.dumps(cases))
    propagator = CasePropagator(provider, taxonomy=mock_taxonomy)

    result = await propagator.propagate(
        skill_md_text=SAMPLE_SKILL_MD,
        risk_level="low",
        category_slug="nonexistent/slug",
        staging_path=tmp_path,
        gap_by_type={"happy_path": 1},
    )

    assert result.used_fallback is False
    assert len(result.cases_written) == 1


# ─── 8. Medium risk, edge gap=2 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_propagate_medium_risk_edge_cases(tmp_path):
    edge_cases = _make_valid_cases("edge", 2)
    provider = MockProvider(response=json.dumps(edge_cases))
    propagator = CasePropagator(provider, taxonomy=None)

    result = await propagator.propagate(
        skill_md_text=SAMPLE_SKILL_MD,
        risk_level="medium",
        category_slug="finance/report",
        staging_path=tmp_path,
        gap_by_type={"edge": 2},
    )

    assert result.used_fallback is False
    assert len(result.cases_written) == 2

    yaml_files = list((tmp_path / "eval_cases").glob("prop_edge_*.yaml"))
    assert len(yaml_files) == 2


# ─── 9. Multiple types in gap_by_type (zero counts skipped) ──────────────────

@pytest.mark.asyncio
async def test_propagate_skips_zero_count_types(tmp_path):
    """gap_by_type with some 0-count entries — only positive-count types generate files."""
    happy_cases = _make_valid_cases("happy_path", 2)
    provider = MockProvider(response=json.dumps(happy_cases))
    propagator = CasePropagator(provider, taxonomy=None)

    result = await propagator.propagate(
        skill_md_text=SAMPLE_SKILL_MD,
        risk_level="medium",
        category_slug="finance/report",
        staging_path=tmp_path,
        gap_by_type={"happy_path": 2, "edge": 0},
    )

    assert result.used_fallback is False
    assert len(result.cases_written) == 2
    yaml_files = list((tmp_path / "eval_cases").glob("*.yaml"))
    assert len(yaml_files) == 2
    assert len(provider.calls) == 1  # only called once (edge skipped)


# ─── 10. Written YAML files have correct structure ────────────────────────────

@pytest.mark.asyncio
async def test_propagate_yaml_structure(tmp_path):
    import yaml

    cases = _make_valid_cases("happy_path", 1)
    provider = MockProvider(response=json.dumps(cases))
    propagator = CasePropagator(provider, taxonomy=None)

    await propagator.propagate(
        skill_md_text=SAMPLE_SKILL_MD,
        risk_level="low",
        category_slug="finance/report",
        staging_path=tmp_path,
        gap_by_type={"happy_path": 1},
    )

    yaml_file = next((tmp_path / "eval_cases").glob("*.yaml"))
    content = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))

    assert content["id"] == "prop_happy_01"
    assert content["type"] == "happy_path"
    assert content["origin"] == "staging_propagator"
    assert "user_intent" in content
    assert "input_template" in content
    assert "expected_behavior" in content

    json_file = tmp_path / "sample_io" / "prop_happy_01.json"
    assert json_file.exists()
    stub = json.loads(json_file.read_text(encoding="utf-8"))
    assert stub["input"] == ""
    assert stub["output"] is None


# ─── 11. LLM returns markdown-fenced JSON → stripped and parsed ──────────────

@pytest.mark.asyncio
async def test_propagate_strips_markdown_fence(tmp_path):
    cases = _make_valid_cases("happy_path", 1)
    fenced = f"```json\n{json.dumps(cases)}\n```"
    provider = MockProvider(response=fenced)
    propagator = CasePropagator(provider, taxonomy=None)

    result = await propagator.propagate(
        skill_md_text=SAMPLE_SKILL_MD,
        risk_level="low",
        category_slug="finance/report",
        staging_path=tmp_path,
        gap_by_type={"happy_path": 1},
    )

    assert result.used_fallback is False
    assert len(result.cases_written) == 1


# ─── 12. LLM-provided ids are ignored — server assigns deterministic ids ───────

@pytest.mark.asyncio
async def test_propagate_ignores_llm_ids(tmp_path):
    """LLM may return conflicting ids; server always assigns prop_{abbr}_{n:02d}."""
    llm_cases = [
        {
            "id": "custom_wrong_id",
            "type": "happy_path",
            "user_intent": "用户意图",
            "input_template": "输入示例",
            "expected_behavior": "期望行为",
        }
    ]
    provider = MockProvider(response=json.dumps(llm_cases))
    propagator = CasePropagator(provider, taxonomy=None)

    result = await propagator.propagate(
        skill_md_text=SAMPLE_SKILL_MD,
        risk_level="low",
        category_slug="finance/report",
        staging_path=tmp_path,
        gap_by_type={"happy_path": 1},
    )

    assert result.cases_written == ["prop_happy_01"]
    yaml_file = tmp_path / "eval_cases" / "prop_happy_01.yaml"
    assert yaml_file.exists()
    assert not (tmp_path / "eval_cases" / "custom_wrong_id.yaml").exists()


# ─── 13. LLM wrong count → fallback ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_propagate_wrong_count_uses_fallback(tmp_path):
    cases = _make_valid_cases("happy_path", 1)
    provider = MockProvider(response=json.dumps(cases))
    propagator = CasePropagator(provider, taxonomy=None)

    result = await propagator.propagate(
        skill_md_text=SAMPLE_SKILL_MD,
        risk_level="low",
        category_slug="finance/report",
        staging_path=tmp_path,
        gap_by_type={"happy_path": 2},
    )

    assert result.used_fallback is True
    assert len(result.cases_failed) == 2
