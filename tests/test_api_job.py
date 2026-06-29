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
            "event_index": i,
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


# ── Phase 9 TDD tests (B6: _get_desktop_path; B2: poll caching) ─────────────

def test_get_desktop_path_returns_nonempty_string():
    """_get_desktop_path() MUST return a non-empty string.
    Written before implementation — MUST FAIL with ImportError until B6 implemented."""
    from app.api.job import _get_desktop_path
    result = _get_desktop_path()
    assert isinstance(result, str), f"Expected str, got {type(result)}"
    assert len(result) > 0, "_get_desktop_path() returned empty string"


def test_get_job_does_not_recall_is_available_after_cache(client, monkeypatch):
    """GET /api/job must not re-run the filesystem check on the second poll.
    Written before implementation — MUST FAIL until T022 cache + T023 removal done."""
    from app.core.frame_analyzer import FrameAnalyzer

    # Reset the cache so the first call actually runs
    FrameAnalyzer._availability_cache = None

    call_count = [0]
    real_is_available = FrameAnalyzer.__dict__.get("is_available")

    original = FrameAnalyzer.is_available.__func__ if hasattr(FrameAnalyzer.is_available, "__func__") else None

    from pathlib import Path
    original_exists = Path.exists

    def counting_exists(self):
        if "Florence" in str(self) or "huggingface" in str(self):
            call_count[0] += 1
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", counting_exists)
    FrameAnalyzer._availability_cache = None

    # First poll
    client.get("/api/job")
    first_count = call_count[0]

    # Second poll — cache should prevent re-checking
    client.get("/api/job")
    second_count = call_count[0]

    assert second_count == first_count, (
        f"Filesystem stat called {second_count - first_count} extra time(s) on second poll — "
        "implement _availability_cache in FrameAnalyzer.is_available()"
    )


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


# ── T008: /api/job/report.html tests (TDD — written before T009/T010 implementation) ──

def test_report_html_no_active_job(client):
    resp = client.get("/api/job/report.html")
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_report_html_no_included_events(client):
    _seed_events(client, 3)
    import app.session as session
    snap = session.snapshot()
    for ev in snap["events"]:
        ev["included"] = False
    session.update(events=snap["events"])

    resp = client.get("/api/job/report.html")
    assert resp.status_code == 400
    data = resp.json()
    assert "error" in data
    assert "nothing to report" in data["error"].lower() or "no events" in data["error"].lower()


def test_report_html_renders_expected_content(client, monkeypatch):
    monkeypatch.setattr("app.core.thumbnail_gen.run", lambda *a, **k: None)
    _seed_events(client, 3)
    import app.session as session
    session.update(source_path="/fake/video.mp4")

    resp = client.get("/api/job/report.html")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    body = resp.text
    assert "video.mp4" in body
    assert "3 of 3" in body
    assert ("Person" in body) or ("Car" in body)


def test_report_html_includes_source_hash(client, monkeypatch, tmp_path):
    monkeypatch.setattr("app.core.thumbnail_gen.run", lambda *a, **k: None)
    known_bytes = b"incident report source hash fixture content"
    source_file = tmp_path / "evidence.mp4"
    source_file.write_bytes(known_bytes)

    _seed_events(client, 2)
    import app.session as session
    session.update(source_path=str(source_file))

    expected_hash = hashlib.sha256(known_bytes).hexdigest()

    resp = client.get("/api/job/report.html")
    assert resp.status_code == 200
    assert expected_hash in resp.text


def test_report_html_no_output_yet(client, monkeypatch):
    monkeypatch.setattr("app.core.thumbnail_gen.run", lambda *a, **k: None)
    _seed_events(client, 2)
    import app.session as session
    session.update(source_path="/fake/video.mp4")  # output_path left at default (None)

    resp = client.get("/api/job/report.html")
    assert resp.status_code == 200
    body_lower = resp.text.lower()
    assert ("no export" in body_lower) or ("not yet" in body_lower)


def test_report_html_shows_filenames_not_paths(client, monkeypatch, tmp_path):
    monkeypatch.setattr("app.core.thumbnail_gen.run", lambda *a, **k: None)
    distinctive_dir = tmp_path / "some_distinctive_dir_12345"
    distinctive_dir.mkdir()
    source_file = distinctive_dir / "video.mp4"
    source_file.write_bytes(b"placeholder video bytes")

    _seed_events(client, 2)
    import app.session as session
    session.update(source_path=str(source_file))

    resp = client.get("/api/job/report.html")
    assert resp.status_code == 200
    body = resp.text
    assert "video.mp4" in body
    assert "some_distinctive_dir_12345" not in body


# ── T016: /api/job/heatmap tests (TDD — written before T019 implementation) ──

def test_heatmap_no_active_job(client):
    resp = client.get("/api/job/heatmap")
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_heatmap_not_yet_generated(client):
    import app.session as session
    session.reset()
    session.update(job_id="test-job", source_path="/fake/video.mp4")

    resp = client.get("/api/job/heatmap")
    assert resp.status_code == 404
    assert "error" in resp.json()


def test_heatmap_served_when_present(client, monkeypatch, tmp_path):
    import cv2
    import numpy as np
    import app.session as session
    from app.api.job import _job_dir

    # Redirect _job_dir's base directory to tmp_path so this test never
    # writes into the real ~/.cctv_processor/jobs (matches the pattern
    # already established in tests/test_thumbnail_gen.py) — avoids leaking
    # a real heatmap.png across pytest invocations and corrupting
    # test_heatmap_not_yet_generated's hardcoded "test-job" job_id.
    monkeypatch.setattr("app.api.job.JOBS_DIR", tmp_path)

    job_id = "test-job"
    session.reset()
    session.update(job_id=job_id, source_path="/fake/video.mp4")

    heatmap_path = _job_dir(job_id) / "heatmap.png"
    blank = np.zeros((10, 10, 3), dtype=np.uint8)
    assert cv2.imwrite(str(heatmap_path), blank)

    resp = client.get("/api/job/heatmap")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")


# ── T023: CSV/JSON event log export endpoint tests (TDD — written before T024 implementation) ──

def test_export_csv_writes_expected_rows(client, tmp_path):
    _seed_events(client, 3)

    resp = client.post("/api/job/export/csv", json={"output_dir": str(tmp_path)})
    assert resp.status_code == 200
    data = resp.json()
    assert "output_path" in data

    out_path = Path(data["output_path"])
    assert out_path.exists()

    import csv
    with open(out_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 3
    for i, row in enumerate(rows):
        assert int(row["event_index"]) == i
        assert float(row["start_s"]) == float(i)
        assert float(row["end_s"]) == float(i + 1)
        assert row["zone_label"] == ("Person" if i % 2 == 0 else "Car")


def test_export_csv_respects_label_filter(client, tmp_path):
    _seed_events(client, 3)  # zone_label alternates Person, Car, Person

    resp = client.post(
        "/api/job/export/csv",
        json={"output_dir": str(tmp_path), "label_filter": ["Person"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    out_path = Path(data["output_path"])
    assert out_path.exists()

    import csv
    with open(out_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
    assert all(row["zone_label"] == "Person" for row in rows)


def test_export_csv_no_included_events(client, tmp_path):
    _seed_events(client, 2)
    import app.session as session
    snap = session.snapshot()
    for ev in snap["events"]:
        ev["included"] = False
    session.update(events=snap["events"])

    resp = client.post("/api/job/export/csv", json={"output_dir": str(tmp_path)})
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "no events" in detail or "match" in detail


def test_export_json_writes_expected_structure(client, tmp_path):
    _seed_events(client, 3)

    resp = client.post("/api/job/export/json", json={"output_dir": str(tmp_path)})
    assert resp.status_code == 200
    data = resp.json()
    assert "output_path" in data

    out_path = Path(data["output_path"])
    assert out_path.exists()

    import json
    written = json.loads(out_path.read_text(encoding="utf-8"))

    assert isinstance(written, list)
    assert len(written) == 3
    for i, ev in enumerate(written):
        assert ev["event_index"] == i
        assert ev["start_s"] == float(i)
        assert ev["end_s"] == float(i + 1)
        assert ev["zone_label"] == ("Person" if i % 2 == 0 else "Car")
        assert ev["included"] is True


# ── Phase 8 test (T007) ──────────────────────────────────────────────────────

def test_thumbnail_stage_progress_after_run(client, tmp_path, monkeypatch):
    """Thumbnail progress must not advance before thumbnail_gen.run() is called.
    After the fix, report_stage_current == 0 when run() is invoked (no pre-run loop)."""
    import app.session as session
    session.reset()
    session.update(
        status="completed", job_id="test-job", source_path="/fake/video.mp4",
        source_info={"duration_s": 60.0}, settings={"mode": "mog2"},
        output_dir=str(tmp_path),
    )
    for i in range(2):
        session.append_event({
            "event_index": i, "start_s": float(i * 5), "end_s": float(i * 5 + 3),
            "peak_motion_score": 0.6, "zone_label": None, "included": True,
            "start_clock": f"00:00:0{i*5}", "end_clock": f"00:00:0{i*5+3}",
        })

    progress_at_run = []

    def spy_run(*args, **kwargs):
        snap = session.snapshot()
        progress_at_run.append(snap.get("report_stage_current", -1))

    monkeypatch.setattr("app.api.job.thumbnail_gen.run", spy_run)

    resp = client.post("/api/job/intel-report/export")
    assert resp.status_code == 200
    assert progress_at_run, "thumbnail_gen.run() was never called"
    # Before fix: progress_at_run[0] == 1 (loop ran ahead for 2 events, last index = 1)
    # After fix:  progress_at_run[0] == 0 (initial state, no pre-run loop)
    assert progress_at_run[0] == 0, (
        f"Thumbnail progress was {progress_at_run[0]} when run() was called; expected 0. "
        "Fix: remove the pre-thumbnail progress loop in app/api/job.py"
    )
