"""Load author-facing gap-fill templates from testskills/_templates/."""

from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_TEMPLATES_DIR = _PROJECT_ROOT / "testskills" / "_templates"

_TEMPLATE_FILES: dict[str, str] = {
    "eval_case": "eval_case.yaml.tpl",
    "sample_io": "sample_io.json.tpl",
    "frontmatter": "frontmatter_snippet.yaml.tpl",
}


def load_gap_templates() -> dict[str, str]:
    """Return template key → file body for UI copy-to-clipboard."""
    result: dict[str, str] = {}
    for key, filename in _TEMPLATE_FILES.items():
        path = _TEMPLATES_DIR / filename
        if path.is_file():
            result[key] = path.read_text(encoding="utf-8")
    return result
