"""SQLite-backed runtime preflight cache helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from skillhub_eval.persistence.sqlite import SqliteRepository


def get_valid_runtime_preflight(
    repo: SqliteRepository,
    *,
    runtime_id: str,
    model_id: str,
    skill_fingerprint: str,
    fingerprint: str,
    now: datetime | str | None = None,
) -> dict | None:
    entry = repo.get_runtime_preflight(
        runtime_id=runtime_id,
        model_id=model_id,
        skill_fingerprint=skill_fingerprint,
    )
    if not entry:
        return None
    if entry.get("status") != "passed":
        return None
    if entry.get("fingerprint") != fingerprint:
        return None

    expires_at = _parse_iso_datetime(entry.get("expires_at"))
    if expires_at is None:
        return None
    if expires_at <= _parse_now(now):
        return None

    return entry


def _parse_now(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = _parse_iso_datetime(value)
        if parsed is None:
            raise ValueError(f"Invalid ISO timestamp: {value!r}")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
