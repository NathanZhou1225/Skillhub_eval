"""W8: exec-fixture-minimal bundle accepted by ingest + Level0."""

from pathlib import Path

from skillhub_eval.core.ingest import ingest_bundle, validate_execution_meta
from skillhub_eval.core.level0 import Level0Checker

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2] / "testskills" / "exec-fixture-minimal"
)


def test_exec_fixture_ingest_and_level0():
    bundle = ingest_bundle(str(FIXTURE_ROOT))
    assert bundle["entrypoint"] == "scripts/run.py"
    assert bundle["execution_source"] == "local"
    assert bundle["has_scripts"] is True
    assert validate_execution_meta(bundle) == []
    l0 = Level0Checker().check_structure(bundle)
    assert l0["passed"] is True
