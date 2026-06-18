from skillhub_eval.core.execution_source import resolve_execution_source_name
from skillhub_eval.execution.local_agent_source import LocalAgentSource
from skillhub_eval.execution.preferences import set_preferences
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.settings import settings


class _FakeAdapter:
    def __init__(self, *, detected: bool):
        self._detected = detected

    def detect(self) -> bool:
        return self._detected


def test_routing_prefers_persisted_exec_source_over_env(monkeypatch, tmp_path):
    db_path = str(tmp_path / "prefs-routing.db")
    SqliteRepository(db_path).init_db()
    set_preferences(db_path=db_path, exec_source="local")

    monkeypatch.setattr(settings, "eval_db_path", db_path)
    monkeypatch.setattr(settings, "exec_source", "sample_io")

    assert resolve_execution_source_name({}) == "local"


def test_local_agent_source_uses_persisted_exec_agent(monkeypatch, tmp_path):
    db_path = str(tmp_path / "prefs-agent.db")
    SqliteRepository(db_path).init_db()
    set_preferences(db_path=db_path, exec_agent="codex")

    monkeypatch.setattr(settings, "eval_db_path", db_path)
    monkeypatch.setattr(settings, "exec_agent", "claude")
    monkeypatch.setattr(
        "skillhub_eval.execution.local_agent_source.has_exec_consent",
        lambda _skill_id: True,
    )

    calls: list[str] = []

    def _fake_resolve_adapter(agent_id: str):
        calls.append(agent_id)
        return _FakeAdapter(detected=False)

    monkeypatch.setattr(
        "skillhub_eval.execution.local_agent_source._resolve_adapter",
        _fake_resolve_adapter,
    )

    source = LocalAgentSource()
    result = source.get_actual_output(str(tmp_path), "h01", bundle={"skill_id": "demo"})

    assert calls == ["codex"]
    assert result.status == "incomplete"
    assert result.degrade_reason == "agent_unavailable"


def test_resolve_execution_source_without_row_defaults_to_local(monkeypatch, tmp_path):
    db_path = str(tmp_path / "prefs-default-local.db")
    SqliteRepository(db_path).init_db()

    monkeypatch.setattr(settings, "eval_db_path", db_path)
    monkeypatch.setattr(settings, "exec_source", "sample_io")

    assert resolve_execution_source_name({}) == "local"
