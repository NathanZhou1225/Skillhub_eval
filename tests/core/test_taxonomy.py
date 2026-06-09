"""Taxonomy loader and slug validation tests."""

from pathlib import Path

from skillhub_eval.core.taxonomy import Taxonomy, TaxonomyLeaf

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TAXONOMY_PATH = _REPO_ROOT / "data" / "category_taxonomy.yaml"

VALID_LEAVES = [
    "fin-research/fin-statement",
    "fin-research/macro-indicator",
    "fin-research/quant-signal",
    "asset-compliance/portfolio-audit",
    "asset-compliance/risk-interceptor",
    "general-utility/data-sanitization",
    "general-utility/report-generator",
]


def test_load_taxonomy():
    taxonomy = Taxonomy(_TAXONOMY_PATH)
    leaves = taxonomy.list_leaves()
    assert len(leaves) == 7
    full_slugs = {leaf.full_slug for leaf in leaves}
    assert full_slugs == set(VALID_LEAVES)


def test_is_valid_slug():
    taxonomy = Taxonomy(_TAXONOMY_PATH)

    for slug in VALID_LEAVES:
        assert taxonomy.is_valid_slug(slug) is True

    assert taxonomy.is_valid_slug("fin-research") is False
    assert taxonomy.is_valid_slug("fin-research/unknown") is False
    assert taxonomy.is_valid_slug("unknown/quant-signal") is False
    assert taxonomy.is_valid_slug("") is False


def test_get_leaf():
    taxonomy = Taxonomy(_TAXONOMY_PATH)
    leaf = taxonomy.get_leaf("fin-research/quant-signal")

    assert leaf is not None
    assert isinstance(leaf, TaxonomyLeaf)
    assert leaf.full_slug == "fin-research/quant-signal"
    assert leaf.level1_slug == "fin-research"
    assert leaf.level2_slug == "quant-signal"
    assert leaf.name_zh == "量化因子/技术形态"
    assert leaf.definition
    assert leaf.case_template_hint

    assert taxonomy.get_leaf("fin-research/nonexistent") is None


def test_to_tree_json():
    taxonomy = Taxonomy(_TAXONOMY_PATH)
    tree = taxonomy.to_tree_json()

    assert tree["version"] == "1.0"
    assert len(tree["categories"]) == 3

    level1_slugs = [cat["slug"] for cat in tree["categories"]]
    assert level1_slugs == ["fin-research", "asset-compliance", "general-utility"]

    fin_research = tree["categories"][0]
    assert fin_research["name_zh"] == "金融核心投研"
    assert len(fin_research["children"]) == 3

    quant = next(c for c in fin_research["children"] if c["slug"] == "quant-signal")
    assert quant["full_slug"] == "fin-research/quant-signal"
    assert quant["name_zh"] == "量化因子/技术形态"
    assert "definition" in quant
    assert "case_template_hint" in quant

    child_counts = [len(cat["children"]) for cat in tree["categories"]]
    assert child_counts == [3, 2, 2]
