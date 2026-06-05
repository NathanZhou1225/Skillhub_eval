"""T6 — stage_timing aggregation for API/UI."""

from skillhub_eval.core.stage_timing import phase_label, summarize_stage_timings


def test_summarize_stage_timings_phases_and_slow_cases():
    events = [
        {"stage": "level0_checking", "ms": 120},
        {"stage": "model_judging", "ms": 45000},
        {"stage": "case_judge", "case_id": "c01", "ms": 8000},
        {"stage": "case_judge", "case_id": "c02", "ms": 22000},
        {"stage": "aggregating", "ms": 50},
    ]
    summary = summarize_stage_timings(events)
    assert summary["total_phase_ms"] == 120 + 45000 + 50
    assert summary["model_judging_ms"] == 45000
    assert len(summary["slow_cases"]) == 2
    assert summary["slow_cases"][0]["case_id"] == "c02"
    assert summary["phases"][1]["stage"] == "model_judging"
    assert phase_label("model_judging") == "双模型评审"
