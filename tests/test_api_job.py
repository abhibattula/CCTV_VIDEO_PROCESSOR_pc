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


# ── T005: bulk toggle endpoint tests (TDD — written before T006 implementation) ──

def _seed_events(client, n=3):
    """Seed session with n completed events via session module directly."""
    import app.session as session
    session.reset()
    session.update(status="completed", job_id="test-job", source_path="/fake/video.mp4")
    for i in range(n):
        session.append_event({
            "start_s": float(i),
            "end_s": float(i + 1),
            "peak_motion_score": 0.5 + i * 0.1,
            "zone_label": "Person" if i % 2 == 0 else "Car",
            "included": True,
        })


def test_bulk_toggle_success(client):
    _seed_events(client, 3)
    resp = client.put("/api/job/events/bulk", json={"indices": [0, 1, 2], "include": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == 3
    assert all(ev["included"] is False for ev in data["events"])


def test_bulk_toggle_empty_indices(client):
    _seed_events(client, 2)
    resp = client.put("/api/job/events/bulk", json={"indices": [], "include": True})
    assert resp.status_code == 400
    assert "non-empty" in resp.json()["detail"].lower()


def test_bulk_toggle_invalid_index(client):
    _seed_events(client, 2)
    resp = client.put("/api/job/events/bulk", json={"indices": [0, 99], "include": True})
    assert resp.status_code == 404
    assert "99" in resp.json()["detail"]


# ── T031a: test_export_with_label_filter (TDD — written before T031 implementation) ──

def test_export_with_label_filter(client, monkeypatch, tmp_path):
    """Export API must pass label_filter through to export_engine.run()."""
    _seed_events(client, 2)

    captured = {}

    def fake_run(events, source_info, settings, output_dir, on_progress, job_dir, logger=None,
                 burn_in=False, label_filter=None):
        captured["label_filter"] = label_filter
        from pathlib import Path
        p = Path(output_dir) / "test_out.mp4"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x00")
        return p, "test_out.mp4", 1

    monkeypatch.setattr("app.core.export_engine.run", fake_run)

    resp = client.post("/api/job/export", json={
        "output_type": "merged",
        "quality": "original",
        "output_dir": str(tmp_path),
        "label_filter": ["Person"],
    })
    assert resp.status_code == 200

    import time
    for _ in range(30):
        if "label_filter" in captured:
            break
        time.sleep(0.1)

    assert captured.get("label_filter") == ["Person"]
