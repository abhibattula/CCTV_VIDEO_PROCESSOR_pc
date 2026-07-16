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
    # Phase 15 extended the response shape; yolo_available semantics unchanged
    assert resp.json()["yolo_available"] is False


# ── Phase 15 T017: capabilities acceleration report ──────────────────────────

def test_system_capabilities_acceleration_shape(client, monkeypatch):
    import app.core.frame_source as fs
    monkeypatch.setattr(
        fs, "get_acceleration_status",
        lambda: {"methods_available": ["qsv", "cuda"], "selected": {"hevc": "qsv"}},
    )
    import app.utils.ai_device as ai_device
    monkeypatch.setattr(ai_device, "describe_ai_device", lambda: "cpu")

    resp = client.get("/api/system/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert "yolo_available" in data
    assert data["ai_device"] == "cpu"
    assert data["decode_acceleration"]["methods_available"] == ["qsv", "cuda"]
    assert data["decode_acceleration"]["selected"] == {"hevc": "qsv"}


def test_system_capabilities_survives_hwaccel_query_failure(client, monkeypatch):
    import app.core.frame_source as fs

    def boom():
        raise OSError("no ffmpeg")

    monkeypatch.setattr(fs, "_query_hwaccels", boom)
    fs._reset_for_tests()
    try:
        resp = client.get("/api/system/capabilities")
        assert resp.status_code == 200
        assert resp.json()["decode_acceleration"]["methods_available"] == []
    finally:
        fs._reset_for_tests()


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
