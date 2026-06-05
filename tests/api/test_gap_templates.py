"""T3 — gap template loader tests."""

from skillhub_eval.adapters.api.gap_templates import load_gap_templates


def test_load_gap_templates_includes_all_keys():
    templates = load_gap_templates()
    assert "eval_case" in templates
    assert "sample_io" in templates
    assert "frontmatter" in templates
    assert "user_intent:" in templates["eval_case"]
    assert '"response"' in templates["sample_io"]
    assert "risk_level:" in templates["frontmatter"]
