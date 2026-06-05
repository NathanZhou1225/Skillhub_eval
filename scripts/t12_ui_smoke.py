"""T12 Fix-4: poll live API report for A1-shaped run (author台 diagnostic payload)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
GRILL = ROOT / "testskills" / "grill-me"
BASE = "http://127.0.0.1:8000"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    body = {
        "skill_id": "grill-me",
        "skill_bundle_path": str(GRILL),
        "bundle_state": "minimal",
        "evaluation_mode": "capability_full",
    }
    with httpx.Client(timeout=120.0) as client:
        r = client.get(f"{BASE}/health")
        if r.status_code != 200:
            print("FAIL: server not healthy")
            return 1

        run = client.post(f"{BASE}/eval/run", json=body)
        run.raise_for_status()
        run_id = run.json()["run_id"]
        print(f"Started run {run_id}")

        for _ in range(30):
            rep = client.get(f"{BASE}/eval/report/{run_id}")
            rep.raise_for_status()
            data = rep.json()
            status = data.get("status")
            if status in ("awaiting_confirm", "completed", "failed", "awaiting_human_review"):
                break
            time.sleep(2)
        else:
            print("FAIL: poll timeout")
            return 1

        report = data.get("report") or {}
        ui = client.get(f"{BASE}/ui/index.html")
        ui_ok = "renderDiagnosticReportCard" in ui.text and "结构诊断报告" in ui.text

        checks = {
            "status_awaiting_confirm": status == "awaiting_confirm",
            "completeness_score": report.get("completeness_score") is not None,
            "gaps_nonempty": bool(report.get("gaps")),
            "required_actions": bool(report.get("required_actions")),
            "ui_helpers_present": ui_ok,
        }
        print(json.dumps({"run_id": run_id, "status": status, "checks": checks}, ensure_ascii=False, indent=2))
        if report.get("gaps"):
            print("gap_fields:", [g.get("field_path") for g in report["gaps"][:6]])
        return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
