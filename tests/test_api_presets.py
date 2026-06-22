"""
Tests for /api/presets router (GET/POST/DELETE).
T002: Written as failing tests (TDD) before T003 implementation.
Uses monkeypatch to direct PRESETS_FILE to tmp_path — never touches real ~/.cctv_processor.
"""
import json
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_temp_presets(monkeypatch, tmp_path):
    """
    Create a fresh TestClient with a monkeypatched temp PRESETS_FILE.
    This ensures the app is instantiated AFTER the monkeypatch is applied.
    Monkeypatch both app.config and app.api.presets since presets imports it at module level.
    """
    presets_file_path = tmp_path / "presets.json"
    monkeypatch.setattr("app.config.PRESETS_FILE", presets_file_path)
    # Reload the presets module to pick up the monkeypatched config
    import importlib
    import app.api.presets
    importlib.reload(app.api.presets)
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_list_presets_empty_when_file_missing(client_with_temp_presets):
    """GET /api/presets returns [] when file doesn't exist."""
    resp = client_with_temp_presets.get("/api/presets")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_presets_empty_when_file_corrupted(client_with_temp_presets):
    """GET /api/presets returns [] when file contains invalid JSON (not 500 error)."""
    import app.config
    app.config.PRESETS_FILE.write_text("{ invalid json", encoding="utf-8")
    resp = client_with_temp_presets.get("/api/presets")
    assert resp.status_code == 200
    assert resp.json() == []


def test_presets_empty_when_file_has_wrong_shape(client_with_temp_presets):
    """
    A presets.json containing syntactically-valid JSON that isn't a list of
    dicts (e.g. an empty object, written by disk corruption or a future schema
    change) must be treated as corrupt: GET returns [], and POST must not crash
    trying to .append() onto a non-list.
    """
    import app.config
    app.config.PRESETS_FILE.write_text("{}", encoding="utf-8")

    resp = client_with_temp_presets.get("/api/presets")
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client_with_temp_presets.post("/api/presets", json={
        "name": "After Corruption",
        "output_type": "merged",
        "quality": "original",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "After Corruption"


def test_create_preset_success(client_with_temp_presets):
    """POST /api/presets creates a preset; GET shows it."""
    resp = client_with_temp_presets.post("/api/presets", json={
        "name": "My Export",
        "output_type": "merged",
        "quality": "original",
        "burn_in": False,
        "label_filter": [],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "My Export"
    assert data["output_type"] == "merged"

    # Verify it persists
    resp = client_with_temp_presets.get("/api/presets")
    assert resp.status_code == 200
    presets = resp.json()
    assert len(presets) == 1
    assert presets[0]["name"] == "My Export"


def test_create_preset_empty_name_rejected(client_with_temp_presets):
    """POST /api/presets rejects whitespace-only names with 400."""
    resp = client_with_temp_presets.post("/api/presets", json={
        "name": "   ",
        "output_type": "merged",
        "quality": "original",
    })
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_create_preset_builtin_name_rejected(client_with_temp_presets):
    """POST /api/presets rejects case-insensitive built-in name collision."""
    # "security report" (lowercase) should collide with "Security Report" (built-in)
    resp = client_with_temp_presets.post("/api/presets", json={
        "name": "security report",
        "output_type": "merged",
        "quality": "original",
    })
    assert resp.status_code == 400
    assert "built-in" in resp.json()["detail"].lower()


def test_create_preset_duplicate_name_rejected(client_with_temp_presets):
    """POST /api/presets rejects case-insensitive + trimmed duplicate."""
    # First, create a custom preset
    resp = client_with_temp_presets.post("/api/presets", json={
        "name": "weekly report",
        "output_type": "merged",
        "quality": "original",
    })
    assert resp.status_code == 200

    # Try to create a duplicate with different case and trailing space
    resp = client_with_temp_presets.post("/api/presets", json={
        "name": "Weekly Report ",  # different case + space
        "output_type": "merged",
        "quality": "original",
    })
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"].lower()


def test_delete_preset_success(client_with_temp_presets):
    """DELETE /api/presets/{name} removes the preset."""
    # Create a preset
    resp = client_with_temp_presets.post("/api/presets", json={
        "name": "Temp Preset",
        "output_type": "merged",
        "quality": "original",
    })
    assert resp.status_code == 200

    # Delete it
    resp = client_with_temp_presets.delete("/api/presets/Temp Preset")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == "Temp Preset"

    # Verify it's gone
    resp = client_with_temp_presets.get("/api/presets")
    assert resp.status_code == 200
    assert resp.json() == []


def test_delete_preset_not_found(client_with_temp_presets):
    """DELETE /api/presets/{name} returns 404 for unknown preset."""
    resp = client_with_temp_presets.delete("/api/presets/NonExistent")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_delete_preset_case_insensitive_and_trimmed(client_with_temp_presets):
    """
    DELETE must use the same case-insensitive + trimmed identity rule as
    POST's collision check (one identity model for create and delete, not
    two) -- found by the final whole-branch review.
    """
    resp = client_with_temp_presets.post("/api/presets", json={
        "name": "Weekly Report",
        "output_type": "merged",
        "quality": "original",
    })
    assert resp.status_code == 200

    # Delete using a different case and extra whitespace.
    resp = client_with_temp_presets.delete("/api/presets/weekly report ")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == "weekly report "

    resp = client_with_temp_presets.get("/api/presets")
    assert resp.status_code == 200
    assert resp.json() == []
