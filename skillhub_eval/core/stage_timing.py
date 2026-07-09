"""Aggregate stage_timing analytics events for API/UI (T6)."""

from __future__ import annotations

_PHASE_LABELS: dict[str, str] = {
    "level0_checking": "Level0 结构",
    "risk_locking": "Risk 锁定",
    "case_executing": "Case 执行",
    "code_asserting": "代码断言",
    "model_judging": "双模型评审",
    "aggregating": "聚合决策",
}


def phase_label(stage: str) -> str:
    if stage == "case_judge":
        return "单 Case 评审"
    return _PHASE_LABELS.get(stage, stage)


def summarize_stage_timings(events: list[dict]) -> dict:
    """Roll up raw stage_timing payloads into phases + slow-case top-N."""
    phases: list[dict] = []
    case_judges: list[dict] = []
    for e in events:
        stage = e.get("stage", "")
        ms = int(e.get("ms") or 0)
        if stage == "case_judge":
            case_judges.append({
                "case_id": e.get("case_id", "?"),
                "ms": ms,
            })
        else:
            phases.append({"stage": stage, "label": phase_label(stage), "ms": ms})

    slow_cases = sorted(case_judges, key=lambda x: x["ms"], reverse=True)[:5]
    model_ms = next((p["ms"] for p in phases if p["stage"] == "model_judging"), None)
    case_exec_ms = next((p["ms"] for p in phases if p["stage"] == "case_executing"), None)
    return {
        "phases": phases,
        "case_judges": case_judges,
        "slow_cases": slow_cases,
        "total_phase_ms": sum(p["ms"] for p in phases),
        "model_judging_ms": model_ms,
        "case_executing_ms": case_exec_ms,
    }
