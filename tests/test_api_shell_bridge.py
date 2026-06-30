"""
Tests for shell bridge API endpoints (US2, Phase 10).
All tests run without a display or Qt process.
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import app.session as session
import app.api.shell_bridge as shell_bridge


_OUTPUT_PATH = "C:/Users/test/outputs/video_export.mp4"


def test_set_filepath_stores_path(client):
    resp = client.post("/api/shell/filepath", json={"path": "/tmp/test.mp4"})
    assert resp.status_code == 200
    assert session.snapshot()["pending_path"] == "/tmp/test.mp4"


def test_get_pending_path_returns_and_clears(client):
    session.update(pending_path="/tmp/test.mp4")
    resp = client.get("/api/shell/pending-path")
    assert resp.json() == {"path": "/tmp/test.mp4"}
    resp2 = client.get("/api/shell/pending-path")
    assert resp2.json() == {"path": None}


def test_get_pending_path_returns_null_when_empty(client):
    resp = client.get("/api/shell/pending-path")
    assert resp.json() == {"path": None}


def test_set_output_dir_updates_session(client):
    resp = client.post("/api/shell/set-output-dir", json={"output_dir": "/home/user/outputs"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert session.snapshot()["output_dir"] == "/home/user/outputs"


def test_open_folder_calls_platform_open(client, monkeypatch):
    mock_fn = MagicMock()
    monkeypatch.setattr(shell_bridge, "_open_folder", mock_fn)
    session.update(output_path=_OUTPUT_PATH)
    resp = client.post("/api/shell/open-folder")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    expected_folder = str(Path(_OUTPUT_PATH).parent)
    mock_fn.assert_called_once_with(expected_folder)


def test_open_folder_returns_false_when_no_output_path(client):
    resp = client.post("/api/shell/open-folder")
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
