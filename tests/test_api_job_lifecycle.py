"""
Tests for start_job, cancel_job, and get_events API endpoints (US1, Phase 10).
All tests run without a video file, GPU, or display.
"""
import time
import builtins
import pytest

import app.session as session
import app.core.detection_engine as detection_engine
import app.core.yolo_detector as yolo_detector


def _fake_detector(*, source_path, source_info, settings,
                   cancel_event, on_progress, on_event, job_dir):
    time.sleep(0.05)
    if cancel_event.is_set():
        return
    on_progress(0.5)
    on_event({"start_s": 0.0, "end_s": 1.0, "zone_label": None,
              "peak_motion_score": 0.8, "included": True, "event_index": 0})
    on_event({"start_s": 2.0, "end_s": 3.0, "zone_label": None,
              "peak_motion_score": 0.6, "included": True, "event_index": 1})


def _raise_fn(**kw):
    raise RuntimeError("boom")


def _slow_detector(*, source_path, source_info, settings,
                   cancel_event, on_progress, on_event, job_dir):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if cancel_event.is_set():
            return
        time.sleep(0.05)
    on_event({"start_s": 0.0, "end_s": 1.0, "zone_label": None,
              "peak_motion_score": 0.5, "included": True, "event_index": 0})


def _poll_until_terminal(timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snap = session.snapshot()
        if snap["status"] in ("completed", "error", "cancelled"):
            return snap
        time.sleep(0.05)
    return session.snapshot()


class TestStartJobStateMachine:
    def test_reject_when_detecting(self, client):
        session.update(status="detecting")
        resp = client.post("/api/job/start", json={})
        assert resp.status_code == 400

    def test_reject_when_idle_no_job(self, client):
        # reset_session autouse leaves status="idle" — not in allowed set
        resp = client.post("/api/job/start", json={})
        assert resp.status_code == 400

    def test_returns_detecting_status(self, client, ready_session, monkeypatch):
        monkeypatch.setattr(detection_engine, "run", lambda **kw: None)
        resp = client.post("/api/job/start", json={})
        assert resp.status_code == 200
        assert resp.json()["status"] == "detecting"

    def test_yolo_missing_sets_error_status(self, client, ready_session, monkeypatch):
        # yolo_detector.run raises ImportError (simulating absent ultralytics);
        # start_job thread catches Exception → session status becomes "error"
        def _raise_import(**kw):
            raise ImportError("ultralytics not installed")
        monkeypatch.setattr(yolo_detector, "run", _raise_import)
        resp = client.post("/api/job/start", json={"mode": "yolo"})
        assert resp.status_code == 200  # endpoint always returns 200 (thread spawned)
        snap = _poll_until_terminal()
        assert snap["status"] == "error"


class TestStartJobThreadLifecycle:
    def test_thread_completes_with_two_events(self, client, ready_session, monkeypatch):
        monkeypatch.setattr(detection_engine, "run", _fake_detector)
        client.post("/api/job/start", json={})
        snap = _poll_until_terminal()
        assert snap["status"] == "completed"
        assert snap["event_count"] == 2

    def test_thread_exception_sets_error_status(self, client, ready_session, monkeypatch):
        monkeypatch.setattr(detection_engine, "run", _raise_fn)
        client.post("/api/job/start", json={})
        snap = _poll_until_terminal()
        assert snap["status"] == "error"
        assert snap["error_msg"] == "boom"

    def test_cancel_stops_thread(self, client, ready_session, monkeypatch):
        monkeypatch.setattr(detection_engine, "run", _slow_detector)
        client.post("/api/job/start", json={})
        client.post("/api/job/cancel", json={})
        snap = _poll_until_terminal()
        assert snap["status"] == "cancelled"


def test_cancel_job_sets_cancelled_status(client, ready_session, monkeypatch):
    monkeypatch.setattr(detection_engine, "run", _slow_detector)
    client.post("/api/job/start", json={})
    resp = client.post("/api/job/cancel", json={})
    assert resp.json()["status"] == "cancelled"
    _poll_until_terminal()  # let thread exit cleanly


def test_get_events_returns_empty_list(client, ready_session):
    resp = client.get("/api/job/events")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_events_after_detection(client, ready_session, monkeypatch):
    monkeypatch.setattr(detection_engine, "run", _fake_detector)
    client.post("/api/job/start", json={})
    _poll_until_terminal()
    resp = client.get("/api/job/events")
    assert resp.status_code == 200
    assert len(resp.json()) == 2
