"""
Tests for the /api/job/* router.
T019 test_health added first (TDD bootstrap).
T034 tests added before T035 implementation.
"""
import hashlib
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


# ── T001: preview-frame endpoint tests (TDD — written before T002 implementation) ──

def test_preview_frame_no_active_job_returns_400(client):
    resp = client.get("/api/job/preview-frame")
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_preview_frame_extraction_failure_returns_500(client, monkeypatch):
    import app.session as session
    session.reset()
    session.update(
        job_id="test-job",
        source_path="/fake/video.mp4",
        source_info={"duration_s": 10},
    )

    class FakeResult:
        returncode = 1

    monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeResult())

    resp = client.get("/api/job/preview-frame")
    assert resp.status_code == 500
    assert "error" in resp.json()


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_preview_frame_extracts_and_caches(client, monkeypatch):
    resp = client.post("/api/job/create", json={"source_path": TEST_VIDEO})
    assert resp.status_code == 200

    import subprocess as _subprocess
    real_run = _subprocess.run
    call_count = {"n": 0}

    def counting_run(*args, **kwargs):
        call_count["n"] += 1
        return real_run(*args, **kwargs)

    monkeypatch.setattr("subprocess.run", counting_run)

    resp1 = client.get("/api/job/preview-frame")
    assert resp1.status_code == 200
    assert resp1.headers["content-type"] == "image/jpeg"
    assert call_count["n"] == 1

    # Second call must serve the cached file, not re-invoke ffmpeg
    resp2 = client.get("/api/job/preview-frame")
    assert resp2.status_code == 200
    assert call_count["n"] == 1


# ── T013: cancel-guard regression test (TDD — written before T014 implementation) ──

@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_create_job_cancels_inflight_detection_before_reset(client):
    """job/create must cancel any in-flight detection from a previous job
    before resetting the session, so an orphaned detection thread can't
    write stale events into the freshly-reset session."""
    import app.api.job as job_module
    job_module._cancel_event.clear()
    assert not job_module._cancel_event.is_set()

    resp = client.post("/api/job/create", json={"source_path": TEST_VIDEO})
    assert resp.status_code == 200
    assert job_module._cancel_event.is_set()


# ── T006: _sha256_file helper tests (TDD — written before T007 implementation) ──

def test_sha256_file_matches_known_hash(tmp_path):
    """_sha256_file() must match an independently-computed hash of known
    content, proving it reads the file correctly."""
    from app.api.job import _sha256_file

    known_bytes = b"the quick brown fox jumps over the lazy dog"
    file_path = tmp_path / "known.txt"
    file_path.write_bytes(known_bytes)

    expected = hashlib.sha256(known_bytes).hexdigest()
    assert _sha256_file(file_path) == expected


def test_sha256_file_chunked_equals_whole_file_hash(tmp_path):
    """_sha256_file() must read in chunks without changing the result.
    Uses a file larger than the default 1 MiB chunk size to actually
    exercise multi-chunk reading."""
    from app.api.job import _sha256_file

    random_bytes = os.urandom(3 * 1024 * 1024)  # 3 MiB, > default 1 MiB chunk
    file_path = tmp_path / "large.bin"
    file_path.write_bytes(random_bytes)

    expected = hashlib.sha256(file_path.read_bytes()).hexdigest()
    assert _sha256_file(file_path) == expected
