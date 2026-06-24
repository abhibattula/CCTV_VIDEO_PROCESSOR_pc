"""
Tests for yolo_detector.py (T066).
TDD: written before implementation, must fail first.
"""
import os
import sys
import threading
import types
import tempfile
from pathlib import Path

import pytest

TEST_VIDEO = str(
    Path(__file__).parent.parent
    / "OLD RASPBERRI PI VERSION"
    / "Test Video"
    / "20260507_012210 (1).mp4"
)
HAS_TEST_VIDEO = os.path.isfile(TEST_VIDEO)

try:
    import ultralytics  # noqa: F401
    HAS_ULTRALYTICS = True
except Exception:
    HAS_ULTRALYTICS = False


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


# ---------------------------------------------------------------------------
# T003 (005-reporting-and-heatmap): emitted events must carry event_index
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
@pytest.mark.skipif(not HAS_ULTRALYTICS, reason="ultralytics not installed")
def test_emitted_events_have_event_index():
    """
    Every event dict yielded via on_event during a real run must contain an
    'event_index' key, incrementing 0, 1, 2, ... across emitted events.

    Regression test for a bug in app/core/yolo_detector.py's _emit_event:
    it currently builds event dicts with no 'event_index' field at all
    (unlike app/core/detection_engine.py, which always sets it).
    """
    from app.core.yolo_detector import run
    from app.utils.ffprobe import probe

    source_info = probe(TEST_VIDEO)

    events_found: list[dict] = []

    def on_event(ev: dict):
        events_found.append(ev)

    cancel = threading.Event()
    settings = {
        "mode": "yolo",
        "sensitivity": "medium",
        "padding_s": 2.0,
        "min_event_s": 1.0,
        "min_gap_s": 2.0,
        "zones": [],
        "recording_start": None,
    }

    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp)
        run(
            source_path=TEST_VIDEO,
            source_info=source_info,
            settings=settings,
            cancel_event=cancel,
            on_progress=lambda p: None,
            on_event=on_event,
            job_dir=job_dir,
        )

    assert len(events_found) >= 1, "Expected at least one detection event from the test video"

    for ev in events_found:
        assert "event_index" in ev, f"Event missing 'event_index' key: {ev}"

    actual_indices = [ev["event_index"] for ev in events_found]
    expected_indices = list(range(len(events_found)))
    assert actual_indices == expected_indices, (
        f"Expected event_index sequence {expected_indices}, got {actual_indices}"
    )
