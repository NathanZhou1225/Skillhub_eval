"""
Ingest a Skill package directory into a flat dict for Level0 + engine use.

Frontmatter parsing is intentionally minimal (no YAML library dependency):
only single-level key: value pairs within the --- block are extracted.
"""

import re
from pathlib import Path


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML-style frontmatter from a markdown string."""
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    meta: dict = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta


def _load_cases(eval_cases_dir: Path) -> list[dict]:
    """Parse eval_cases directory into a list of minimal case dicts."""
    if not eval_cases_dir.exists():
        return []
    cases: list[dict] = []
    for filepath in sorted(eval_cases_dir.iterdir()):
        if filepath.suffix not in (".yaml", ".yml", ".json"):
            continue
        text = filepath.read_text(encoding="utf-8")
        case: dict = {"_path": str(filepath)}
        for line in text.splitlines():
            for key in ("id", "type", "user_intent"):
                if line.startswith(f"{key}:"):
                    case[key] = line.split(":", 1)[1].strip()
        if "id" in case:
            cases.append(case)
    return cases


def ingest_bundle(bundle_path: str) -> dict:
    """
    Parse a Skill package directory into a flat dict used throughout the engine.

    Returns:
        skill_id, bundle_path, has_skill_md, skill_meta (frontmatter),
        risk_level_declared, eval_cases, n_cases,
        has_sample_io, has_scripts, skill_md_text
    """
    root = Path(bundle_path)
    skill_md = root / "SKILL.md"
    has_skill_md = skill_md.exists()

    skill_md_text = ""
    meta: dict = {}
    if has_skill_md:
        skill_md_text = skill_md.read_text(encoding="utf-8")
        meta = _parse_frontmatter(skill_md_text)

    cases = _load_cases(root / "eval_cases")
    has_sample_io = (root / "sample_io").exists()

    scripts_dir = root / "scripts"
    has_scripts = scripts_dir.exists() and any(
        f.suffix == ".py" for f in scripts_dir.iterdir()
    ) if scripts_dir.exists() else False

    skill_id = meta.get("id") or meta.get("name") or root.name

    return {
        "skill_id": skill_id,
        "bundle_path": str(root),
        "has_skill_md": has_skill_md,
        "skill_meta": meta,
        "skill_md_text": skill_md_text,
        "risk_level_declared": meta.get("risk_level"),
        "eval_cases": cases,
        "n_cases": len(cases),
        "has_sample_io": has_sample_io,
        "has_scripts": has_scripts,
    }
