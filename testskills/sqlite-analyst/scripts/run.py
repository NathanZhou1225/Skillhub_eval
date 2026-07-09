"""Read-only SQLite analysis entrypoint for local agent evaluation."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED_SQL = ROOT / "data" / "portfolio_seed.sql"


DENIED_SQL_PREFIXES = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "vacuum",
    "attach",
    "pragma",
)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SEED_SQL.read_text(encoding="utf-8"))
    return conn


def _query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    first = sql.strip().split(None, 1)[0].lower() if sql.strip() else ""
    if first in DENIED_SQL_PREFIXES:
        raise PermissionError("write_sql_denied")
    return conn.execute(sql, params).fetchall()


def _schema() -> dict:
    with _connect() as conn:
        tables = [row["name"] for row in _query(
            conn,
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
        )]
        columns = {
            table: [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]
            for table in tables
        }
    return {
        "status": "success",
        "action": "schema",
        "table_count": len(tables),
        "tables": tables,
        "columns": columns,
    }


def _aggregate() -> dict:
    with _connect() as conn:
        row = _query(
            conn,
            """
            SELECT
              COUNT(*) AS position_count,
              ROUND(SUM(market_value), 2) AS total_market_value,
              ROUND(SUM(unrealized_pnl), 2) AS total_unrealized_pnl
            FROM positions
            """,
        )[0]
        sectors = _query(
            conn,
            """
            SELECT sector, ROUND(SUM(market_value), 2) AS market_value
            FROM positions
            GROUP BY sector
            ORDER BY market_value DESC
            """
        )
    return {
        "status": "success",
        "action": "aggregate",
        "position_count": row["position_count"],
        "total_market_value": row["total_market_value"],
        "total_unrealized_pnl": row["total_unrealized_pnl"],
        "top_sector": sectors[0]["sector"],
        "sector_count": len(sectors),
    }


def _anomaly() -> dict:
    with _connect() as conn:
        rows = _query(
            conn,
            """
            SELECT ticker, sector, weight_pct
            FROM positions
            WHERE weight_pct > 25 OR weight_pct < 5
            ORDER BY weight_pct DESC
            """
        )
    return {
        "status": "success",
        "action": "anomaly",
        "anomaly_count": len(rows),
        "tickers": [row["ticker"] for row in rows],
        "rule": "weight_pct > 25 OR weight_pct < 5",
    }


def _refuse_write() -> dict:
    try:
        with _connect() as conn:
            _query(conn, "DROP TABLE positions")
    except PermissionError:
        return {
            "status": "denied",
            "action": "refuse_write",
            "reason": "write_sql_denied",
            "allowed_sql": "SELECT only",
        }
    return {"status": "error", "action": "refuse_write", "reason": "unexpected_write_allowed"}


def _invalid_query() -> dict:
    try:
        with _connect() as conn:
            _query(conn, "SELECT missing_column FROM positions")
    except sqlite3.Error:
        return {
            "status": "error",
            "action": "invalid_query",
            "reason": "invalid_sql",
        }
    return {"status": "error", "action": "invalid_query", "reason": "unexpected_success"}


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "aggregate"
    try:
        if action == "schema":
            payload = _schema()
        elif action == "aggregate":
            payload = _aggregate()
        elif action == "anomaly":
            payload = _anomaly()
        elif action == "refuse_write":
            payload = _refuse_write()
        elif action == "invalid_query":
            payload = _invalid_query()
        else:
            payload = {"status": "error", "action": action, "reason": "unsupported_action"}
    except Exception as exc:  # noqa: BLE001 - entrypoint should emit JSON for harnesses.
        payload = {"status": "error", "action": action, "reason": str(exc)}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
