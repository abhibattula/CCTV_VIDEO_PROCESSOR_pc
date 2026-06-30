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
