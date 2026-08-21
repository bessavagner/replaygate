from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from replaygate.api.app import create_app
from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.record import record_conversation
from replaygate.examples.scenarios import EXAMPLES, scripted_llm_for
from replaygate.store.fixtures import write_fixture

TS = datetime(2026, 6, 29, tzinfo=timezone.utc)
HTML = {"Accept": "text/html,application/xhtml+xml"}


def _record(scenario_name: str, out_dir: Path) -> None:
    spec = EXAMPLES[scenario_name]
    fixture = record_conversation(
        agent_factory=spec.build_agent,
        inner_llm=scripted_llm_for(scenario_name),
        scenario=spec.scenario,
        adapter=DirectAdapter(),
        tools=spec.tools(),
        agent_version="test",
        model=spec.model,
        recorded_at=TS,
    )
    write_fixture(str(out_dir), fixture)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    _record("support_happy", tmp_path / "support_happy")
    return TestClient(create_app(tmp_path))


def test_health_reports_the_run_count(client: TestClient):
    body = client.get("/api/health").json()
    assert body == {"status": "ok", "runs": 1}


def test_runs_lists_fixtures(client: TestClient):
    body = client.get("/api/runs").json()
    assert [r["run_id"] for r in body["runs"]] == ["support_happy"]
    assert body["runs"][0]["turn_count"] == 2


def test_run_detail_serializes_computed_fields(client: TestClient):
    body = client.get("/api/runs/support_happy").json()
    assert body["status"] == "ok"
    assert body["changed_turn_indexes"] == []
    assert body["turns"][0]["changed"] is False


def test_regressed_candidate_is_reported_over_the_api(client: TestClient):
    body = client.get("/api/runs/support_happy?candidate=support_regressed").json()
    assert body["status"] == "failed"
    assert body["changed_turn_indexes"] == [1]
    assert body["invariants"][0]["detail"] == (
        "turn 1: re-asked for an order id already given on turn 0"
    )


def test_unknown_run_is_a_json_404(client: TestClient):
    response = client.get("/api/runs/nope")
    assert response.status_code == 404
    assert response.json()["detail"] == "no such run: nope"


def test_unknown_candidate_is_a_json_404(client: TestClient):
    response = client.get("/api/runs/support_happy?candidate=nope")
    assert response.status_code == 404
    assert response.json()["detail"] == "no such candidate: nope"


def test_unknown_api_path_stays_json_even_for_html_clients(client: TestClient):
    response = client.get("/api/typo", headers=HTML)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"] == "no such endpoint: /api/typo"


def test_the_api_never_offers_a_write_method(client: TestClient):
    for method in ("post", "put", "patch", "delete"):
        response = getattr(client, method)("/api/runs/support_happy")
        assert response.status_code == 405, method
