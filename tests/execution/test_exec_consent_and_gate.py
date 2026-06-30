"""W8: exec consent gate + security blocked bundle must not spawn."""

import json

import pytest

from skillhub_eval.execution.consent import clear_exec_consent, grant_exec_consent
from skillhub_eval.execution.local_agent_source import LocalAgentSource
from skillhub_eval.execution.runner import LocalAgentRunner, _FakeProcess
from skillhub_eval.execution.workspace import PerRunWorkspace


class _CountingAdapter:
    agent_id = "claude"
    calls = 0

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        return ["stub"]

    def detect(self) -> bool:
        return True

    def parse_stream(self, lines: list[str]):
        from skillhub_eval.execution.stream_parser import parse_stream_events

        return parse_stream_events(lines)


@pytest.fixture(autouse=True)
def _reset_consent():
    clear_exec_consent()
    _CountingAdapter.calls = 0
    yield
    clear_exec_consent()


def test_local_agent_requires_consent_before_spawn(tmp_path, monkeypatch):
    from skillhub_eval.persistence.sqlite import SqliteRepository
    from skillhub_eval.settings import settings

    db_path = str(tmp_path / "no-consent.db")
    monkeypatch.setattr(settings, "eval_db_path", db_path)
    SqliteRepository(db_path).init_db()
    bundle = {
        "skill_id": "needs-consent",
        "bundle_path": str(tmp_path),
        "has_scripts": False,
    }
    lines = [json.dumps({"type": "result"})]

    def fake_spawn(args, **kwargs):
        _CountingAdapter.calls += 1
        return _FakeProcess(returncode=0, stdout_lines=[ln + "\n" for ln in lines])

    src = LocalAgentSource(
        runner=LocalAgentRunner(spawn_fn=fake_spawn),
        workspace=PerRunWorkspace(retain=True),
        adapter=_CountingAdapter(),
    )
    result = src.get_actual_output(
        bundle["bundle_path"],
        "h01",
        case={"id": "h01", "type": "happy_path"},
        bundle=bundle,
    )
    assert result.status == "incomplete"
    assert result.degrade_reason == "consent_required"
    assert _CountingAdapter.calls == 0

    grant_exec_consent("needs-consent")
    result2 = src.get_actual_output(
        bundle["bundle_path"],
        "h01",
        case={"id": "h01", "type": "happy_path"},
        bundle=bundle,
    )
    assert _CountingAdapter.calls == 1
    assert result2.status in ("ok", "incomplete")


def test_has_exec_consent_survives_memory_clear_from_sqlite(tmp_path, monkeypatch):
    """UI consent persists in sqlite; engine must honor it after serve restart."""
    from skillhub_eval.execution.consent import has_exec_consent
    from skillhub_eval.execution.preferences import grant_persisted_consent
    from skillhub_eval.persistence.sqlite import SqliteRepository
    from skillhub_eval.settings import settings

    db_path = str(tmp_path / "consent.db")
    monkeypatch.setattr(settings, "eval_db_path", db_path)
    monkeypatch.setattr(settings, "exec_consent_required", True)
    SqliteRepository(db_path).init_db()
    grant_persisted_consent(db_path=db_path)
    clear_exec_consent()
    assert has_exec_consent("restarted-skill") is True
