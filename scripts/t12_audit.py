"""T12 post-live audit: Q-10 score variance, Q-11 dimension nulls, Fix-4 report fields."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from skillhub_eval.persistence.sqlite import SqliteRepository

DB = ROOT / "data" / "t8_validation.db"
RUBRIC_KEYS = ("instruction_following", "output_compliance", "business_resolution")


def audit_run(repo: SqliteRepository, run_id: str, label: str) -> dict:
    report = repo.get_report(run_id) or {}
    votes = report.get("model_votes") or []
    result = {
        "label": label,
        "run_id": run_id,
        "status": report.get("status"),
        "q10_pass": None,
        "q11_pass": None,
        "fix4_pass": None,
        "ds_unique": [],
        "issues": [],
    }

    ds_scores: list[tuple[str, float | None]] = []
    null_dims: list[str] = []

    for v in votes:
        model = v.get("model", "")
        case = v.get("case_id", "?")
        st = v.get("score_total")
        if "deepseek" in model:
            ds_scores.append((case, st))

        dim = v.get("dimension_scores") or {}
        missing = [k for k in RUBRIC_KEYS if dim.get(k) is None]
        if missing:
            null_dims.append(f"{model}/{case}: missing {missing}")

        raw = json.dumps(dim)
        if "<integer" in raw.lower():
            result["issues"].append(f"placeholder leak {model}/{case}")

    if ds_scores:
        vals = [s for _, s in ds_scores if s is not None]
        uniq = sorted(set(vals))
        result["ds_unique"] = uniq
        result["q10_pass"] = len(uniq) >= 2 if len(vals) > 1 else len(uniq) == 1
        if len(vals) > 1 and len(uniq) <= 1:
            result["issues"].append(f"Q-10 FAIL: DS flat score {uniq}")

    if votes:
        result["q11_pass"] = len(null_dims) == 0
        if null_dims:
            result["issues"].extend(null_dims[:8])

    if report.get("status") == "awaiting_confirm":
        ok = (
            report.get("completeness_score") is not None
            and bool(report.get("gaps"))
            and bool(report.get("required_actions"))
        )
        result["fix4_pass"] = ok
        if not ok:
            result["issues"].append("Fix-4: incomplete awaiting_confirm report")

    return result


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    repo = SqliteRepository(str(DB))
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT run_id, skill_id, status FROM evaluation_runs ORDER BY created_at"
    ).fetchall()
    conn.close()

    labels = ["A1 grill-me", "A2 grill-me", "A3 grill-me", "B tiered", "C stock-radar"]
    all_ok = True
    for i, (rid, sid, _st) in enumerate(rows):
        lab = labels[i] if i < len(labels) else sid
        r = audit_run(repo, rid, lab)
        print(f"\n=== {r['label']} ({rid[:8]}…) status={r['status']} ===")
        if r["ds_unique"]:
            print(f"  DeepSeek unique totals: {r['ds_unique']}")
            print(f"  Q-10: {'PASS' if r['q10_pass'] else 'FAIL'}")
        if r["q11_pass"] is not None:
            print(f"  Q-11: {'PASS' if r['q11_pass'] else 'FAIL'}")
        if r["fix4_pass"] is not None:
            print(f"  Fix-4 API: {'PASS' if r['fix4_pass'] else 'FAIL'}")
        if r["issues"]:
            all_ok = False
            for issue in r["issues"]:
                print(f"  ! {issue}")

    # dump stock-radar DS per-case detail
    stock = [x for x in rows if "stock" in x[1]]
    if stock:
        report = repo.get_report(stock[0][0]) or {}
        print("\n--- C stock-radar model_votes (DeepSeek) ---")
        for v in report.get("model_votes") or []:
            if "deepseek" not in v.get("model", ""):
                continue
            print(
                f"  {v.get('case_id')}: total={v.get('score_total')} "
                f"dim={v.get('dimension_scores')}"
            )

    print("\n=== T12 AUDIT SUMMARY ===")
    print("OVERALL:", "PASS" if all_ok else "NEEDS REVIEW")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
