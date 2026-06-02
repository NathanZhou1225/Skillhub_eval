import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from skillhub_eval.core.schemas import EvaluationReport

DDL = """
CREATE TABLE IF NOT EXISTS evaluation_runs (
    run_id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    skill_bundle_path TEXT NOT NULL,
    bundle_state TEXT NOT NULL,
    evaluation_mode TEXT NOT NULL,
    orchestration_mode TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    risk_level_locked TEXT,
    level_achieved TEXT,
    review_status TEXT,
    score_total REAL,
    score_total_source TEXT,
    completeness_score REAL,
    reason_codes TEXT DEFAULT '[]',
    report_json TEXT,
    human_review_required INTEGER DEFAULT 0,
    human_review_trigger_codes TEXT DEFAULT '[]',
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stage_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    entered_at TEXT NOT NULL,
    exited_at TEXT,
    metadata_json TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS model_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    case_id TEXT NOT NULL,
    vote_json TEXT NOT NULL,
    latency_ms INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gaps_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    gaps_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS human_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    action TEXT NOT NULL,
    operator TEXT NOT NULL,
    comment TEXT DEFAULT '',
    preserved_votes_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bundle_confirmations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL,
    field_path TEXT NOT NULL,
    confirmed_value TEXT,
    confirmed_by TEXT NOT NULL,
    confirmed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    payload_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);
"""


class SqliteRepository:
    def __init__(self, db_path: str = "data/skillhub_eval.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(DDL)

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def create_run(
        self,
        skill_id: str,
        skill_bundle_path: str,
        bundle_state: str,
        evaluation_mode: str,
    ) -> str:
        run_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO evaluation_runs (
                    run_id, skill_id, skill_bundle_path, bundle_state,
                    evaluation_mode, started_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    skill_id,
                    skill_bundle_path,
                    bundle_state,
                    evaluation_mode,
                    self._now(),
                    self._now(),
                ),
            )
        return run_id

    def update_status(self, run_id: str, status: str, **kwargs) -> None:
        sets = ["status=?"]
        vals: list = [status]
        allowed = {
            "risk_level_locked",
            "level_achieved",
            "review_status",
            "score_total",
            "score_total_source",
            "completeness_score",
            "reason_codes",
            "orchestration_mode",
            "completed_at",
        }
        for key, value in kwargs.items():
            if key in allowed:
                sets.append(f"{key}=?")
                vals.append(json.dumps(value) if isinstance(value, list) else value)
        if status in ("completed", "failed"):
            sets.append("completed_at=?")
            vals.append(self._now())
        vals.append(run_id)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE evaluation_runs SET {', '.join(sets)} WHERE run_id=?",
                vals,
            )

    def append_stage(
        self,
        run_id: str,
        stage: str,
        metadata: dict | None = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO stage_transitions (run_id, stage, entered_at, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, stage, self._now(), json.dumps(metadata or {})),
            )

    def save_report(self, run_id: str, report: EvaluationReport) -> None:
        report_json = report.model_dump_json()
        review_status = report.review_status
        if hasattr(review_status, "value"):
            review_status = review_status.value
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE evaluation_runs
                SET report_json=?, review_status=?, score_total=?, completed_at=?
                WHERE run_id=?
                """,
                (report_json, review_status, report.score_total, self._now(), run_id),
            )

    def get_run(self, run_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM evaluation_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_report(self, run_id: str) -> dict | None:
        row = self.get_run(run_id)
        if not row or not row.get("report_json"):
            return None
        return json.loads(row["report_json"])

    def list_history(
        self,
        limit: int = 50,
        human_review_required: bool | None = None,
    ) -> list[dict]:
        query = (
            "SELECT run_id, skill_id, status, review_status, score_total, "
            "bundle_state, evaluation_mode, human_review_required, created_at "
            "FROM evaluation_runs"
        )
        params: list = []
        if human_review_required is not None:
            query += " WHERE human_review_required=?"
            params.append(1 if human_review_required else 0)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def save_gaps(self, run_id: str, gaps_json: dict) -> None:
        skill_id = gaps_json.get("skill_id", "")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO gaps_snapshots (run_id, skill_id, gaps_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, skill_id, json.dumps(gaps_json), self._now()),
            )

    def get_gaps(self, skill_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT gaps_json FROM gaps_snapshots
                WHERE skill_id=? ORDER BY created_at DESC LIMIT 1
                """,
                (skill_id,),
            ).fetchone()
        return json.loads(row["gaps_json"]) if row else None

    def save_votes(self, run_id: str, votes: list[dict]) -> None:
        with self._conn() as conn:
            for vote in votes:
                conn.execute(
                    """
                    INSERT INTO model_votes (
                        run_id, provider, case_id, vote_json, latency_ms, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        vote.get("model", ""),
                        vote.get("case_id", ""),
                        json.dumps(vote),
                        vote.get("latency_ms", 0),
                        self._now(),
                    ),
                )

    def get_votes_for_run(self, run_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT vote_json FROM model_votes WHERE run_id=? ORDER BY id",
                (run_id,),
            ).fetchall()
        return [json.loads(row["vote_json"]) for row in rows]

    def save_human_review(
        self,
        run_id: str,
        action: str,
        operator: str,
        comment: str,
        preserved_votes: list[dict],
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO human_reviews (
                    run_id, action, operator, comment, preserved_votes_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    action,
                    operator,
                    comment,
                    json.dumps(preserved_votes),
                    self._now(),
                ),
            )
            conn.execute(
                "UPDATE evaluation_runs SET human_review_required=0 WHERE run_id=?",
                (run_id,),
            )

    def save_confirmation(
        self,
        skill_id: str,
        field_path: str,
        confirmed_value: str,
        operator: str,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO bundle_confirmations (
                    skill_id, field_path, confirmed_value, confirmed_by, confirmed_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (skill_id, field_path, confirmed_value, operator, self._now()),
            )

    def set_human_review_required(
        self,
        run_id: str,
        required: bool,
        trigger_codes: list[str],
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE evaluation_runs
                SET human_review_required=?, human_review_trigger_codes=?
                WHERE run_id=?
                """,
                (1 if required else 0, json.dumps(trigger_codes), run_id),
            )

    def log_event(self, run_id: str, event_name: str, payload: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO analytics_events (run_id, event_name, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, event_name, json.dumps(payload), self._now()),
            )
