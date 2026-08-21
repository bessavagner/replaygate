from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from replaygate.api.app import create_app

HTML = {"Accept": "text/html,application/xhtml+xml"}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>ReplayGate</title>")
    return TestClient(create_app(fixtures, frontend_dir=dist))


def test_root_serves_the_spa(client: TestClient):
    response = client.get("/", headers=HTML)
    assert response.status_code == 200
    assert "ReplayGate" in response.text


def test_client_side_route_falls_back_to_index(client: TestClient):
    response = client.get("/runs/support_happy", headers=HTML)
    assert response.status_code == 200
    assert "ReplayGate" in response.text


def test_api_still_answers_json_behind_the_spa_mount(client: TestClient):
    response = client.get("/api/health", headers=HTML)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unknown_api_path_is_not_swallowed_by_the_spa_fallback(client: TestClient):
    response = client.get("/api/typo", headers=HTML)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
