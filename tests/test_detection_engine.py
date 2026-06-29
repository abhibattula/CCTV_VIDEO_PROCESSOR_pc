"""
Tests for app/core/detection_engine.py — written BEFORE implementation (TDD).
Video-dependent tests skip if the test video is absent.
"""
import inspect
import os
import threading
import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

TEST_VIDEO = str(
    Path(__file__).parent.parent
    / "OLD RASPBERRI PI VERSION"
    / "Test Video"
    / "20260507_012210 (1).mp4"
)
HAS_TEST_VIDEO = os.path.isfile(TEST_VIDEO)


def test_detection_engine_has_run_attr():
    from app.core import detection_engine
    assert hasattr(detection_engine, "run"), "detection_engine must expose a 'run' function"
    assert callable(detection_engine.run)


def test_run_signature_accepts_callbacks():
    from app.core.detection_engine import run
    sig = inspect.signature(run)
    params = list(sig.parameters.keys())
    assert "on_progress" in params, f"run() missing 'on_progress' param; got: {params}"
    assert "on_event" in params, f"run() missing 'on_event' param; got: {params}"
    assert "cancel_event" in params, f"run() missing 'cancel_event' param; got: {params}"
    assert "source_path" in params, f"run() missing 'source_path' param; got: {params}"


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_detection_finds_events_on_real_video():
    from app.core.detection_engine import run
    from app.utils.ffprobe import probe

    source_info = probe(TEST_VIDEO)

    progress_values: list[float] = []
    events_found: list[dict] = []

    def on_progress(p: float):
        progress_values.append(p)

    def on_event(ev: dict):
        events_found.append(ev)

    cancel = threading.Event()
    settings = {
        "sensitivity": "medium",
        "frame_skip": 3,
        "padding_s": 2.0,
        "min_gap_s": 2.0,
        "min_event_s": 1.0,
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
            on_progress=on_progress,
            on_event=on_event,
            job_dir=job_dir,
        )

    assert len(events_found) >= 1, "Expected at least one motion event from the test video"
    assert max(progress_values) >= 0.99, "Expected progress to reach ~1.0"
    # Validate event dict shape
    ev = events_found[0]
    assert "start_s" in ev
    assert "end_s" in ev
    assert ev["end_s"] > ev["start_s"]
    assert "peak_motion_score" in ev
    assert "included" in ev


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_detection_respects_cancel():
    from app.core.detection_engine import run
    from app.utils.ffprobe import probe

    source_info = probe(TEST_VIDEO)
    events_found: list[dict] = []
    cancel = threading.Event()
    cancel.set()  # pre-cancel before calling run()

    settings = {
        "sensitivity": "medium",
        "frame_skip": 0,
        "padding_s": 2.0,
        "min_gap_s": 2.0,
        "min_event_s": 1.0,
        "zones": [],
        "recording_start": None,
    }

    with tempfile.TemporaryDirectory() as tmp:
        run(
            source_path=TEST_VIDEO,
            source_info=source_info,
            settings=settings,
            cancel_event=cancel,
            on_progress=lambda p: None,
            on_event=events_found.append,
            job_dir=Path(tmp),
        )

    assert events_found == [], "Pre-cancelled run must produce zero events"


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_run_writes_heatmap_png():
    from app.core.detection_engine import run
    from app.utils.ffprobe import probe

    source_info = probe(TEST_VIDEO)
    cancel = threading.Event()
    settings = {
        "sensitivity": "medium",
        "frame_skip": 3,
        "padding_s": 2.0,
        "min_gap_s": 2.0,
        "min_event_s": 1.0,
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
            on_event=lambda ev: None,
            job_dir=job_dir,
        )

        heatmap_path = job_dir / "heatmap.png"
        assert heatmap_path.exists(), "Expected heatmap.png to be written after run()"
        img = cv2.imread(str(heatmap_path))
        assert img is not None, "heatmap.png must be a valid, readable image"
        assert img.size > 0, "heatmap.png must not be empty"


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_heatmap_matches_source_resolution():
    from app.core.detection_engine import run
    from app.utils.ffprobe import probe

    source_info = probe(TEST_VIDEO)
    cancel = threading.Event()
    settings = {
        "sensitivity": "medium",
        "frame_skip": 3,
        "padding_s": 2.0,
        "min_gap_s": 2.0,
        "min_event_s": 1.0,
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
            on_event=lambda ev: None,
            job_dir=job_dir,
        )

        heatmap_path = job_dir / "heatmap.png"
        if not heatmap_path.exists():
            pytest.skip("Test video produced no MOG2 foreground — heatmap resolution check skipped")
        img = cv2.imread(str(heatmap_path))
        assert img is not None, "heatmap.png must be a valid, readable image"
        # Must match the SOURCE video's resolution (upscaled), not the
        # smaller internal DETECT_WIDTH/DETECT_HEIGHT working resolution.
        assert img.shape[:2] == (source_info["height"], source_info["width"]), (
            f"Expected heatmap shape {(source_info['height'], source_info['width'])}, "
            f"got {img.shape[:2]}"
        )


def test_heatmap_skipped_on_zero_motion(tmp_path):
    from app.core.detection_engine import _write_heatmap

    job_dir = tmp_path
    accum = np.zeros((360, 640), dtype=np.float32)
    source_info = {"width": 1920, "height": 1080}
    _write_heatmap(accum, source_info, job_dir)

    assert not (job_dir / "heatmap.png").exists(), (
        "heatmap.png must NOT be written when zero motion was accumulated"
    )


@pytest.mark.skipif(not HAS_TEST_VIDEO, reason="Test video not available")
def test_cancelled_run_still_attempts_heatmap_write():
    from app.core.detection_engine import run
    from app.utils.ffprobe import probe

    source_info = probe(TEST_VIDEO)
    events_found: list[dict] = []
    cancel = threading.Event()
    cancel.set()  # pre-cancel before calling run()

    settings = {
        "sensitivity": "medium",
        "frame_skip": 0,
        "padding_s": 2.0,
        "min_gap_s": 2.0,
        "min_event_s": 1.0,
        "zones": [],
        "recording_start": None,
    }

    with tempfile.TemporaryDirectory() as tmp:
        # No exception should propagate even though cancellation happened
        # before any frame was processed (heatmap_accum will be all-zero,
        # so heatmap.png may or may not exist — that is not asserted here).
        run(
            source_path=TEST_VIDEO,
            source_info=source_info,
            settings=settings,
            cancel_event=cancel,
            on_progress=lambda p: None,
            on_event=events_found.append,
            job_dir=Path(tmp),
        )

    assert events_found == [], "Pre-cancelled run must produce zero events"
