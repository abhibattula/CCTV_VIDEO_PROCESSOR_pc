"""
Tests for yolo_detector.py (T066).
TDD: written before implementation, must fail first.
"""
import sys
import types
import pytest


# ---------------------------------------------------------------------------
# T066-a: module has a `run` callable
# ---------------------------------------------------------------------------

def test_yolo_detector_imports():
    """yolo_detector module must exist and expose a `run` callable."""
    from app.core import yolo_detector
    assert callable(getattr(yolo_detector, "run", None))


# ---------------------------------------------------------------------------
# T066-b: ImportError with helpful message when ultralytics is absent
# ---------------------------------------------------------------------------

def test_yolo_unavailable_raises_helpful_error(monkeypatch):
    """
    When ultralytics is not installed, calling run() must raise ImportError
    whose message contains 'ultralytics'.
    """
    import threading
    from pathlib import Path

    # Force ultralytics to appear absent by removing it from sys.modules
    # and patching the import inside the module.
    saved = sys.modules.get("ultralytics")
    sys.modules["ultralytics"] = None  # type: ignore

    try:
        # Re-import the module so it re-evaluates the ultralytics import
        import importlib
        import app.core.yolo_detector as yd
        importlib.reload(yd)

        events = []
        source_info = {"fps": 25.0, "width": 1920, "height": 1080,
                       "duration_s": 10.0, "has_audio": False,
                       "audio_codec": "", "needs_reencode": False}
        settings = {"mode": "yolo", "sensitivity": "medium",
                    "padding_s": 1.0, "min_event_s": 1.0,
                    "min_gap_s": 1.0, "zones": [],
                    "recording_start": None}
        cancel = threading.Event()
        job_dir = Path(".")

        with pytest.raises(ImportError) as exc_info:
            yd.run(
                source_path="fake.mp4",
                source_info=source_info,
                settings=settings,
                cancel_event=cancel,
                on_progress=lambda p: None,
                on_event=lambda ev: events.append(ev),
                job_dir=job_dir,
            )
        assert "ultralytics" in str(exc_info.value).lower()
    finally:
        # Restore
        if saved is None:
            sys.modules.pop("ultralytics", None)
        else:
            sys.modules["ultralytics"] = saved
