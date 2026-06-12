"""Build trace API payload from votes + judge_traces."""

from __future__ import annotations

from skillhub_eval.core.divergence import _case_gap, _votes_by_case
from skillhub_eval.core.provider_summary import build_provider_summary
from skillhub_eval.core.ports import Repository


def build_trace_report(run_id: str, repo: Repository) -> dict | None:
    run = repo.get_run(run_id)
    if run is None:
        return None

    report = repo.get_report(run_id) or {}
    votes = repo.get_votes_for_run(run_id)
    traces = {t["case_id"]: t for t in repo.get_judge_traces(run_id)}

    agg_stub = {"ds_score": None, "wb_score": None, "r5_triggered": False}
    if report.get("provider_summary"):
        ps = report["provider_summary"]
        agg_stub["ds_score"] = ps.get("deepseek_score")
        agg_stub["wb_score"] = ps.get("gemini_score")
        agg_stub["r5_triggered"] = ps.get("r5_triggered", False)
    provider_summary = build_provider_summary(votes, agg_stub)

    grouped = _votes_by_case(votes)
    case_ids = list(dict.fromkeys(
        list(grouped.keys()) + list(traces.keys())
    ))

    cases_out: list[dict] = []
    for case_id in case_ids:
        by_model = grouped.get(case_id, {})
        ds_vote = by_model.get("deepseek")
        gm_vote = by_model.get("gemini")
        trace_row = traces.get(case_id, {})
        gap = _case_gap(ds_vote, gm_vote)

        def _vote_payload(vote: dict | None) -> dict | None:
            if not vote:
                return None
            sub = vote.get("dimension_scores") or vote.get("sub_scores") or {}
            return {
                "score_total": vote.get("score_total"),
                "suggested_review_status": vote.get("suggested_review_status"),
                "confidence": vote.get("confidence"),
                "feedback": vote.get("feedback", ""),
                "sub_scores": sub,
            }

        cases_out.append(
            {
                "case_id": case_id,
                "case_type": (ds_vote or gm_vote or {}).get("case_type", "happy_path"),
                "gap": gap,
                "prompt_text": trace_row.get("prompt_text"),
                "votes": {
                    "deepseek": _vote_payload(ds_vote),
                    "gemini": _vote_payload(gm_vote),
                },
                "divergence": trace_row.get("divergence_json"),
            }
        )

    return {
        "run_id": run_id,
        "skill_id": run.get("skill_id") or report.get("skill_id"),
        "review_status": run.get("review_status") or report.get("review_status"),
        "evaluation_mode": run.get("evaluation_mode"),
        "prompt_version": report.get("prompt_version", "review-agent-v0.4"),
        "provider_summary": provider_summary.model_dump(),
        "cases": cases_out,
    }
