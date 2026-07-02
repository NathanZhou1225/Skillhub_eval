"""Conversation archive — DELETE /conversations/{id} (sidebar soft-delete)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.adapters.api.deps import get_repo
from skillhub_eval.persistence.sqlite import SqliteRepository


@pytest.fixture()
def client_with_repo(tmp_path):
    db_path = str(tmp_path / "archive.db")
    repo = SqliteRepository(db_path)
    repo.init_db()
    app = create_app()
    app.dependency_overrides[get_repo] = lambda: repo
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, repo


def _new_conv(repo: SqliteRepository) -> str:
    return repo.create_conversation(skill_id="demo.skill", source="upload")


def test_archive_hides_from_list_and_sets_archived_at(client_with_repo):
    client, repo = client_with_repo
    conv_id = _new_conv(repo)

    resp = client.delete(f"/conversations/{conv_id}")
    assert resp.status_code == 204

    conv = repo.get_conversation(conv_id)
    assert conv["status"] == "archived"
    assert conv["archived_at"]

    listed = client.get("/conversations").json()["conversations"]
    assert all(c["conversation_id"] != conv_id for c in listed)

    messages = repo.get_lui_messages(conv_id)
    assert messages == [] or isinstance(messages, list)


def test_archive_not_found(client_with_repo):
    client, _ = client_with_repo
    resp = client.delete("/conversations/does-not-exist")
    assert resp.status_code == 404


def test_archive_idempotent_not_found(client_with_repo):
    client, repo = client_with_repo
    conv_id = _new_conv(repo)
    assert client.delete(f"/conversations/{conv_id}").status_code == 204
    assert client.delete(f"/conversations/{conv_id}").status_code == 404


def test_archive_blocked_while_run_in_progress(client_with_repo):
    client, repo = client_with_repo
    conv_id = _new_conv(repo)
    run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path="/tmp/bundle",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, "model_judging")

    resp = client.delete(f"/conversations/{conv_id}")
    assert resp.status_code == 409
    assert repo.get_conversation(conv_id)["status"] != "archived"


def test_archive_allowed_when_run_stale_in_running_status(client_with_repo):
    client, repo = client_with_repo
    conv_id = _new_conv(repo)
    run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path="/tmp/bundle",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, "case_executing")
    with repo._conn() as conn:
        conn.execute(
            "UPDATE evaluation_runs SET started_at = ? WHERE run_id = ?",
            ("2020-01-01T00:00:00+00:00", run_id),
        )
        conn.commit()

    resp = client.delete(f"/conversations/{conv_id}")
    assert resp.status_code == 204
    assert repo.get_conversation(conv_id)["status"] == "archived"
    assert repo.get_run(run_id)["status"] == "failed"


def test_archive_frozen_blocked_for_author_allowed_for_expert(client_with_repo):
    client, repo = client_with_repo
    conv_id = _new_conv(repo)
    repo.update_conversation_status(conv_id, "frozen")

    resp_author = client.delete(f"/conversations/{conv_id}?perspective=author")
    assert resp_author.status_code == 403

    resp_expert = client.delete(f"/conversations/{conv_id}?perspective=expert")
    assert resp_expert.status_code == 204
    assert repo.get_conversation(conv_id)["status"] == "archived"


def test_archive_human_review_blocked_for_author(client_with_repo):
    client, repo = client_with_repo
    conv_id = _new_conv(repo)
    run_id = repo.create_run(
        skill_id="demo.skill",
        skill_bundle_path="/tmp/bundle",
        bundle_state="confirmed",
        evaluation_mode="capability_full",
        conversation_id=conv_id,
    )
    repo.update_status(run_id, "awaiting_human_review")
    repo.set_human_review_required(run_id, True, ["MODEL_DISAGREEMENT_R5"])

    resp_author = client.delete(f"/conversations/{conv_id}?perspective=author")
    assert resp_author.status_code == 403

    resp_expert = client.delete(f"/conversations/{conv_id}?perspective=expert")
    assert resp_expert.status_code == 204
