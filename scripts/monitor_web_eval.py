"""Background monitor for web UI eval + exec bridge calls."""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import datetime
from urllib.error import URLError
from urllib.request import urlopen

BASE = "http://127.0.0.1:8000"
DB = "data/skillhub_eval.db"
POLL_S = 3
MAX_LOOPS = 200  # ~10 min


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def get_json(path: str) -> dict | list | None:
    try:
        with urlopen(f"{BASE}{path}", timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        print(f"[{ts()}] GET {path} FAIL: {exc}", flush=True)
        return None


def latest_run_from_db() -> dict | None:
    try:
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT run_id, status, skill_id, created_at,
                   execution_source_used, level_achieved, spot_check_eligible
            FROM evaluation_runs
            WHERE status != 'superseded'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as exc:
        print(f"[{ts()}] DB read FAIL: {exc}", flush=True)
        return None


def run_stages(run_id: str) -> list[str]:
    try:
        conn = sqlite3.connect(DB)
        row = conn.execute(
            "SELECT stage_progress FROM evaluation_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        conn.close()
        if not row or not row[0]:
            return []
        return json.loads(row[0])
    except Exception:
        return []


def main() -> int:
    print(f"[{ts()}] MONITOR START base={BASE} db={DB}", flush=True)
    baseline_run = latest_run_from_db()
    baseline_id = baseline_run["run_id"] if baseline_run else None
    print(f"[{ts()}] baseline run={baseline_id}", flush=True)

    seen_runs: set[str] = set()
    last_prefs: str | None = None
    last_status: str | None = None
    last_stages: list[str] = []
    active_run_id: str | None = None

    for _i in range(MAX_LOOPS):
        health = get_json("/health")
        if not health:
            print(f"[{ts()}] server not reachable, waiting...", flush=True)
            time.sleep(POLL_S)
            continue

        prefs = get_json("/api/exec/preferences")
        if prefs:
            snap = json.dumps(
                {
                    "exec_source": prefs.get("exec_source"),
                    "exec_agent": prefs.get("exec_agent"),
                    "consent_granted": prefs.get("consent_granted"),
                    "ready": prefs.get("ready"),
                    "ready_reason": prefs.get("ready_reason"),
                },
                ensure_ascii=False,
            )
            if snap != last_prefs:
                print(f"[{ts()}] PREFERENCES {snap}", flush=True)
                last_prefs = snap

        run = latest_run_from_db()
        if run:
            rid = run["run_id"]
            if baseline_id and rid == baseline_id and not active_run_id:
                pass
            else:
                active_run_id = rid
                status = run.get("status")
                if rid not in seen_runs:
                    seen_runs.add(rid)
                    print(
                        f"[{ts()}] NEW RUN {rid[:8]}… skill={run.get('skill_id')} "
                        f"status={status}",
                        flush=True,
                    )
                if status != last_status:
                    print(
                        f"[{ts()}] RUN {rid[:8]}… status={status} "
                        f"exec_source_used={run.get('execution_source_used')} "
                        f"level={run.get('level_achieved')} "
                        f"spot_check={run.get('spot_check_eligible')}",
                        flush=True,
                    )
                    last_status = status
                stages = run_stages(rid)
                if stages != last_stages:
                    print(f"[{ts()}] RUN {rid[:8]}… stages={stages}", flush=True)
                    last_stages = stages

                if status in ("completed", "failed", "awaiting_human_review"):
                    report = get_json(f"/eval/report/{rid}")
                    if isinstance(report, dict):
                        print(
                            f"[{ts()}] REPORT {rid[:8]}… "
                            f"review_status={report.get('review_status')} "
                            f"execution_source_used={report.get('execution_source_used')} "
                            f"level_achieved={report.get('level_achieved')} "
                            f"error={report.get('error_detail')}",
                            flush=True,
                        )
                    print(f"[{ts()}] MONITOR DONE (terminal run state={status})", flush=True)
                    return 0

        time.sleep(POLL_S)

    print(f"[{ts()}] MONITOR TIMEOUT after {MAX_LOOPS * POLL_S}s", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
