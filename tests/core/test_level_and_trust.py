"""W8: level_achieved from exec evidence + spot_check_eligible trust v1."""

from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.core.schemas.report import ExecResult


def _engine_with_results(results: dict[str, ExecResult]) -> EvaluationEngine:
    engine = EvaluationEngine(repo=None, ds_provider=None, wb_provider=None)
    engine._case_exec_results = results
    return engine


def test_level_achieved_level2_when_local_entrypoint_ok():
    engine = _engine_with_results({
        "h01": ExecResult(source="local_agent", status="ok", level="level_2"),
    })
    assert engine._compute_level_achieved() == "level_2"


def test_level_achieved_level1_when_only_sample_io():
    engine = _engine_with_results({
        "h01": ExecResult(source="sample_io", status="ok", level="level_1"),
    })
    assert engine._compute_level_achieved() == "level_1"


def test_spot_check_eligible_on_pass_with_local_agent():
    engine = _engine_with_results({
        "h01": ExecResult(source="local_agent", status="ok", level="level_2"),
    })
    assert engine._compute_spot_check_eligible("pass", human_required=False) is True


def test_spot_check_not_eligible_on_warn_or_human_review():
    engine = _engine_with_results({
        "h01": ExecResult(source="local_agent", status="ok", level="level_2"),
    })
    assert engine._compute_spot_check_eligible("warn", human_required=False) is False
    assert engine._compute_spot_check_eligible("pass", human_required=True) is False


def test_execution_source_used_mixed():
    engine = _engine_with_results({
        "h01": ExecResult(source="local_agent", status="ok"),
        "h02": ExecResult(source="sample_io", status="ok"),
    })
    assert engine._compute_execution_source_used({"execution_source": "local"}) == "mixed"
