"""Web service tests: landing page, health, sample, review API."""

import json
from pathlib import Path

import pytest

from apps.web.app import create_app

SAMPLE = json.loads(
    Path("apps/acquisition_review/sample_evidence.json").read_text()
)


@pytest.fixture()
def client():
    return create_app().test_client()


def test_landing_page(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Institutional Intelligence Infrastructure" in html
    assert "READY FOR HUMAN AUTHORITY" in html
    assert "/api/review" in html


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_sample_shape(client):
    data = client.get("/api/sample").get_json()
    assert set(data) == {"target", "terms", "evidence", "risks", "scenarios"}
    assert len(data["evidence"]) > 0


def test_review_full_pipeline(client):
    r = client.post("/api/review", json={"intake": SAMPLE, "with_reframing": False})
    assert r.status_code == 200
    d = r.get_json()
    assert d["gate_state"] == "ready_for_human_authority"
    assert d["readiness"] == "ready_for_human_authority"
    assert isinstance(d["recommendation"], str)
    assert 0.0 <= d["combined_confidence"] <= 1.0
    assert len(d["perspectives"]) == 4
    assert "# Minority Report" in d["minority_report_markdown"]
    assert "AWAITING HUMAN AUTHORIZATION" in d["dossier_markdown"]
    assert isinstance(d["sensitivity"], list) and d["sensitivity"]


def test_review_rejects_bad_intake(client):
    r = client.post("/api/review", json={})
    assert r.status_code == 400
    r = client.post("/api/review", json={"intake": {"target": "x"}})
    assert r.status_code == 400
    assert "at least one evidence item" in r.get_json()["error"]
    r = client.post("/api/review", json={"intake": "not-an-object"})
    assert r.status_code == 400


def test_review_rejects_non_json(client):
    r = client.post("/api/review", data="hello", content_type="text/plain")
    assert r.status_code == 400
