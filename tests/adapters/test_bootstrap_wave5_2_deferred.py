"""Wave 5.2 Task 3 — deferred propagation at bootstrap."""

from __future__ import annotations

import io
import json
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_ds_provider, get_gemini_provider, get_repo
from skillhub_eval.core.case_sanitizer import SanitizerResult
from skillhub_eval.core.security_scan import SecurityScanResult
from skillhub_eval.persistence.sqlite import SqliteRepository

_VALID_BUNDLE = {
    "skill_md_text": "---\nname: from-skill-md\n---\n# Demo Skill\n",
    "skill_meta": {
        "name": "from-skill-md",
        "category": "fin-research/quant-signal",
        "description": "这是一个足够长的 Skill 描述，用于在 complete cases 测试中跳过 L0 purpose 澄清门槛。",
    },
    "risk_level_declared": "low",
    "eval_cases": [{"id": "c1", "type": "happy_path"}],
    "n_cases": 1,
    "skill_id": "from-skill-md",
}


def _make_zip_bytes(
    *,
    skill_md: str,
    eval_case: str | None = None,
    filename: str = "my-bundle.zip",
) -> tuple[bytes, str]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", skill_md)
        if eval_case is not None:
            zf.writestr("eval_cases/case_001.yaml", eval_case)
    return buffer.getvalue(), filename


def _make_sanitizer_result(*, needs_propagation: bool = False) -> SanitizerResult:
    return SanitizerResult(
        broken_moved=0,
        invalid_type_count=0,
        gap_by_type={"happy_path": 0},
        needs_propagation=needs_propagation,
        existing_counts={"happy_path": 1},
    )


def _count_runs(repo: SqliteRepository, conversation_id: str) -> int:
    with repo._conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM evaluation_runs WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
    return int(row[0])


@pytest.fixture()
def client_with_repo(tmp_path):
    db_path = str(tmp_path / "wave5_2_deferred.db")
    repo = SqliteRepository(db_path)
    repo.init_db()

    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_ds_provider] = lambda: MagicMock()
    app.dependency_overrides[get_gemini_provider] = lambda: MagicMock()

    with patch(
        "skillhub_eval.adapters.api.routes.conversations.EvaluationEngine"
    ) as mock_engine_cls:
        mock_engine_cls.return_value.run_async = AsyncMock()
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c, repo


def test_bootstrap_skill_only_zip_defers_propagation(
    client_with_repo, tmp_path, monkeypatch
):
    client, repo = client_with_repo
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    skill_md = (
        "---\n"
        "name: grill-me-skill\n"
        "description: 这是一个用于测试 deferred propagation 的 Skill，描述足够长以满足 L0 门槛。\n"
        "risk_level: low\n"
        "category: document.docx\n"
        "---\n"
        "# Grill Me Skill\n\n"
        "本 Skill 用于验证 bootstrap 在缺题时会暂停并展示补题计划。\n"
    )
    payload, filename = _make_zip_bytes(skill_md=skill_md)

    new_resp = client.post("/conversations/new")
    conv_id = new_resp.json()["conversation_id"]

    with patch(
        "skillhub_eval.adapters.api.routes.conversations.CasePropagator.propagate",
        new_callable=AsyncMock,
    ) as mock_propagate:
        resp = client.post(
            f"/conversations/{conv_id}/bootstrap",
            data={"skill_id": "grill-me-skill", "source": "upload"},
            files={"bundle_zip": (filename, payload, "application/zip")},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["run_id"] is None
    assert body["propagation_deferred"] is True
    assert body["propagator_used"] is False
    assert body["status"] in (
        "awaiting_propagation_confirm",
        "awaiting_propagation_clarify",
    )
    mock_propagate.assert_not_called()
    assert _count_runs(repo, conv_id) == 0

    messages = repo.get_lui_messages(conv_id)
    plan_messages = [m for m in messages if m["message_type"] == "propagation_plan"]
    assert len(plan_messages) == 1
    payload_json = plan_messages[0]["payload_json"]
    if isinstance(payload_json, str):
        payload_json = json.loads(payload_json)
    assert payload_json["gap_by_type"]["happy_path"] >= 1
    assert "rows" in payload_json

    conv = repo.get_conversation(conv_id)
    assert conv["status"] == body["status"]


def test_bootstrap_skill_only_missing_category_defers_to_clarify(
    client_with_repo, tmp_path, monkeypatch
):
    client, repo = client_with_repo
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))

    skill_md = (
        "---\n"
        "name: no-category-skill\n"
        "description: 这是一个用于测试 L0 category 澄清触发的 Skill，描述足够长以满足 L0 门槛。\n"
        "risk_level: low\n"
        "---\n"
        "# No Category\n\n"
        "缺少 category 时应进入 awaiting_propagation_clarify。\n"
    )
    payload, filename = _make_zip_bytes(skill_md=skill_md)

    new_resp = client.post("/conversations/new")
    conv_id = new_resp.json()["conversation_id"]

    with patch(
        "skillhub_eval.adapters.api.routes.conversations.CasePropagator.propagate",
        new_callable=AsyncMock,
    ) as mock_propagate:
        resp = client.post(
            f"/conversations/{conv_id}/bootstrap",
            data={"skill_id": "no-category-skill", "source": "upload"},
            files={"bundle_zip": (filename, payload, "application/zip")},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["propagation_deferred"] is True
    assert body["status"] == "awaiting_propagation_clarify"
    mock_propagate.assert_not_called()
    assert _count_runs(repo, conv_id) == 0

    messages = repo.get_lui_messages(conv_id)
    assert any(m["message_type"] == "propagation_plan" for m in messages)


def test_bootstrap_complete_cases_still_creates_run(client_with_repo, tmp_path, monkeypatch):
    client, repo = client_with_repo
    monkeypatch.setattr("skillhub_eval.settings.settings.staging_root", str(tmp_path / "staging"))
    passed = SecurityScanResult(status="passed", findings=[])

    new_resp = client.post("/conversations/new")
    conv_id = new_resp.json()["conversation_id"]
    payload, filename = _make_zip_bytes(
        skill_md="---\nname: from-skill-md\n---\n# Demo Skill\n",
        eval_case="id: case_001\ntype: happy_path\n",
    )

    with (
        patch(
            "skillhub_eval.adapters.api.routes.conversations.ingest_bundle",
            return_value=_VALID_BUNDLE,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.security_scan",
            return_value=passed,
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CaseSanitizer",
            return_value=MagicMock(run=MagicMock(return_value=_make_sanitizer_result())),
        ),
        patch(
            "skillhub_eval.adapters.api.routes.conversations.CasePropagator.propagate",
            new_callable=AsyncMock,
        ) as mock_propagate,
    ):
        resp = client.post(
            f"/conversations/{conv_id}/bootstrap",
            data={"skill_id": "explicit-skill", "source": "upload"},
            files={"bundle_zip": (filename, payload, "application/zip")},
        )

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["run_id"]
    assert body["propagation_deferred"] is False
    assert body["propagator_used"] is False
    mock_propagate.assert_not_called()
    assert _count_runs(repo, conv_id) == 1

    messages = repo.get_lui_messages(conv_id)
    assert not any(m["message_type"] == "propagation_plan" for m in messages)
