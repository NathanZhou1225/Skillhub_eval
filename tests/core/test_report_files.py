from skillhub_eval.core.report_files import write_evaluation_report_file
from skillhub_eval.core.schemas.report import EvaluationReport


def test_write_evaluation_report_file_writes_json_under_run_directory(tmp_path):
    report = EvaluationReport(
        run_id="run-1",
        skill_id="skill-1",
        skill_bundle_path="/tmp/skill",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        status="completed",
        review_status="pass",
    )

    out = write_evaluation_report_file(
        run_id="run-1",
        report=report,
        reports_root=tmp_path,
    )

    assert out == tmp_path / "run-1" / "evaluation_report.json"
    assert out.exists()
    assert '"skill_id": "skill-1"' in out.read_text(encoding="utf-8")
