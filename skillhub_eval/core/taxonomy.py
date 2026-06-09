"""Load and query the Q-08 business scenario category taxonomy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_TAXONOMY_PATH = _REPO_ROOT / "data" / "category_taxonomy.yaml"


@dataclass(frozen=True)
class TaxonomyLeaf:
    full_slug: str
    level1_slug: str
    level2_slug: str
    name_zh: str
    definition: str
    case_template_hint: str


class Taxonomy:
    def __init__(self, path: Path | None = None) -> None:
        taxonomy_path = path or _DEFAULT_TAXONOMY_PATH
        raw = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8"))
        self._version: str = raw.get("version", "1.0")
        self._categories: list[dict] = raw.get("categories", [])
        self._leaves: dict[str, TaxonomyLeaf] = {}
        self._build_leaves()

    def _build_leaves(self) -> None:
        for level1 in self._categories:
            level1_slug = level1["slug"]
            for child in level1.get("children", []):
                level2_slug = child["slug"]
                full_slug = f"{level1_slug}/{level2_slug}"
                self._leaves[full_slug] = TaxonomyLeaf(
                    full_slug=full_slug,
                    level1_slug=level1_slug,
                    level2_slug=level2_slug,
                    name_zh=child["name_zh"],
                    definition=child["definition"],
                    case_template_hint=child["case_template_hint"],
                )

    def is_valid_slug(self, slug: str) -> bool:
        return slug in self._leaves

    def get_leaf(self, slug: str) -> TaxonomyLeaf | None:
        return self._leaves.get(slug)

    def list_leaves(self) -> list[TaxonomyLeaf]:
        return list(self._leaves.values())

    def to_tree_json(self) -> dict:
        categories = []
        for level1 in self._categories:
            level1_slug = level1["slug"]
            children = []
            for child in level1.get("children", []):
                full_slug = f"{level1_slug}/{child['slug']}"
                children.append(
                    {
                        "slug": child["slug"],
                        "full_slug": full_slug,
                        "name_zh": child["name_zh"],
                        "definition": child["definition"],
                        "case_template_hint": child["case_template_hint"],
                    }
                )
            categories.append(
                {
                    "slug": level1_slug,
                    "name_zh": level1["name_zh"],
                    "children": children,
                }
            )
        return {"version": self._version, "categories": categories}
