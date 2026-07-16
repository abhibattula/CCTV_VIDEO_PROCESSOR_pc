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

    assert events_found == [], "Pre-cancelled run must produce zero events — first test"


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


# ── Phase 10 T015 mock-counterpart tests (US6 AC6) ───────────────────────────

_SETTINGS = {
    "sensitivity": "medium",
    "frame_skip": 0,
    "padding_s": 2.0,
    "min_gap_s": 2.0,
    "min_event_s": 1.0,
    "zones": [],
    "recording_start": None,
}
_SOURCE_INFO = {"fps": 25.0, "duration_s": 2.4, "width": 320, "height": 240}


def _make_mock_capture(frame_count=60):
    frames = [np.zeros((240, 320, 3), dtype=np.uint8) for _ in range(frame_count)]
    idx = [0]

    class _MockCap:
        def __init__(self, *a): pass
        def isOpened(self): return True
        def read(self):
            if idx[0] < len(frames):
                f = frames[idx[0]]
                idx[0] += 1
                return True, f
            return False, None
        def get(self, prop):
            if prop == cv2.CAP_PROP_FRAME_COUNT: return float(frame_count)
            if prop == cv2.CAP_PROP_FPS: return 25.0
            if prop == cv2.CAP_PROP_FRAME_WIDTH: return 320.0
            if prop == cv2.CAP_PROP_FRAME_HEIGHT: return 240.0
            if prop == cv2.CAP_PROP_POS_MSEC: return idx[0] * 40.0
            return 0.0
        def release(self): pass
        def set(self, *a): return True

    return _MockCap


def test_run_emits_progress_and_events_with_mocked_capture(tmp_path, monkeypatch):
    from app.core import detection_engine as det
    monkeypatch.setattr(det.cv2, "VideoCapture", _make_mock_capture(60))
    progress_vals = []
    det.run(
        source_path="/fake.mp4",
        source_info=_SOURCE_INFO,
        settings=_SETTINGS,
        cancel_event=threading.Event(),
        on_progress=progress_vals.append,
        on_event=lambda ev: None,
        job_dir=tmp_path,
    )
    assert len(progress_vals) >= 1
    assert all(0.0 <= v <= 1.0 for v in progress_vals)


def test_run_respects_cancel_with_mocked_capture(tmp_path, monkeypatch):
    from app.core import detection_engine as det
    monkeypatch.setattr(det.cv2, "VideoCapture", _make_mock_capture(60))
    cancel = threading.Event()
    cancel.set()
    events = []
    det.run(
        source_path="/fake.mp4",
        source_info=_SOURCE_INFO,
        settings=_SETTINGS,
        cancel_event=cancel,
        on_progress=lambda p: None,
        on_event=events.append,
        job_dir=tmp_path,
    )
    assert events == []


def test_run_handles_capture_open_failure_mocked(tmp_path, monkeypatch):
    from app.core import detection_engine as det

    class _FailCap:
        def __init__(self, *a): pass
        def isOpened(self): return False
        def release(self): pass

    monkeypatch.setattr(det.cv2, "VideoCapture", _FailCap)
    with pytest.raises(RuntimeError):
        det.run(
            source_path="/fake.mp4",
            source_info=_SOURCE_INFO,
            settings=_SETTINGS,
            cancel_event=threading.Event(),
            on_progress=lambda p: None,
            on_event=lambda ev: None,
            job_dir=tmp_path,
        )


# ── Phase 15 T006: sampled (Fast Scan) path ───────────────────────────────────

import app.config as _config
from app.core.frame_source import FrameSourceError


def _sampled_settings(scan_speed="balanced", **over):
    s = dict(_SETTINGS)
    s.update({"scan_speed": scan_speed, "padding_s": 1.0, "min_gap_s": 1.0,
              "min_event_s": 1.0})
    s.update(over)
    return s


_SAMPLED_INFO = {"fps": 30.0, "duration_s": 10.0, "width": 320, "height": 240,
                 "codec": "h264", "rotation": 0}


def _detect_frame(white: bool) -> np.ndarray:
    W, H = _config.DETECT_WIDTH, _config.DETECT_HEIGHT
    val = 255 if white else 0
    return np.full((H, W, 3), val, dtype=np.uint8)


class _FakeStream:
    """Stands in for frame_source.FrameStream."""
    def __init__(self, frames, sample_fps, raise_after=None, returncode=0):
        self._frames = frames
        self.sample_fps = sample_fps
        self.decoder = "software"
        self.frames_delivered = 0
        self._raise_after = raise_after
        self._rc = returncode
        self.closed = False

    def __iter__(self):
        for i, f in enumerate(self._frames):
            if self._raise_after is not None and i >= self._raise_after:
                raise FrameSourceError("simulated mid-run failure")
            self.frames_delivered += 1
            yield f, i / self.sample_fps
        if self._raise_after is not None and self._raise_after >= len(self._frames):
            raise FrameSourceError("simulated mid-run failure")

    @property
    def returncode(self):
        return self._rc

    @property
    def stderr_tail(self):
        return ""

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class _FakeMOG:
    """Motion iff the (gray) frame is bright."""
    created_with: list[dict] = []

    def __init__(self, **kwargs):
        _FakeMOG.created_with.append(kwargs)

    def apply(self, gray):
        return ((gray > 128).astype(np.uint8)) * 255


def _fake_mog_factory(**kwargs):
    return _FakeMOG(**kwargs)


@pytest.fixture
def fake_mog(monkeypatch):
    from app.core import detection_engine as det
    _FakeMOG.created_with = []
    monkeypatch.setattr(det.cv2, "createBackgroundSubtractorMOG2",
                        _fake_mog_factory)
    return _FakeMOG


def _patch_open_frames(monkeypatch, stream, record=None):
    from app.core import detection_engine as det

    def fake_open(source_path, source_info, sample_fps, width, height, logger):
        if record is not None:
            record.update(sample_fps=sample_fps, width=width, height=height)
        stream.sample_fps = sample_fps
        return stream

    monkeypatch.setattr(det.frame_source, "open_frames", fake_open)


def test_sampled_motion_window_timestamps_and_heatmap(tmp_path, monkeypatch, fake_mog):
    """(a)+(c): motion at pts 4.0–6.0 s → one event with padded source-time bounds."""
    from app.core import detection_engine as det
    fps = 5.0
    frames = [_detect_frame(4.0 <= i / fps <= 6.0) for i in range(50)]  # 0–9.8 s
    _patch_open_frames(monkeypatch, _FakeStream(frames, fps))

    events, progress = [], []
    det.run(
        source_path="/fake.mp4", source_info=_SAMPLED_INFO,
        settings=_sampled_settings("balanced"),
        cancel_event=threading.Event(),
        on_progress=progress.append, on_event=events.append,
        job_dir=tmp_path,
    )
    assert len(events) == 1, f"expected exactly one event, got {events}"
    assert events[0]["start_s"] == pytest.approx(3.0, abs=0.3)   # 4.0 − padding 1.0
    assert events[0]["end_s"] == pytest.approx(7.2, abs=0.5)     # silence + padding
    assert max(progress) == 1.0
    assert (tmp_path / "heatmap.png").exists()


def test_sampled_mog2_history_rescaled(tmp_path, monkeypatch, fake_mog):
    """(b): history is seconds-based × effective fps; warmup ≥ 5 frames."""
    from app.core import detection_engine as det
    for speed, fps_expected in (("balanced", 5.0), ("fast", 2.0)):
        _FakeMOG.created_with = []
        frames = [_detect_frame(False) for _ in range(30)]
        _patch_open_frames(monkeypatch, _FakeStream(frames, fps_expected))
        det.run(
            source_path="/fake.mp4", source_info=_SAMPLED_INFO,
            settings=_sampled_settings(speed), cancel_event=threading.Event(),
            on_progress=lambda p: None, on_event=lambda ev: None,
            job_dir=tmp_path,
        )
        assert _FakeMOG.created_with, "sampled path must construct MOG2"
        hist = _FakeMOG.created_with[0]["history"]
        assert hist == int(det.HISTORY_SECONDS["medium"] * fps_expected)


def test_thorough_never_touches_frame_source(tmp_path, monkeypatch):
    """(d): thorough (and legacy settings without scan_speed) = old loop only."""
    from app.core import detection_engine as det

    def _boom(*a, **kw):
        raise AssertionError("frame_source must not be used in thorough mode")

    monkeypatch.setattr(det.frame_source, "open_frames", _boom)

    for settings in (_sampled_settings("thorough", frame_skip=1), dict(_SETTINGS)):
        monkeypatch.setattr(det.cv2, "VideoCapture", _make_mock_capture(60))
        det.run(
            source_path="/fake.mp4", source_info=_SOURCE_INFO,
            settings=settings, cancel_event=threading.Event(),
            on_progress=lambda p: None, on_event=lambda ev: None,
            job_dir=tmp_path,
        )


def test_sampled_zero_frames_falls_back_to_legacy(tmp_path, monkeypatch, fake_mog):
    """(e): empty pipe → legacy loop still completes the run."""
    from app.core import detection_engine as det
    _patch_open_frames(monkeypatch, _FakeStream([], 5.0))
    monkeypatch.setattr(det.cv2, "VideoCapture", _make_mock_capture(60))

    progress = []
    det.run(
        source_path="/fake.mp4", source_info=_SAMPLED_INFO,
        settings=_sampled_settings("balanced"), cancel_event=threading.Event(),
        on_progress=progress.append, on_event=lambda ev: None,
        job_dir=tmp_path,
    )
    assert progress and max(progress) == 1.0


def test_sampled_midrun_failure_discards_and_reruns_legacy(tmp_path, monkeypatch, fake_mog):
    """(f): pipe dies after motion frames → no duplicate/partial events leak."""
    from app.core import detection_engine as det
    fps = 5.0
    frames = [_detect_frame(True) for _ in range(40)]  # constant motion
    _patch_open_frames(monkeypatch, _FakeStream(frames, fps, raise_after=25))
    monkeypatch.setattr(det.cv2, "VideoCapture", _make_mock_capture(60))  # black → no motion

    events = []
    det.run(
        source_path="/fake.mp4", source_info=_SAMPLED_INFO,
        settings=_sampled_settings("balanced"), cancel_event=threading.Event(),
        on_progress=lambda p: None, on_event=events.append,
        job_dir=tmp_path,
    )
    assert events == [], "partial sampled events must be discarded on mid-run failure"


def test_sampled_fps_capped_at_source_fps(tmp_path, monkeypatch, fake_mog):
    """(g): 2 fps source in balanced mode samples at 2 fps — never upsample."""
    from app.core import detection_engine as det
    record = {}
    _patch_open_frames(monkeypatch, _FakeStream([_detect_frame(False)] * 4, 2.0),
                       record=record)
    info = dict(_SAMPLED_INFO, fps=2.0)
    det.run(
        source_path="/fake.mp4", source_info=info,
        settings=_sampled_settings("balanced"), cancel_event=threading.Event(),
        on_progress=lambda p: None, on_event=lambda ev: None,
        job_dir=tmp_path,
    )
    assert record["sample_fps"] == 2.0


def test_sampled_short_clip_single_frame(tmp_path, monkeypatch, fake_mog):
    """(h): a clip shorter than one sampling interval still analyzes ≥ 1 frame."""
    from app.core import detection_engine as det
    stream = _FakeStream([_detect_frame(False)], 5.0)
    _patch_open_frames(monkeypatch, stream)
    info = dict(_SAMPLED_INFO, duration_s=0.1)

    progress = []
    det.run(
        source_path="/fake.mp4", source_info=info,
        settings=_sampled_settings("balanced"), cancel_event=threading.Event(),
        on_progress=progress.append, on_event=lambda ev: None,
        job_dir=tmp_path,
    )
    assert stream.frames_delivered == 1
    assert progress and max(progress) == 1.0


def test_sampled_precancel_produces_no_events(tmp_path, monkeypatch, fake_mog):
    from app.core import detection_engine as det
    _patch_open_frames(monkeypatch, _FakeStream([_detect_frame(True)] * 20, 5.0))
    cancel = threading.Event()
    cancel.set()
    events = []
    det.run(
        source_path="/fake.mp4", source_info=_SAMPLED_INFO,
        settings=_sampled_settings("balanced"), cancel_event=cancel,
        on_progress=lambda p: None, on_event=events.append,
        job_dir=tmp_path,
    )
    assert events == []


# ── Phase 15 T020: normalization guard for long inputs ────────────────────────

def _bad_probe_cap(frame_count: float):
    class _Cap:
        def __init__(self, *a): pass
        def isOpened(self): return True
        def read(self): return False, None   # probe reads all fail → normalize path
        def get(self, prop):
            if prop == cv2.CAP_PROP_FRAME_COUNT: return frame_count
            if prop == cv2.CAP_PROP_FPS: return 25.0
            if prop == cv2.CAP_PROP_FRAME_WIDTH: return 320.0
            if prop == cv2.CAP_PROP_FRAME_HEIGHT: return 240.0
            return 0.0
        def release(self): pass
    return _Cap


def test_normalize_guard_warns_for_long_inputs(tmp_path, monkeypatch):
    from app.core import detection_engine as det
    normalize_calls = []
    monkeypatch.setattr(det, "_normalize_via_vc",
                        lambda *a, **kw: normalize_calls.append(a) or False)
    # 90,000 frames @ 25 fps = 3600 s (> 30 min threshold)
    monkeypatch.setattr(det.cv2, "VideoCapture", _bad_probe_cap(90000.0))

    logs = []
    det._open_video("/fake.mp4", tmp_path, 25.0, logs.append)

    warned = [m for m in logs if "warning" in m.lower()]
    assert warned, f"expected a WARNING log line before normalizing, got: {logs}"
    assert any("60" in m or "3600" in m for m in warned), (
        "warning must state the video's scale (minutes/seconds)"
    )
    assert normalize_calls, "repair must still proceed after the warning"


def test_normalize_guard_silent_for_short_inputs(tmp_path, monkeypatch):
    from app.core import detection_engine as det
    monkeypatch.setattr(det, "_normalize_via_vc",
                        lambda *a, **kw: False)
    # 7,500 frames @ 25 fps = 300 s (≤ 30 min) — no warning expected
    monkeypatch.setattr(det.cv2, "VideoCapture", _bad_probe_cap(7500.0))

    logs = []
    det._open_video("/fake.mp4", tmp_path, 25.0, logs.append)
    assert not [m for m in logs if "warning" in m.lower()]
