"""
Tests for POST /conversations/start (Wave 3, Task 4).

Strategy: mock everything external to the route logic so no real DB,
filesystem, or LLM calls are made.  Each test controls exactly one
variable (security status, propagation need, etc.).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.case_sanitizer import SanitizerResult
from skillhub_eval.core.propagator import PropagatorResult
from skillhub_eval.core.security_scan import SecurityScanResult


# ── helpers ───────────────────────────────────────────────────────────────────

_VALID_BUNDLE = {
    "skill_md_text": "---\nname: test-skill\n---\n# Test Skill\n" + ("x" * 200),
    "skill_meta": {
        "name": "test-skill",
        "category": "fin-research/quant-signal",
        "description": "这是一个足够长的 Skill 描述，用于在 complete cases 测试中跳过 L0 purpose 澄清门槛。",
    },
    "risk_level_declared": "low",
    "eval_cases": [{"id": "c1", "type": "happy_path"}],
    "n_cases": 1,
}

_MOCK_CONV_ID = "conv-test-1234"
_MOCK_RUN_ID = "run-test-5678"


def _make_repo(conv_id: str = _MOCK_CONV_ID, run_id: str = _MOCK_RUN_ID) -> MagicMock:
    repo = MagicMock()
    repo.create_conversation.return_value = conv_id
    repo.create_run.return_value = run_id
    repo.update_conversation_status.return_value = None
    repo.get_conversation.return_value = {
        "status": "active",
        "auto_run_count": 0,
        "max_auto_runs": 5,
    }
    repo.get_lui_messages.return_value = []
    return repo


def _make_resolver(staging_path: Path) -> MagicMock:
    resolver = MagicMock()
    resolver.ref.staging_path = staging_path
    resolver.ensure_staging.return_value = None
    return resolver


def _make_sanitizer_result(needs_propagation: bool = False) -> SanitizerResult:
    return SanitizerResult(
        broken_moved=0,
        invalid_type_count=0,
        gap_by_type={"happy_path": 2} if needs_propagation else {"happy_path": 0},
        needs_propagation=needs_propagation,
        existing_counts={"happy_path": 1} if not needs_propagation else {},
    )


def _make_prop_result(used_fallback: bool = False) -> PropagatorResult:
    result = PropagatorResult()
    result.used_fallback = used_fallback
    if used_fallback:
        result.cases_failed = ["prop_happy_01"]
    else:
        result.cases_written = ["prop_happy_01"]
    return result


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client(tmp_path):
    """Test client with repo + ds_provider + gemini overridden; engine mocked."""
    app = create_app()
    repo = _make_repo()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: MagicMock()
    app.dependency_overrides[get_gemini_provider] = lambda: MagicMock()
    with patch("skillhub_eval.adapters.api.routes.conversations.EvaluationEngine") as mock_engine_cls:
        mock_engine_cls.return_value.run_async = AsyncMock()
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c, repo, tmp_path


# ── test 1: security blocked → 422, no run, conversation status updated ───────

def test_security_blocked_returns_422(client):
    test_client, repo, tmp_path = client
    staging = tmp_path / "conv-test-1234"
    staging.mkdir()

    blocked_result = SecurityScanResult(status="blocked", findings=[])

    with (
        patch(
            "skillhub_eval.adapters.api.routes.conversations.BundleResolver.from_settings",
            return_value=_make_resolver(staging),
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.ingest_bundle",
            return_value=_VALID_BUNDLE,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.security_scan",
            return_value=blocked_result,
        ),
    ):
        resp = test_client.post(
            "/conversations/start",
            json={
                "skill_id": "skill-x",
                "skill_bundle_path": str(tmp_path / "bundle"),
                "source": "local_ref",
            },
        )

    assert resp.status_code == 422
    body = resp.json()
    detail = body["detail"]
    assert detail["security_status"] == "blocked"
    assert "conversation_id" in detail
    # run must NOT have been created
    repo.create_run.assert_not_called()
    # conversation status must be updated to security_blocked
    repo.update_conversation_status.assert_called_once_with(
        _MOCK_CONV_ID, "security_blocked"
    )


# ── test 2: security passed, no propagation → 200, run created ───────────────

def test_security_passed_no_propagation(client):
    test_client, repo, tmp_path = client
    staging = tmp_path / "conv-test-1234"
    staging.mkdir()

    passed_result = SecurityScanResult(status="passed", findings=[])
    sanitizer_result = _make_sanitizer_result(needs_propagation=False)

    with (
        patch(
            "skillhub_eval.adapters.api.routes.conversations.BundleResolver.from_settings",
            return_value=_make_resolver(staging),
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.ingest_bundle",
            return_value=_VALID_BUNDLE,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.security_scan",
            return_value=passed_result,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CaseSanitizer",
            return_value=MagicMock(run=MagicMock(return_value=sanitizer_result)),
        ),
    ):
        resp = test_client.post(
            "/conversations/start",
            json={
                "skill_id": "skill-x",
                "skill_bundle_path": str(tmp_path / "bundle"),
                "source": "local_ref",
            },
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["conversation_id"] == _MOCK_CONV_ID
    assert body["run_id"] == _MOCK_RUN_ID
    assert body["security_status"] == "passed"
    assert body["propagator_used"] is False
    repo.create_run.assert_called_once()


# ── test 3: security warning → 200, run created, security_status="warning" ───

def test_security_warning_still_creates_run(client):
    test_client, repo, tmp_path = client
    staging = tmp_path / "conv-test-1234"
    staging.mkdir()

    warn_result = SecurityScanResult(status="warning", findings=[])
    sanitizer_result = _make_sanitizer_result(needs_propagation=False)

    with (
        patch(
            "skillhub_eval.adapters.api.routes.conversations.BundleResolver.from_settings",
            return_value=_make_resolver(staging),
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.ingest_bundle",
            return_value=_VALID_BUNDLE,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.security_scan",
            return_value=warn_result,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CaseSanitizer",
            return_value=MagicMock(run=MagicMock(return_value=sanitizer_result)),
        ),
    ):
        resp = test_client.post(
            "/conversations/start",
            json={
                "skill_id": "skill-x",
                "skill_bundle_path": str(tmp_path / "bundle"),
                "source": "local_ref",
            },
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["security_status"] == "warning"
    assert body["run_id"] == _MOCK_RUN_ID
    repo.create_run.assert_called_once()
    # conversation must NOT be blocked (active on run start is OK)
    for call in repo.update_conversation_status.call_args_list:
        assert call[0][1] != "security_blocked"


# ── test 4: needs_propagation → deferred (W5.2), propagator NOT called on /start ─

def test_needs_propagation_defers_bootstrap(client):
    test_client, repo, tmp_path = client
    staging = tmp_path / "conv-test-1234"
    staging.mkdir()

    passed_result = SecurityScanResult(status="passed", findings=[])
    sanitizer_result = _make_sanitizer_result(needs_propagation=True)
    prop_result = _make_prop_result(used_fallback=False)

    mock_propagator = MagicMock()
    mock_propagator.propagate = AsyncMock(return_value=prop_result)

    with (
        patch(
            "skillhub_eval.adapters.api.routes.conversations.BundleResolver.from_settings",
            return_value=_make_resolver(staging),
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.ingest_bundle",
            return_value=_VALID_BUNDLE,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.security_scan",
            return_value=passed_result,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CaseSanitizer",
            return_value=MagicMock(run=MagicMock(return_value=sanitizer_result)),
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CasePropagator",
            return_value=mock_propagator,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.Taxonomy",
            return_value=MagicMock(),
        ),
    ):
        resp = test_client.post(
            "/conversations/start",
            json={
                "skill_id": "skill-x",
                "skill_bundle_path": str(tmp_path / "bundle"),
                "source": "local_ref",
            },
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["run_id"] is None
    assert body["propagation_deferred"] is True
    assert body["propagator_used"] is False
    mock_propagator.propagate.assert_not_called()
    repo.create_run.assert_not_called()


# ── test 5: needs_propagation defer — propagator not invoked on /start (W5.2) ──

def test_needs_propagation_no_immediate_propagator(client):
    test_client, repo, tmp_path = client
    staging = tmp_path / "conv-test-1234"
    staging.mkdir()

    passed_result = SecurityScanResult(status="passed", findings=[])
    sanitizer_result = _make_sanitizer_result(needs_propagation=True)
    prop_result = _make_prop_result(used_fallback=True)

    mock_propagator = MagicMock()
    mock_propagator.propagate = AsyncMock(return_value=prop_result)

    with (
        patch(
            "skillhub_eval.adapters.api.routes.conversations.BundleResolver.from_settings",
            return_value=_make_resolver(staging),
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.ingest_bundle",
            return_value=_VALID_BUNDLE,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.security_scan",
            return_value=passed_result,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CaseSanitizer",
            return_value=MagicMock(run=MagicMock(return_value=sanitizer_result)),
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CasePropagator",
            return_value=mock_propagator,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.Taxonomy",
            return_value=MagicMock(),
        ),
    ):
        resp = test_client.post(
            "/conversations/start",
            json={
                "skill_id": "skill-x",
                "skill_bundle_path": str(tmp_path / "bundle"),
                "source": "local_ref",
            },
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["propagation_deferred"] is True
    assert body["propagator_used"] is False
    mock_propagator.propagate.assert_not_called()


# ── test 7: needs_propagation defers — no run until user confirms (W5.2) ─────

def test_needs_propagation_no_run_on_start(client):
    test_client, repo, tmp_path = client
    staging = tmp_path / "conv-test-1234"
    staging.mkdir()

    passed_result = SecurityScanResult(status="passed", findings=[])
    blocked_result = SecurityScanResult(status="blocked", findings=[])
    sanitizer_result = _make_sanitizer_result(needs_propagation=True)
    prop_result = _make_prop_result(used_fallback=False)

    mock_propagator = MagicMock()
    mock_propagator.propagate = AsyncMock(return_value=prop_result)

    with (
        patch(
            "skillhub_eval.adapters.api.routes.conversations.BundleResolver.from_settings",
            return_value=_make_resolver(staging),
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.ingest_bundle",
            return_value=_VALID_BUNDLE,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.security_scan",
            return_value=passed_result,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CaseSanitizer",
            return_value=MagicMock(run=MagicMock(return_value=sanitizer_result)),
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CasePropagator",
            return_value=mock_propagator,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.Taxonomy",
            return_value=MagicMock(),
        ),
    ):
        resp = test_client.post(
            "/conversations/start",
            json={
                "skill_id": "skill-x",
                "skill_bundle_path": str(tmp_path / "bundle"),
                "source": "local_ref",
            },
        )

    assert resp.status_code == 202
    assert resp.json()["propagation_deferred"] is True
    assert resp.json()["run_id"] is None
    repo.create_run.assert_not_called()
    mock_propagator.propagate.assert_not_called()


# ── test 6: local_ref source creates staging from source path ─────────────────

def test_local_ref_creates_staging(tmp_path):
    """Verify BundleResolver.from_settings is called with correct local_ref args."""
    app = create_app()
    repo = _make_repo()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: MagicMock()
    app.dependency_overrides[get_gemini_provider] = lambda: MagicMock()

    staging = tmp_path / _MOCK_CONV_ID
    staging.mkdir()

    passed_result = SecurityScanResult(status="passed", findings=[])
    sanitizer_result = _make_sanitizer_result(needs_propagation=False)

    bundle_path = str(tmp_path / "my_bundle")

    with (
        patch(
            "skillhub_eval.adapters.api.routes.conversations.BundleResolver.from_settings",
        ) as mock_from_settings,
        patch(
            "skillhub_eval.adapters.api.routes.conversations.ingest_bundle",
            return_value=_VALID_BUNDLE,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.security_scan",
            return_value=passed_result,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CaseSanitizer",
            return_value=MagicMock(run=MagicMock(return_value=sanitizer_result)),
        ),
        patch("skillhub_eval.adapters.api.routes.conversations.EvaluationEngine") as mock_engine_cls,
    ):
        mock_engine_cls.return_value.run_async = AsyncMock()
        mock_from_settings.return_value = _make_resolver(staging)

        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post(
                "/conversations/start",
                json={
                    "skill_id": "skill-x",
                    "skill_bundle_path": bundle_path,
                    "source": "local_ref",
                },
            )

    assert resp.status_code == 202
    mock_from_settings.assert_called_once_with(
        conversation_id=_MOCK_CONV_ID,
        source="local_ref",
        source_path=bundle_path,
    )
