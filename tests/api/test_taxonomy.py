"""Task 4 — GET /taxonomy/categories API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_get_taxonomy_categories(client: TestClient) -> None:
    response = client.get("/taxonomy/categories")
    assert response.status_code == 200


def test_get_taxonomy_categories_structure(client: TestClient) -> None:
    data = client.get("/taxonomy/categories").json()
    assert "version" in data
    assert "categories" in data
    assert isinstance(data["categories"], list)
    assert len(data["categories"]) > 0

    level1 = data["categories"][0]
    assert "slug" in level1
    assert "name_zh" in level1
    assert "children" in level1
    assert isinstance(level1["children"], list)
    assert len(level1["children"]) > 0

    child = level1["children"][0]
    assert "slug" in child
    assert "full_slug" in child
    assert "name_zh" in child


def test_get_taxonomy_categories_contains_leaf_slug(client: TestClient) -> None:
    data = client.get("/taxonomy/categories").json()
    full_slugs = [
        child["full_slug"]
        for level1 in data["categories"]
        for child in level1["children"]
    ]
    assert "fin-research/quant-signal" in full_slugs
