"""SQLite persistence for SkillHub eval engine.

Conversation status values (Wave 5.2 propagation/clarify flow):
  awaiting_propagation_confirm, awaiting_propagation_clarify,
  awaiting_manual_upload, awaiting_clarify
"""
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from skillhub_eval.core.schemas import EvaluationReport
from skillhub_eval.core.stage_timing import summarize_stage_timings

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
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    active_run_id TEXT,
    auto_run_count INTEGER NOT NULL DEFAULT 0,
    max_auto_runs INTEGER NOT NULL DEFAULT 5,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lui_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    run_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exec_preferences (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    exec_source TEXT NOT NULL DEFAULT 'local',
    exec_agent TEXT NOT NULL DEFAULT 'claude',
    exec_model TEXT NOT NULL DEFAULT 'default',
    consent_granted INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""


class SqliteRepository:
    SCHEMA_VERSION = 11

    def __init__(self, db_path: str = "data/skillhub_eval.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Single-transaction schema init and migration (no executescript)."""
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
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
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS stage_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    entered_at TEXT NOT NULL,
                    exited_at TEXT,
                    metadata_json TEXT DEFAULT '{}'
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS model_votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    vote_json TEXT NOT NULL,
                    latency_ms INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS gaps_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    skill_id TEXT NOT NULL,
                    gaps_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS human_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    comment TEXT DEFAULT '',
                    preserved_votes_json TEXT DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS bundle_confirmations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_id TEXT NOT NULL,
                    field_path TEXT NOT NULL,
                    confirmed_value TEXT,
                    confirmed_by TEXT NOT NULL,
                    confirmed_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    payload_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    active_run_id TEXT,
                    auto_run_count INTEGER NOT NULL DEFAULT 0,
                    auto_confirmed INTEGER NOT NULL DEFAULT 0,
                    max_auto_runs INTEGER NOT NULL DEFAULT 5,
                    source_path TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lui_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    run_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    message_type TEXT NOT NULL DEFAULT 'text',
                    payload_json TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS exec_preferences (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    exec_source TEXT NOT NULL DEFAULT 'local',
                    exec_agent TEXT NOT NULL DEFAULT 'claude',
                    exec_model TEXT NOT NULL DEFAULT 'default',
                    consent_granted INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )

            version = cursor.execute("PRAGMA user_version").fetchone()[0]
            if version < 1:
                existing = {
                    row[1]
                    for row in cursor.execute(
                        "PRAGMA table_info('evaluation_runs')"
                    ).fetchall()
                }
                for col, typedef in [
                    ("conversation_id", "TEXT"),
                    ("parent_run_id", "TEXT"),
                    ("superseded_by_run_id", "TEXT"),
                ]:
                    if col not in existing:
                        cursor.execute(
                            f"ALTER TABLE evaluation_runs ADD COLUMN {col} {typedef}"
                        )
                cursor.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")

            if version < 2:
                existing_cols = {
                    row[1]
                    for row in cursor.execute(
                        "PRAGMA table_info('conversations')"
                    ).fetchall()
                }
                for col, typedef in [
                    ("auto_confirmed", "INTEGER NOT NULL DEFAULT 0"),
                    ("source_path", "TEXT"),
                ]:
                    if col not in existing_cols:
                        cursor.execute(
                            f"ALTER TABLE conversations ADD COLUMN {col} {typedef}"
                        )
                cursor.execute("PRAGMA user_version = 2")

            if version < 3:
                msg_cols = {
                    row[1]
                    for row in cursor.execute(
                        "PRAGMA table_info('lui_messages')"
                    ).fetchall()
                }
                if "message_type" not in msg_cols:
                    cursor.execute(
                        "ALTER TABLE lui_messages ADD COLUMN "
                        "message_type TEXT NOT NULL DEFAULT 'text'"
                    )
                if "payload_json" not in msg_cols:
                    cursor.execute(
                        "ALTER TABLE lui_messages ADD COLUMN payload_json TEXT"
                    )
                cursor.execute("PRAGMA user_version = 3")

            if version < 4:
                conv_cols = {
                    row[1]
                    for row in cursor.execute(
                        "PRAGMA table_info('conversations')"
                    ).fetchall()
                }
                if "pending_patch_json" not in conv_cols:
                    cursor.execute(
                        "ALTER TABLE conversations ADD COLUMN pending_patch_json TEXT"
                    )
                cursor.execute("PRAGMA user_version = 4")

            if version < 5:
                conv_cols = {
                    row[1]
                    for row in cursor.execute(
                        "PRAGMA table_info('conversations')"
                    ).fetchall()
                }
                if "clarifications_json" not in conv_cols:
                    cursor.execute(
                        "ALTER TABLE conversations ADD COLUMN clarifications_json TEXT"
                    )
                cursor.execute("PRAGMA user_version = 5")

            if version < 6:
                conv_cols = {
                    row[1]
                    for row in cursor.execute(
                        "PRAGMA table_info('conversations')"
                    ).fetchall()
                }
                if "plan_enrichment_json" not in conv_cols:
                    cursor.execute(
                        "ALTER TABLE conversations ADD COLUMN plan_enrichment_json TEXT"
                    )
                cursor.execute("PRAGMA user_version = 6")

            if version < 7:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS judge_traces (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL,
                        case_id TEXT NOT NULL,
                        prompt_text TEXT NOT NULL,
                        divergence_json TEXT,
                        created_at TEXT NOT NULL,
                        UNIQUE(run_id, case_id)
                    )
                    """
                )
                cursor.execute("PRAGMA user_version = 7")

            if version < 8:
                conv_cols = {
                    row[1]
                    for row in cursor.execute(
                        "PRAGMA table_info('conversations')"
                    ).fetchall()
                }
                if "archived_at" not in conv_cols:
                    cursor.execute(
                        "ALTER TABLE conversations ADD COLUMN archived_at TEXT"
                    )
                cursor.execute("PRAGMA user_version = 8")

            if version < 9:
                run_cols = {
                    row[1]
                    for row in cursor.execute(
                        "PRAGMA table_info('evaluation_runs')"
                    ).fetchall()
                }
                if "spot_check_eligible" not in run_cols:
                    cursor.execute(
                        "ALTER TABLE evaluation_runs "
                        "ADD COLUMN spot_check_eligible INTEGER NOT NULL DEFAULT 0"
                    )
                if "execution_source_used" not in run_cols:
                    cursor.execute(
                        "ALTER TABLE evaluation_runs "
                        "ADD COLUMN execution_source_used TEXT"
                    )
                cursor.execute("PRAGMA user_version = 9")
            if version < 10:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS exec_preferences (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        exec_source TEXT NOT NULL DEFAULT 'local',
                        exec_agent TEXT NOT NULL DEFAULT 'claude',
                        exec_model TEXT NOT NULL DEFAULT 'default',
                        consent_granted INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cursor.execute("PRAGMA user_version = 10")
            if version < 11:
                pref_cols = {
                    row[1]
                    for row in cursor.execute(
                        "PRAGMA table_info('exec_preferences')"
                    ).fetchall()
                }
                if "exec_model" not in pref_cols:
                    cursor.execute(
                        "ALTER TABLE exec_preferences "
                        "ADD COLUMN exec_model TEXT NOT NULL DEFAULT 'default'"
                    )
                cursor.execute("PRAGMA user_version = 11")
        return datetime.now(UTC).isoformat()

    def get_exec_preferences(self) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM exec_preferences WHERE id = 1"
            ).fetchone()
        return dict(row) if row else None

    def upsert_exec_preferences(
        self,
        *,
        exec_source: str | None = None,
        exec_agent: str | None = None,
        exec_model: str | None = None,
        consent_granted: bool | None = None,
    ) -> dict:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM exec_preferences WHERE id = 1"
            ).fetchone()
            source = (
                exec_source
                if exec_source is not None
                else (row["exec_source"] if row else "local")
            )
            agent = (
                exec_agent
                if exec_agent is not None
                else (row["exec_agent"] if row else "claude")
            )
            model = (
                exec_model
                if exec_model is not None
                else (row["exec_model"] if row else "default")
            )
            consent = (
                bool(consent_granted)
                if consent_granted is not None
                else bool(row["consent_granted"]) if row else False
            )
            conn.execute(
                """
                INSERT INTO exec_preferences (
                    id, exec_source, exec_agent, exec_model, consent_granted, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    exec_source=excluded.exec_source,
                    exec_agent=excluded.exec_agent,
                    exec_model=excluded.exec_model,
                    consent_granted=excluded.consent_granted,
                    updated_at=excluded.updated_at
                """,
                (source, agent, model, 1 if consent else 0, self._now()),
            )
            saved = conn.execute(
                "SELECT * FROM exec_preferences WHERE id = 1"
            ).fetchone()
        return dict(saved)

    def create_conversation(
        self,
        skill_id: str,
        source: str,
        max_auto_runs: int = 5,
        source_path: str = "",
    ) -> str:
        conv_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO conversations
                    (
                        conversation_id, skill_id, source, max_auto_runs,
                        source_path, created_at
                    )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (conv_id, skill_id, source, max_auto_runs, source_path, self._now()),
            )
        return conv_id

    def set_conversation_source(self, conversation_id: str, source: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE conversations SET source=? WHERE conversation_id=?",
                (source, conversation_id),
            )

    def set_conversation_source_path(
        self,
        conversation_id: str,
        source_path: str,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE conversations SET source_path=? WHERE conversation_id=?",
                (source_path, conversation_id),
            )

    def increment_auto_run_count(self, conversation_id: str) -> int:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE conversations
                SET auto_run_count = auto_run_count + 1
                WHERE conversation_id=?
                """,
                (conversation_id,),
            )
            row = conn.execute(
                "SELECT auto_run_count FROM conversations WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
        return int(row["auto_run_count"]) if row else 0

    def reset_auto_run_count(self, conversation_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE conversations SET auto_run_count=0 WHERE conversation_id=?",
                (conversation_id,),
            )

    def set_conversation_auto_confirmed(self, conversation_id: str, value: bool) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE conversations SET auto_confirmed=? WHERE conversation_id=?",
                (1 if value else 0, conversation_id),
            )

    def set_pending_patch(self, conversation_id: str, patch: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE conversations
                SET pending_patch_json=?, status='awaiting_draft_confirm'
                WHERE conversation_id=?
                """,
                (json.dumps(patch, ensure_ascii=False), conversation_id),
            )

    def get_pending_patch(self, conversation_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT pending_patch_json FROM conversations WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
        if not row or not row["pending_patch_json"]:
            return None
        try:
            parsed = json.loads(row["pending_patch_json"])
        except (TypeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def clear_pending_patch(self, conversation_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE conversations
                SET pending_patch_json=NULL, status='active'
                WHERE conversation_id=?
                """,
                (conversation_id,),
            )

    def get_clarifications(self, conversation_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT clarifications_json FROM conversations WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
        if not row or not row["clarifications_json"]:
            return None
        try:
            parsed = json.loads(row["clarifications_json"])
        except (TypeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def merge_clarifications(self, conversation_id: str, patch: dict) -> None:
        existing = self.get_clarifications(conversation_id) or {}
        merged = {**existing, **patch}
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE conversations
                SET clarifications_json=?
                WHERE conversation_id=?
                """,
                (json.dumps(merged, ensure_ascii=False), conversation_id),
            )

    def get_plan_enrichment(self, conversation_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT plan_enrichment_json FROM conversations WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
        if not row or not row["plan_enrichment_json"]:
            return None
        try:
            parsed = json.loads(row["plan_enrichment_json"])
        except (TypeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def set_plan_enrichment(self, conversation_id: str, payload: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE conversations
                SET plan_enrichment_json=?
                WHERE conversation_id=?
                """,
                (json.dumps(payload, ensure_ascii=False), conversation_id),
            )

    def get_conversation(self, conversation_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_conversation_status(self, conversation_id: str, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE conversations SET status=? WHERE conversation_id=?",
                (status, conversation_id),
            )

    def archive_conversation(self, conversation_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT status FROM conversations WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            if row is None or row["status"] == "archived":
                return False
            conn.execute(
                """
                UPDATE conversations
                SET status='archived', archived_at=?
                WHERE conversation_id=?
                """,
                (self._now(), conversation_id),
            )
            return True

    def set_conversation_skill_id(self, conversation_id: str, skill_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE conversations SET skill_id=? WHERE conversation_id=?",
                (skill_id, conversation_id),
            )

    def append_lui_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        run_id: str | None = None,
        message_type: str = "text",
        payload_json: dict | None = None,
    ) -> None:
        payload_str = json.dumps(payload_json) if payload_json is not None else None
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO lui_messages
                    (conversation_id, run_id, role, content,
                     message_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    run_id,
                    role,
                    content,
                    message_type,
                    payload_str,
                    self._now(),
                ),
            )

    def has_rich_report_for_run(self, conversation_id: str, run_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM lui_messages
                WHERE conversation_id=?
                  AND message_type='rich_report'
                  AND run_id=?
                LIMIT 1
                """,
                (conversation_id, run_id),
            ).fetchone()
        return row is not None

    def list_conversations(
        self,
        limit: int = 50,
        pending_review: bool | None = None,
    ) -> list[dict]:
        query = """
            SELECT
                c.*,
                (
                    SELECT COUNT(*) FROM lui_messages m
                    WHERE m.conversation_id = c.conversation_id
                ) AS lui_message_count,
                (
                    SELECT m.content FROM lui_messages m
                    WHERE m.conversation_id = c.conversation_id
                    ORDER BY m.created_at DESC, m.id DESC
                    LIMIT 1
                ) AS last_message_preview,
                (
                    SELECT MAX(m.created_at) FROM lui_messages m
                    WHERE m.conversation_id = c.conversation_id
                ) AS last_message_at,
                CASE WHEN r.human_review_required = 1
                      AND r.status = 'awaiting_human_review'
                     THEN 1 ELSE 0 END AS human_review_pending,
                r.status AS active_run_status
            FROM conversations c
            LEFT JOIN evaluation_runs r ON r.run_id = c.active_run_id
            WHERE c.status != 'archived'
        """
        params: list = []
        if pending_review is True:
            query += (
                " AND r.human_review_required = 1"
                " AND r.status = 'awaiting_human_review'"
            )
        elif pending_review is False:
            query += (
                " AND NOT (r.human_review_required = 1"
                " AND r.status = 'awaiting_human_review')"
            )
        query += """
            ORDER BY COALESCE(last_message_at, c.created_at) DESC
            LIMIT ?
        """
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["human_review_pending"] = bool(d.get("human_review_pending"))
            d["lui_message_count"] = int(d.get("lui_message_count") or 0)
            results.append(d)
        return results

    def get_lui_messages(self, conversation_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM lui_messages
                WHERE conversation_id=?
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            raw = d.get("payload_json")
            if raw:
                try:
                    d["payload_json"] = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    d["payload_json"] = None
            else:
                d["payload_json"] = None
            d.setdefault("message_type", "text")
            result.append(d)
        return result

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def create_run(
        self,
        skill_id: str,
        skill_bundle_path: str,
        bundle_state: str,
        evaluation_mode: str,
        conversation_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> str:
        run_id = str(uuid.uuid4())
        with self._conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO evaluation_runs (
                    run_id, skill_id, skill_bundle_path, bundle_state,
                    evaluation_mode, conversation_id, parent_run_id,
                    started_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    skill_id,
                    skill_bundle_path,
                    bundle_state,
                    evaluation_mode,
                    conversation_id,
                    parent_run_id,
                    self._now(),
                    self._now(),
                ),
            )
            if conversation_id:
                cursor.execute(
                    "UPDATE conversations SET active_run_id=? WHERE conversation_id=?",
                    (run_id, conversation_id),
                )
        return run_id

    def supersede_run(self, old_run_id: str, new_run_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE evaluation_runs
                SET status=?, superseded_by_run_id=?
                WHERE run_id=?
                """,
                ("superseded", new_run_id, old_run_id),
            )

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
            "superseded_by_run_id",
            "spot_check_eligible",
            "execution_source_used",
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

    def get_stage_progress(self, run_id: str) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT stage FROM stage_transitions
                WHERE run_id=? ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
            budget_rows = conn.execute(
                """
                SELECT payload_json FROM analytics_events
                WHERE run_id=? AND event_name='stage_budget'
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
        progress: list = [row["stage"] for row in rows]
        for row in budget_rows:
            try:
                payload = json.loads(row["payload_json"] or "{}")
            except json.JSONDecodeError:
                continue
            progress.append({"event": "stage_budget", **payload})
        return progress

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

    def patch_report_after_human_review(
        self,
        run_id: str,
        action: str,
        operator: str,
        comment: str,
        review_status: str,
        narrative_override=None,
    ) -> None:
        """T5/Q6: merge expert ruling into persisted report_json."""
        report = self.get_report(run_id)
        if not report:
            return
        if narrative_override is not None:
            report["narrative"] = (
                narrative_override.model_dump()
                if hasattr(narrative_override, "model_dump")
                else dict(narrative_override)
            )
        hr = report.get("human_review") or {}
        hr["reviewer_action"] = action
        hr["operator"] = operator
        hr["comment"] = comment
        hr["required"] = False
        report["human_review"] = hr
        report["status"] = "completed"
        report["review_status"] = review_status
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE evaluation_runs
                SET report_json=?, review_status=?, status=?, completed_at=?
                WHERE run_id=?
                """,
                (
                    json.dumps(report),
                    review_status,
                    "completed",
                    self._now(),
                    run_id,
                ),
            )

    def list_history(
        self,
        limit: int = 50,
        human_review_required: bool | None = None,
        spot_check_eligible: bool | None = None,
        execution_source_used: str | None = None,
    ) -> list[dict]:
        query = (
            "SELECT run_id, skill_id, status, review_status, score_total, "
            "score_total_source, reason_codes, bundle_state, evaluation_mode, "
            "human_review_required, conversation_id, created_at, "
            "spot_check_eligible, execution_source_used "
            "FROM evaluation_runs WHERE status != 'superseded'"
        )
        params: list = []
        if human_review_required is not None:
            query += " AND human_review_required=?"
            params.append(1 if human_review_required else 0)
        if spot_check_eligible is not None:
            query += " AND spot_check_eligible=?"
            params.append(1 if spot_check_eligible else 0)
        if execution_source_used is not None:
            query += " AND execution_source_used=?"
            params.append(execution_source_used)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        runs = []
        for row in rows:
            d = dict(row)
            raw_codes = d.get("reason_codes")
            try:
                d["reason_codes"] = json.loads(raw_codes) if raw_codes else []
            except (TypeError, json.JSONDecodeError):
                d["reason_codes"] = []
            runs.append(d)
        self._enrich_history_conversation_fields(runs)
        summaries = self.get_stage_timing_summaries([r["run_id"] for r in runs])
        for r in runs:
            r["timing_summary"] = summaries.get(r["run_id"], {})
        return runs

    def _enrich_history_conversation_fields(self, runs: list[dict]) -> None:
        conv_ids = [
            r["conversation_id"] for r in runs if r.get("conversation_id")
        ]
        if not conv_ids:
            for r in runs:
                r["lui_message_count"] = 0
                r["last_message_preview"] = None
            return

        placeholders = ",".join("?" for _ in conv_ids)
        with self._conn() as conn:
            count_rows = conn.execute(
                f"""
                SELECT conversation_id, COUNT(*) AS cnt
                FROM lui_messages
                WHERE conversation_id IN ({placeholders})
                GROUP BY conversation_id
                """,
                conv_ids,
            ).fetchall()
            preview_rows = conn.execute(
                f"""
                SELECT m.conversation_id, m.content
                FROM lui_messages m
                INNER JOIN (
                    SELECT conversation_id, MAX(id) AS max_id
                    FROM lui_messages
                    WHERE conversation_id IN ({placeholders})
                    GROUP BY conversation_id
                ) latest ON m.id = latest.max_id
                """,
                conv_ids,
            ).fetchall()

        counts = {row["conversation_id"]: int(row["cnt"]) for row in count_rows}
        previews = {
            row["conversation_id"]: row["content"] for row in preview_rows
        }
        for r in runs:
            conv_id = r.get("conversation_id")
            if conv_id:
                r["lui_message_count"] = counts.get(conv_id, 0)
                r["last_message_preview"] = previews.get(conv_id)
            else:
                r["lui_message_count"] = 0
                r["last_message_preview"] = None

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

    def save_judge_trace(
        self,
        run_id: str,
        case_id: str,
        prompt_text: str,
        divergence_json: dict | None = None,
    ) -> None:
        div_raw = json.dumps(divergence_json) if divergence_json is not None else None
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO judge_traces (
                    run_id, case_id, prompt_text, divergence_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id, case_id) DO UPDATE SET
                    prompt_text=excluded.prompt_text,
                    divergence_json=COALESCE(excluded.divergence_json, judge_traces.divergence_json)
                """,
                (run_id, case_id, prompt_text, div_raw, self._now()),
            )

    def update_judge_trace_divergence(
        self,
        run_id: str,
        case_id: str,
        divergence_json: dict,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE judge_traces
                SET divergence_json=?
                WHERE run_id=? AND case_id=?
                """,
                (json.dumps(divergence_json), run_id, case_id),
            )

    def get_judge_traces(self, run_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT case_id, prompt_text, divergence_json
                FROM judge_traces WHERE run_id=? ORDER BY id
                """,
                (run_id,),
            ).fetchall()
        result: list[dict] = []
        for row in rows:
            div = None
            if row["divergence_json"]:
                try:
                    div = json.loads(row["divergence_json"])
                except json.JSONDecodeError:
                    div = None
            result.append(
                {
                    "case_id": row["case_id"],
                    "prompt_text": row["prompt_text"],
                    "divergence_json": div,
                }
            )
        return result

    def has_judge_traces(self, run_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM judge_traces WHERE run_id=? LIMIT 1",
                (run_id,),
            ).fetchone()
        return row is not None

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

    def get_confirmations(self, skill_id: str) -> dict[str, str]:
        """Return latest confirmed value per field_path for a skill."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT field_path, confirmed_value FROM bundle_confirmations
                WHERE skill_id=? ORDER BY confirmed_at ASC
                """,
                (skill_id,),
            ).fetchall()
        result: dict[str, str] = {}
        for row in rows:
            result[row["field_path"]] = row["confirmed_value"]
        return result

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

    def list_events(self, run_id: str, event_name: str | None = None) -> list[dict]:
        query = """
            SELECT event_name, payload_json, created_at
            FROM analytics_events
            WHERE run_id=?
        """
        params: list[object] = [run_id]
        if event_name is not None:
            query += " AND event_name=?"
            params.append(event_name)
        query += " ORDER BY id ASC"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        events: list[dict] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"] or "{}")
            except json.JSONDecodeError:
                payload = {}
            events.append(
                {
                    "event_name": row["event_name"],
                    "payload": payload,
                    "created_at": row["created_at"],
                }
            )
        return events

    def get_provider_errors(self, run_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT payload_json FROM analytics_events
                WHERE run_id=? AND event_name='provider_error'
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
        result: list[dict] = []
        for row in rows:
            try:
                result.append(json.loads(row["payload_json"]))
            except (TypeError, json.JSONDecodeError):
                continue
        return result

    def get_stage_timings(self, run_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT payload_json FROM analytics_events
                WHERE run_id=? AND event_name='stage_timing'
                ORDER BY id ASC
                """,
                (run_id,),
            ).fetchall()
        result: list[dict] = []
        for row in rows:
            try:
                result.append(json.loads(row["payload_json"]))
            except (TypeError, json.JSONDecodeError):
                continue
        return result

    def get_stage_timing_summaries(self, run_ids: list[str]) -> dict[str, dict]:
        if not run_ids:
            return {}
        placeholders = ",".join("?" * len(run_ids))
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT run_id, payload_json FROM analytics_events
                WHERE run_id IN ({placeholders}) AND event_name='stage_timing'
                ORDER BY id ASC
                """,
                run_ids,
            ).fetchall()
        by_run: dict[str, list[dict]] = {}
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            by_run.setdefault(row["run_id"], []).append(payload)
        return {
            run_id: summarize_stage_timings(events)
            for run_id, events in by_run.items()
        }
