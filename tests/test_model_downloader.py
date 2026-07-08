"""
Tests for app/core/model_downloader.py — the shared AI-model download engine
used by both the first-run wizard and the /api/system/ai-download endpoint.
Pure Python; no Qt, no network (http_download is monkeypatched).
"""
import hashlib
import threading
import time

import pytest

from app.core import model_downloader as md


# ---------------------------------------------------------------------------
# build_model_list — RAM gating
# ---------------------------------------------------------------------------

def test_build_model_list_yolo_only_when_ai_disabled(monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg, "AI_FEATURES_ENABLED", False)
    names = [m["name"] for m in md.build_model_list()]
    assert names == ["YOLOv8n"]


def test_build_model_list_all_models_when_ai_enabled(monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg, "AI_FEATURES_ENABLED", True)
    names = [m["name"] for m in md.build_model_list()]
    assert "YOLOv8n" in names
    assert "Florence-2" in names
    assert "CLIP ViT-B/32" in names


# ---------------------------------------------------------------------------
# verify_sha256
# ---------------------------------------------------------------------------

def test_verify_sha256_match(tmp_path):
    f = tmp_path / "w.bin"
    f.write_bytes(b"weights")
    assert md.verify_sha256(f, hashlib.sha256(b"weights").hexdigest()) is True


def test_verify_sha256_mismatch(tmp_path):
    f = tmp_path / "w.bin"
    f.write_bytes(b"weights")
    assert md.verify_sha256(f, "0" * 64) is False


# ---------------------------------------------------------------------------
# download_models — orchestration
# ---------------------------------------------------------------------------

def _model(tmp_path, *, sha=None, required=True):
    return {
        "name": "YOLOv8n",
        "url": "https://example.com/yolov8n.pt",
        "dest": tmp_path / "yolov8n.pt",
        "sha256": sha,
        "size": 100,
        "required": required,
    }


def test_download_models_success(tmp_path, monkeypatch):
    content = b"good"
    sha = hashlib.sha256(content).hexdigest()

    def fake_http(url, dest, progress_cb=None):
        dest.write_bytes(content)

    monkeypatch.setattr(md, "http_download", fake_http)
    ok, err = md.download_models(models=[_model(tmp_path, sha=sha)])
    assert ok is True
    assert err == ""
    assert (tmp_path / "yolov8n.pt").exists()


def test_download_models_skips_cached_file(tmp_path, monkeypatch):
    content = b"cached"
    sha = hashlib.sha256(content).hexdigest()
    dest = tmp_path / "yolov8n.pt"
    dest.write_bytes(content)

    calls = []
    monkeypatch.setattr(md, "http_download", lambda *a, **k: calls.append(a))
    ok, _ = md.download_models(models=[_model(tmp_path, sha=sha)])
    assert ok is True
    assert calls == []


def test_download_models_fails_after_retries_on_bad_hash(tmp_path, monkeypatch):
    def bad_http(url, dest, progress_cb=None):
        dest.write_bytes(b"corrupt")

    monkeypatch.setattr(md, "http_download", bad_http)
    ok, err = md.download_models(models=[_model(tmp_path, sha="a" * 64)])
    assert ok is False
    assert err != ""


def test_download_models_optional_failure_still_succeeds(tmp_path, monkeypatch):
    def bad_http(url, dest, progress_cb=None):
        raise OSError("network down")

    monkeypatch.setattr(md, "http_download", bad_http)
    ok, err = md.download_models(models=[_model(tmp_path, sha=None, required=False)])
    assert ok is True


# ---------------------------------------------------------------------------
# Background download + status registry
# ---------------------------------------------------------------------------

def test_get_status_initial_state():
    md._reset_status_for_tests()
    st = md.get_status()
    assert st["state"] == "idle"
    assert st["pct"] == 0


def test_start_background_download_runs_and_completes(tmp_path, monkeypatch):
    md._reset_status_for_tests()
    content = b"ok"
    sha = hashlib.sha256(content).hexdigest()

    def fake_http(url, dest, progress_cb=None):
        dest.write_bytes(content)

    monkeypatch.setattr(md, "http_download", fake_http)
    monkeypatch.setattr(md, "build_model_list", lambda: [_model(tmp_path, sha=sha)])

    assert md.start_background_download() is True
    # Wait for the worker thread to finish (fast — no real network)
    for _ in range(100):
        if md.get_status()["state"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert md.get_status()["state"] == "done"


def test_start_background_download_rejects_concurrent_start(tmp_path, monkeypatch):
    md._reset_status_for_tests()
    release = threading.Event()

    def slow_http(url, dest, progress_cb=None):
        release.wait(timeout=5)
        dest.write_bytes(b"x")

    monkeypatch.setattr(md, "http_download", slow_http)
    monkeypatch.setattr(md, "build_model_list", lambda: [_model(tmp_path)])

    assert md.start_background_download() is True
    try:
        assert md.start_background_download() is False  # already running
    finally:
        release.set()
        for _ in range(100):
            if md.get_status()["state"] in ("done", "error"):
                break
            time.sleep(0.05)


def test_background_download_resets_frame_analyzer_cache(tmp_path, monkeypatch):
    """After a successful download, FrameAnalyzer must re-check availability."""
    md._reset_status_for_tests()
    from app.core.frame_analyzer import FrameAnalyzer
    monkeypatch.setattr(FrameAnalyzer, "_availability_cache", False)

    monkeypatch.setattr(md, "http_download", lambda u, d, progress_cb=None: d.write_bytes(b"x"))
    monkeypatch.setattr(md, "build_model_list", lambda: [_model(tmp_path)])

    md.start_background_download()
    for _ in range(100):
        if md.get_status()["state"] in ("done", "error"):
            break
        time.sleep(0.05)

    assert FrameAnalyzer._availability_cache is None  # cache invalidated
