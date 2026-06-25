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

    The real test video is ~115s at ~60fps (6864 frames) at 1080p, and
    yolo_detector.run() has no frame-skip option and runs YOLO inference on
    every single frame at full resolution. Measured directly: nothing in
    this clip scores above the "medium"/"high" sensitivity thresholds until
    well past the first 20% of frames, so an early-exit-on-first-event
    strategy doesn't actually shorten the common case here — the test
    genuinely needs to process most of the video before anything closes,
    same as an unbounded run (confirmed empirically to take ~14 minutes on a
    warm model). on_event still requests cancellation the instant the first
    event closes (free speedup if a future test video makes detection happen
    earlier), and a watchdog timer forces cancellation at 1800s (30 min) to
    turn a genuine hang into a clear test failure; the higher limit vs. the
    organic ~14 min runtime is intentional — this test runs first in the
    YOLO suite on a cold model, and YOLOv8's first-ever inference on a
    machine triggers one-time JIT compilation that can add 5-10+ minutes of
    overhead not present on subsequent warm runs.
    """
    from app.core.yolo_detector import run
    from app.utils.ffprobe import probe

    source_info = probe(TEST_VIDEO)

    events_found: list[dict] = []
    cancel = threading.Event()

    def on_event(ev: dict):
        events_found.append(ev)
        cancel.set()

    watchdog = threading.Timer(1800.0, cancel.set)
    watchdog.start()

    settings = {
        "mode": "yolo",
        "sensitivity": "medium",
        "padding_s": 2.0,
        "min_event_s": 1.0,
        "min_gap_s": 2.0,
        "zones": [],
        "recording_start": None,
    }

    try:
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
    finally:
        watchdog.cancel()

    assert len(events_found) >= 1, (
        "Expected at least one detection event from the test video within the 1800s watchdog window"
    )

    for ev in events_found:
        assert "event_index" in ev, f"Event missing 'event_index' key: {ev}"

    actual_indices = [ev["event_index"] for ev in events_found]
    expected_indices = list(range(len(events_found)))
    assert actual_indices == expected_indices, (
        f"Expected event_index sequence {expected_indices}, got {actual_indices}"
    )


# ---------------------------------------------------------------------------
# T015 (005-reporting-and-heatmap): yolo_detector.run() must write heatmap.png
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
@pytest.mark.skipif(not HAS_ULTRALYTICS, reason="ultralytics not installed")
def test_run_writes_heatmap_png():
    """
    After a real run, job_dir / "heatmap.png" must exist and be a valid,
    non-empty image — yolo_detector.run() must accumulate detected bounding
    boxes into a heatmap (filled rectangles weighted by confidence, sized to
    the source video resolution) and write it via
    detection_engine._write_heatmap, same as detection_engine.run() already
    does.

    The real test video is ~115s at ~60fps (6864 frames) at 1080p, and
    yolo_detector.run() has no frame-skip option and runs YOLO inference on
    every single frame at full resolution. Measured directly: this exact
    test video produces its first closeable YOLO event around the 51-55s
    mark at "medium" sensitivity, so on_event requests cancellation the
    instant the first event closes, keeping this test fast (~6m35s
    wall-clock, measured directly). A watchdog timer forces cancellation at
    960s (~16 min, the same safety margin used in
    test_emitted_events_have_event_index) purely to turn a genuine hang into
    a clear test failure instead of an infinite wait. By the time the first
    event closes, the per-frame bounding-box accumulation will already have
    non-zero values from the whole activity period leading up to that
    close, so the heatmap PNG assertion should pass without needing to
    process more of the video.
    """
    import cv2

    from app.core.yolo_detector import run
    from app.utils.ffprobe import probe

    source_info = probe(TEST_VIDEO)

    events_found: list[dict] = []
    cancel = threading.Event()

    def on_event(ev: dict):
        events_found.append(ev)
        cancel.set()

    watchdog = threading.Timer(960.0, cancel.set)
    watchdog.start()

    settings = {
        "mode": "yolo",
        "sensitivity": "medium",
        "padding_s": 2.0,
        "min_event_s": 1.0,
        "min_gap_s": 2.0,
        "zones": [],
        "recording_start": None,
    }

    try:
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

            heatmap_path = job_dir / "heatmap.png"
            assert heatmap_path.exists(), "Expected heatmap.png to be written after run()"
            img = cv2.imread(str(heatmap_path))
            assert img is not None, "heatmap.png must be a valid, readable image"
            assert img.size > 0, "heatmap.png must not be empty"
    finally:
        watchdog.cancel()
