"""
Tests for system API endpoints (US6, Phase 10).
Runs without GPU or special hardware.
"""
import sys
import pytest


def test_system_stats_has_correct_keys(client):
    resp = client.get("/api/system/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"cpu_pct", "ram_pct", "cpu_temp"}


def test_system_capabilities_yolo_false_when_not_installed(client, monkeypatch):
    monkeypatch.setitem(sys.modules, "ultralytics", None)
    resp = client.get("/api/system/capabilities")
    assert resp.status_code == 200
    assert resp.json() == {"yolo_available": False}


def test_system_ai_status_shape(client):
    resp = client.get("/api/system/ai-status")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {
        "ai_supported", "florence_available", "florence_reason",
        "clip_available", "yolo_model_present", "download",
    }
    assert data["download"]["state"] in ("idle", "running", "done", "error")


def test_system_ai_download_starts_background(client, monkeypatch):
    from app.core import model_downloader

    calls = []
    monkeypatch.setattr(model_downloader, "start_background_download",
                        lambda: calls.append(1) or True)
    resp = client.post("/api/system/ai-download")
    assert resp.status_code == 200
    assert resp.json()["started"] is True
    assert calls == [1]


def test_system_ai_download_reports_already_running(client, monkeypatch):
    from app.core import model_downloader

    monkeypatch.setattr(model_downloader, "start_background_download", lambda: False)
    resp = client.post("/api/system/ai-download")
    assert resp.status_code == 200
    assert resp.json()["started"] is False
