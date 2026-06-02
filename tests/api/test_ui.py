"""
Task 11 — Static UI smoke tests.
Verifies that index.html is served at /ui and contains expected elements.
"""

from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app


def test_ui_index_returns_200():
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_ui_has_tailwind_cdn():
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "tailwindcss.com" in r.text


def test_ui_has_both_tabs():
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "tab-author" in r.text
    assert "tab-expert" in r.text
    assert "tab-history" in r.text


def test_ui_has_key_api_endpoints_referenced():
    """JS code must reference all 5 contract endpoints."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "/eval/run" in r.text
    assert "/eval/report/" in r.text
    assert "/eval/history" in r.text
    assert "/eval/review/" in r.text
    assert "/bundle/" in r.text


def test_ui_has_confirm_and_review_forms():
    """Both interaction forms (gap confirm + expert review) must be present."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "submitConfirm" in r.text
    assert "submitReview" in r.text
    assert "negative_prompts" in r.text      # security-sensitive field
    assert "approve" in r.text
    assert "reject" in r.text
