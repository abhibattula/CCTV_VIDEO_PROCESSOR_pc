"""
Tests for the /api/job/* router.
T019 test_health added first (TDD bootstrap).
T034 tests added before T035 implementation.
"""
import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

TEST_VIDEO = str(
    Path(__file__).parent.parent
    / "OLD RASPBERRI PI VERSION"
    / "Test Video"
    / "20260507_012210 (1).mp4"
)
HAS_TEST_VIDEO = os.path.isfile(TEST_VIDEO)


@pytest.fixture
def client():
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_job_missing_file(client):
    resp = client.post("/api/job/create", json={"source_path": "/no/such/file.mp4"})
    assert resp.status_code == 400
    data = resp.json()
    assert "not found" in data.get("detail", "").lower()


def test_get_job_initial_state(client):
    resp = client.get("/api/job")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "idle"


def test_toggle_event_out_of_range(client):
    # No events exist in a fresh session — idx 0 should 404
    resp = client.put("/api/job/events/0/toggle")
    assert resp.status_code == 404


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_create_job_valid_file(client):
    resp = client.post("/api/job/create", json={"source_path": TEST_VIDEO})
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "ready"
