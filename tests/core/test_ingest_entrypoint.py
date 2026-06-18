"""W8: entrypoint / execution_source metadata ingest + validation."""

from skillhub_eval.core.ingest import ingest_bundle, validate_execution_meta
from skillhub_eval.core.level0 import Level0Checker


def _write_skill(tmp_path, frontmatter: str, *, scripts: bool = False):
    (tmp_path / "SKILL.md").write_text(
        f"---\n{frontmatter}\n---\n# Skill\n",
        encoding="utf-8",
    )
    (tmp_path / "eval_cases").mkdir(exist_ok=True)
    (tmp_path / "eval_cases" / "h01.yaml").write_text(
        "id: h01\ntype: happy_path\nuser_intent: test\n",
        encoding="utf-8",
    )
    if scripts:
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "run.py").write_text("print('ok')\n", encoding="utf-8")


def test_ingest_parses_entrypoint_and_execution_source(tmp_path):
    _write_skill(
        tmp_path,
        "name: my-skill\nrisk_level: low\n"
        "entrypoint: scripts/run.py\nexecution_source: local\n",
        scripts=True,
    )
    bundle = ingest_bundle(str(tmp_path))
    assert bundle["entrypoint"] == "scripts/run.py"
    assert bundle["execution_source"] == "local"
    assert bundle["has_scripts"] is True


def test_validate_execution_meta_requires_entrypoint_when_has_scripts(tmp_path):
    _write_skill(tmp_path, "name: s\nrisk_level: low\n", scripts=True)
    bundle = ingest_bundle(str(tmp_path))
    issues = validate_execution_meta(bundle)
    assert len(issues) == 1
    assert issues[0]["field"] == "entrypoint"


def test_validate_execution_meta_ok_without_scripts(tmp_path):
    _write_skill(tmp_path, "name: s\nrisk_level: low\n")
    bundle = ingest_bundle(str(tmp_path))
    assert validate_execution_meta(bundle) == []


def test_level0_structure_fails_missing_entrypoint(tmp_path):
    _write_skill(tmp_path, "name: s\nrisk_level: low\n", scripts=True)
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check_structure(bundle)
    assert result["passed"] is False
    assert "LEVEL0_SCHEMA_FAIL" in result["reason_codes"]
