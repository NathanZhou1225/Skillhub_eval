from __future__ import annotations

import io
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.case_sanitizer import SanitizerResult
from skillhub_eval.core.bundle_security import BundleSecurityScanResult

_MOCK_CONV_ID = "conv-upload-123"
_MOCK_RUN_ID = "run-upload-456"

_VALID_BUNDLE = {
    "skill_md_text": "# Uploaded Skill\n" + ("content\n" * 50),
    "skill_meta": {
        "name": "skill-upload",
        "category": "fin-research/quant-signal",
        "description": "这是一个足够长的 Skill 描述，用于在 complete cases 测试中跳过 L0 purpose 澄清门槛。",
    },
    "risk_level_declared": "low",
    "eval_cases": [{"id": "c1", "type": "happy_path"}],
    "n_cases": 1,
}


def _make_repo() -> MagicMock:
    repo = MagicMock()
    repo.create_conversation.return_value = _MOCK_CONV_ID
    repo.create_run.return_value = _MOCK_RUN_ID
    repo.get_conversation.return_value = {
        "status": "active",
        "auto_run_count": 0,
        "max_auto_runs": 5,
    }
    repo.get_lui_messages.return_value = []
    return repo


def _make_zip_bytes(include_skill_md: bool = True, nested_folder: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        prefix = f"{nested_folder}/" if nested_folder else ""
        if include_skill_md:
            zf.writestr(f"{prefix}SKILL.md", "# Demo Skill\n")
        zf.writestr(f"{prefix}eval_cases/case_001.yaml", "id: case_001\ntype: happy_path\n")
    return buffer.getvalue()


def _make_sanitizer_result() -> SanitizerResult:
    return SanitizerResult(
        broken_moved=0,
        invalid_type_count=0,
        gap_by_type={"happy_path": 0},
        needs_propagation=False,
        existing_counts={"happy_path": 1},
    )


@pytest.fixture()
def client():
    app = create_app()
    repo = _make_repo()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: MagicMock()
    app.dependency_overrides[get_gemini_provider] = lambda: MagicMock()
    with patch("skillhub_eval.adapters.api.routes.conversations.EvaluationEngine") as mock_engine_cls:
        mock_engine_cls.return_value.run_async = AsyncMock()
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c, repo


def test_upload_zip_creates_originals_and_staging(client, tmp_path, monkeypatch):
    test_client, repo = client
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    passed_result = BundleSecurityScanResult(intake_status="passed")
    sanitizer_result = _make_sanitizer_result()
    payload = _make_zip_bytes(include_skill_md=True)

    with (
        patch("skillhub_eval.adapters.api.routes.conversations.ingest_bundle", return_value=_VALID_BUNDLE),
        patch("skillhub_eval.adapters.api.routes.conversations.scan_bundle_security", return_value=passed_result),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CaseSanitizer",
            return_value=MagicMock(run=MagicMock(return_value=sanitizer_result)),
        ),
        patch("skillhub_eval.adapters.api.routes.conversations._set_conversation_source_path") as mock_set_source,
    ):
        resp = test_client.post(
            "/conversations/start",
            data={"skill_id": "skill-upload", "source": "upload"},
            files={"bundle_zip": ("bundle.zip", payload, "application/zip")},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["conversation_id"] == _MOCK_CONV_ID
    assert body["run_id"] == _MOCK_RUN_ID

    originals = tmp_path / "originals" / _MOCK_CONV_ID
    staging = tmp_path / "staging" / _MOCK_CONV_ID
    assert (originals / "SKILL.md").exists()
    assert (staging / "SKILL.md").exists()

    repo.create_conversation.assert_called_once_with(
        skill_id="skill-upload",
        source="upload",
        source_path="",
    )
    mock_set_source.assert_called_once_with(repo, _MOCK_CONV_ID, originals)


def test_upload_invalid_zip_returns_422_and_cleans_originals(client, tmp_path, monkeypatch):
    test_client, repo = client
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    resp = test_client.post(
        "/conversations/start",
        data={"skill_id": "skill-upload", "source": "upload"},
        files={"bundle_zip": ("bundle.zip", b"not-a-zip", "application/zip")},
    )

    assert resp.status_code == 422
    assert "zip" in str(resp.json()["detail"]).lower()
    assert not (tmp_path / "originals" / _MOCK_CONV_ID).exists()
    repo.create_run.assert_not_called()


def test_upload_zip_without_skill_md_returns_422_and_cleans_originals(client, tmp_path, monkeypatch):
    test_client, repo = client
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    payload = _make_zip_bytes(include_skill_md=False)
    resp = test_client.post(
        "/conversations/start",
        data={"skill_id": "skill-upload", "source": "upload"},
        files={"bundle_zip": ("bundle.zip", payload, "application/zip")},
    )

    assert resp.status_code == 422
    assert "skill.md" in str(resp.json()["detail"]).lower()
    assert not (tmp_path / "originals" / _MOCK_CONV_ID).exists()
    assert not (tmp_path / "staging" / _MOCK_CONV_ID).exists()
    repo.create_run.assert_not_called()


def test_upload_zip_with_single_wrapper_folder_hoists_skill_md(client, tmp_path, monkeypatch):
    """Windows 'compress folder' zips put SKILL.md one level down — should still work."""
    test_client, repo = client
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    passed_result = BundleSecurityScanResult(intake_status="passed")
    sanitizer_result = _make_sanitizer_result()
    payload = _make_zip_bytes(include_skill_md=True, nested_folder="grill-me")

    with (
        patch("skillhub_eval.adapters.api.routes.conversations.ingest_bundle", return_value=_VALID_BUNDLE),
        patch("skillhub_eval.adapters.api.routes.conversations.scan_bundle_security", return_value=passed_result),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CaseSanitizer",
            return_value=MagicMock(run=MagicMock(return_value=sanitizer_result)),
        ),
    ):
        resp = test_client.post(
            "/conversations/start",
            data={"skill_id": "skill-upload", "source": "upload"},
            files={"bundle_zip": ("grill-me.zip", payload, "application/zip")},
        )

    assert resp.status_code == 202
    originals = tmp_path / "originals" / _MOCK_CONV_ID
    assert (originals / "SKILL.md").exists()
    assert not (originals / "grill-me").exists()


def test_local_ref_json_still_works_and_sets_source_path(client, tmp_path):
    test_client, repo = client
    bundle_path = str(tmp_path / "bundle")
    staging = tmp_path / _MOCK_CONV_ID
    staging.mkdir()

    passed_result = BundleSecurityScanResult(intake_status="passed")
    sanitizer_result = _make_sanitizer_result()

    resolver = MagicMock()
    resolver.ref.staging_path = Path(staging)
    resolver.ensure_staging.return_value = None

    with (
        patch(
            "skillhub_eval.adapters.api.routes.conversations.BundleResolver.from_settings",
            return_value=resolver,
        ),
        patch("skillhub_eval.adapters.api.routes.conversations.ingest_bundle", return_value=_VALID_BUNDLE),
        patch("skillhub_eval.adapters.api.routes.conversations.scan_bundle_security", return_value=passed_result),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CaseSanitizer",
            return_value=MagicMock(run=MagicMock(return_value=sanitizer_result)),
        ),
    ):
        resp = test_client.post(
            "/conversations/start",
            json={
                "skill_id": "skill-local",
                "skill_bundle_path": bundle_path,
                "source": "local_ref",
            },
        )

    assert resp.status_code == 202
    repo.create_conversation.assert_called_once_with(
        skill_id="skill-local",
        source="local_ref",
        source_path=bundle_path,
    )
