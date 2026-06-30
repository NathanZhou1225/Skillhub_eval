"""Global execution preferences persisted in sqlite."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from skillhub_eval.execution.consent import grant_exec_consent
from skillhub_eval.execution.agent_registry import (
    DEFAULT_MODEL_ID,
    get_agent_catalog,
    resolve_adapter,
)
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.settings import settings


@dataclass
class ExecPreferences:
    exec_source: str
    exec_agent: str
    exec_model: str
    consent_granted: bool
    ready: bool
    ready_reason: str | None = None


def get_preferences(*, db_path: str | None = None) -> dict:
    repo = _repo(db_path)
    repo.init_db()
    stored = repo.get_exec_preferences()
    defaults = _default_preferences()
    exec_source = str((stored or {}).get("exec_source") or defaults["exec_source"])
    exec_agent = str((stored or {}).get("exec_agent") or defaults["exec_agent"])
    exec_model = _effective_exec_model((stored or {}).get("exec_model"))
    consent_granted = bool((stored or {}).get("consent_granted", False))
    ready, ready_reason = compute_ready(exec_source, exec_agent, consent_granted)
    return asdict(
        ExecPreferences(
            exec_source=exec_source,
            exec_agent=exec_agent,
            exec_model=exec_model,
            consent_granted=consent_granted,
            ready=ready,
            ready_reason=ready_reason,
        )
    )


def set_preferences(
    *,
    db_path: str | None = None,
    exec_source: str | None = None,
    exec_agent: str | None = None,
    exec_model: str | None = None,
    consent_granted: bool | None = None,
) -> dict:
    repo = _repo(db_path)
    repo.init_db()
    repo.upsert_exec_preferences(
        exec_source=exec_source,
        exec_agent=exec_agent,
        exec_model=exec_model,
        consent_granted=consent_granted,
    )
    return get_preferences(db_path=db_path)


def get_exec_source(*, db_path: str | None = None) -> str:
    repo = _repo(db_path)
    repo.init_db()
    stored = repo.get_exec_preferences()
    if stored and stored.get("exec_source"):
        return str(stored["exec_source"])
    return "local"


def get_exec_agent(*, db_path: str | None = None) -> str:
    repo = _repo(db_path)
    repo.init_db()
    stored = repo.get_exec_preferences()
    if stored and stored.get("exec_agent"):
        return str(stored["exec_agent"])
    return _default_exec_agent()


def get_exec_model(*, db_path: str | None = None) -> str:
    repo = _repo(db_path)
    repo.init_db()
    stored = repo.get_exec_preferences()
    return _effective_exec_model((stored or {}).get("exec_model"))


def grant_persisted_consent(*, db_path: str | None = None) -> None:
    repo = _repo(db_path)
    repo.init_db()
    repo.upsert_exec_preferences(consent_granted=True)
    grant_exec_consent("*")


def compute_ready(
    exec_source: str,
    exec_agent: str,
    consent_granted: bool,
) -> tuple[bool, str | None]:
    source = (exec_source or "").strip()
    if source == "sample_io":
        return True, None
    if source != "local":
        return False, "invalid_exec_source"

    agent = (exec_agent or "").strip()
    if not agent:
        return False, "agent_not_selected"
    if not _is_agent_detected(agent):
        return False, "agent_unavailable"
    if settings.exec_consent_required and not consent_granted:
        return False, "consent_required"
    return True, None


def _default_preferences() -> dict:
    return {
        "exec_source": "local",
        "exec_agent": _default_exec_agent(),
        "exec_model": str(settings.exec_model or DEFAULT_MODEL_ID),
    }


def _effective_exec_model(stored_model: object | None) -> str:
    value = str(stored_model or "").strip()
    if value and value != DEFAULT_MODEL_ID:
        return value
    return str(settings.exec_model or DEFAULT_MODEL_ID)


def _default_exec_agent() -> str:
    configured = (settings.exec_agent or "").strip()
    if configured:
        return configured
    for agent in get_agent_catalog():
        candidate = agent.agent_id
        if _is_agent_detected(candidate):
            return candidate
    return "claude"


def _is_agent_detected(agent_id: str) -> bool:
    from skillhub_eval.execution.agent_registry import get_agent_def
    from skillhub_eval.execution.detection import detect_agent

    agent = get_agent_def(agent_id)
    return bool(agent and detect_agent(agent).detected)


def _resolve_adapter(agent_id: str):
    return resolve_adapter(agent_id)


def _repo(db_path: str | None) -> SqliteRepository:
    return SqliteRepository(db_path or settings.eval_db_path)
