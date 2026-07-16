"""
YOLO-based motion/object detector — PC version.

Same `run()` interface as detection_engine.run(), so job.py can swap
between engines transparently via settings["mode"].

Requires: pip install ultralytics
Model is auto-downloaded to MODEL_DIR on first use (~6 MB for yolov8n.pt).

Raises ImportError with install hint if ultralytics is not installed.
"""
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from app.config import MODEL_DIR, BATCH_SIZE, YOLO_FRAME_SKIP
from app.core import frame_source
from app.utils import ai_device

# Sampled (Fast Scan) modes decode at 640×360 — yolov8's native input is
# 640 px, so detect-resolution frames would cost small-object recall.
SAMPLED_W, SAMPLED_H = 640, 360

# Expose time module so tests can monkeypatch it
import time as _time_module

# ── Warm-up state ─────────────────────────────────────────────────────────────
_model_ready: threading.Event = threading.Event()
_cached_yolo_model = None
_model_lock = threading.Lock()

# YOLO class IDs we care about (COCO dataset subset)
_LABEL_MAP: dict[int, str] = {
    0:  "Person",
    1:  "Bicycle",
    2:  "Car",
    3:  "Motorcycle",
    5:  "Bus",
    7:  "Truck",
    14: "Bird",
    15: "Cat",
    16: "Dog",
    17: "Horse",
    18: "Sheep",
    19: "Cow",
}

# Confidence thresholds per sensitivity
_CONF: dict[str, float] = {
    "low":    0.6,
    "medium": 0.4,
    "high":   0.25,
}

# Minimum IoU / frame score to open a new event
_SCORE_THRESH: dict[str, float] = {
    "low":    0.5,
    "medium": 0.3,
    "high":   0.15,
}


def _require_ultralytics():
    import sys
    mod = sys.modules.get("ultralytics")
    if mod is None:
        raise ImportError(
            "ultralytics is not installed. "
            "Install it with: pip install ultralytics"
        )
    # Normal import path
    try:
        import ultralytics  # noqa: F401
        return ultralytics
    except Exception as exc:
        raise ImportError(
            f"ultralytics import failed: {exc}. "
            "Install it with: pip install ultralytics"
        ) from exc


def prewarm() -> None:
    """Load the YOLO model in a background daemon thread and signal _model_ready.

    Called once from job.py after POST /api/job/create so the model is ready
    by the time run() is called. Idempotent — silently does nothing if the
    model is already cached.  Never raises.
    """
    def _load():
        global _cached_yolo_model
        try:
            _require_ultralytics()
            from ultralytics import YOLO  # type: ignore
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            model_path = MODEL_DIR / "yolov8n.pt"
            with _model_lock:
                if _cached_yolo_model is None:
                    _cached_yolo_model = YOLO(str(model_path))
        except Exception:
            pass
        finally:
            _model_ready.set()

    threading.Thread(target=_load, daemon=True, name="yolo-prewarm").start()


def run(
    source_path: str,
    source_info: dict,
    settings: dict,
    cancel_event: threading.Event,
    on_progress: Callable[[float], None],
    on_event: Callable[[dict], None],
    job_dir: Path,
    logger: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Run YOLO object detection on source_path.

    Emits events via on_event(dict) and progress via on_progress(float 0-1).
    Raises ImportError if ultralytics is not installed. scan_speed
    "balanced"/"fast" uses the sampled FFmpeg frame source (falls back to the
    legacy loop on pipe failure); "thorough"/absent is the legacy loop.
    """
    _require_ultralytics()

    from ultralytics import YOLO  # type: ignore

    _log = logger or (lambda msg: None)
    sensitivity = settings.get("sensitivity", "medium")
    padding_s   = float(settings.get("padding_s", 1.0))
    min_event_s = float(settings.get("min_event_s", 1.0))
    min_gap_s   = float(settings.get("min_gap_s", 1.0))
    recording_start = settings.get("recording_start")

    conf_thresh  = _CONF.get(sensitivity, 0.4)
    score_thresh = _SCORE_THRESH.get(sensitivity, 0.3)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "yolov8n.pt"

    # Use pre-warmed model if ready; fall back to cold load (60s timeout)
    _model_ready.wait(timeout=60)
    with _model_lock:
        if _cached_yolo_model is not None:
            model = _cached_yolo_model
        else:
            model = YOLO(str(model_path))

    scan_speed = settings.get("scan_speed", "thorough")
    if scan_speed in ("balanced", "fast"):
        try:
            if _run_sampled_yolo(model, source_path, source_info, settings,
                                 cancel_event, on_progress, on_event,
                                 job_dir, scan_speed, conf_thresh, score_thresh,
                                 padding_s, min_event_s, min_gap_s,
                                 recording_start, _log):
                return
        except frame_source.FrameSourceError as exc:
            _log(f"[FASTSCAN] sampled pipeline failed mid-run: {exc}")
        _log("[FASTSCAN] falling back to the legacy full-decode scan")

    import cv2
    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {source_path}")

    fps         = source_info.get("fps") or cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1
    heatmap_accum = np.zeros((src_h, src_w), dtype=np.float32)

    events: list[dict] = []
    active_start: Optional[float] = None
    active_label: str = ""
    active_peak: float = 0.0
    last_event_end: float = 0.0
    event_index: int = 0

    frame_idx = 0
    _last_progress_at = _time_module.monotonic()

    try:
        while True:
            if cancel_event.is_set():
                break

            ret, frame = cap.read()
            if not ret:
                break

            t_s = frame_idx / fps
            frame_idx += 1

            # Time-based dual progress trigger: fire if BATCH_SIZE frames OR >2s elapsed
            now = _time_module.monotonic()
            if frame_idx % BATCH_SIZE == 0 or now - _last_progress_at >= 2.0:
                on_progress(min(0.99, frame_idx / total_frames))
                _last_progress_at = now

            # Frame skip: skip inference on non-sampled frames
            if frame_idx % YOLO_FRAME_SKIP != 0:
                continue

            # Run inference (returns Results object)
            results = model(frame, conf=conf_thresh, verbose=False,
                            device=ai_device.get_ai_device())
            detections = results[0].boxes if results else None

            # Score = max confidence across relevant classes
            score = 0.0
            best_label = ""
            if detections is not None and len(detections):
                for box in detections:
                    cls_id = int(box.cls[0])
                    conf   = float(box.conf[0])
                    label  = _LABEL_MAP.get(cls_id, "Object")
                    if conf > score:
                        score      = conf
                        best_label = label
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(heatmap_accum, (x1, y1), (x2, y2), color=conf, thickness=-1)

            motion_detected = score >= score_thresh

            if motion_detected:
                if active_start is None:
                    # Gap check
                    if t_s - last_event_end >= min_gap_s or last_event_end == 0.0:
                        active_start = max(0.0, t_s - padding_s)
                        active_label = best_label
                        active_peak  = score
                else:
                    if score > active_peak:
                        active_peak  = score
                        active_label = best_label
            else:
                if active_start is not None:
                    end_s = t_s + padding_s
                    dur   = end_s - active_start
                    if dur >= min_event_s:
                        _emit_event(
                            events, on_event,
                            active_start, end_s,
                            active_peak, active_label,
                            recording_start,
                            event_index,
                        )
                        event_index += 1
                        last_event_end = end_s
                    active_start = None
                    active_peak  = 0.0
                    active_label = ""

        # Close any open event at end of video
        if active_start is not None:
            end_s = frame_idx / fps
            dur   = end_s - active_start
            if dur >= min_event_s:
                _emit_event(
                    events, on_event,
                    active_start, end_s,
                    active_peak, active_label,
                    recording_start,
                    event_index,
                )
                event_index += 1
    finally:
        cap.release()

    from app.core.detection_engine import _write_heatmap
    import cv2 as _cv2
    _write_heatmap(heatmap_accum, source_info, job_dir)
    # After a complete run, always ensure a heatmap file exists so the UI and tests
    # have a valid file to display even when YOLO found no detectable objects.
    _heatmap_path = job_dir / "heatmap.png"
    if not _heatmap_path.exists():
        _h = int(source_info.get("height") or src_h)
        _w = int(source_info.get("width") or src_w)
        _cv2.imwrite(str(_heatmap_path), np.zeros((_h, _w, 3), dtype=np.uint8))

    on_progress(1.0)


def _run_sampled_yolo(
    model,
    source_path: str,
    source_info: dict,
    settings: dict,
    cancel_event: threading.Event,
    on_progress: Callable[[float], None],
    on_event: Callable[[dict], None],
    job_dir: Path,
    scan_speed: str,
    conf_thresh: float,
    score_thresh: float,
    padding_s: float,
    min_event_s: float,
    min_gap_s: float,
    recording_start,
    _log: Callable[[str], None],
) -> bool:
    """
    Fast Scan for YOLO mode: 640×360 sampled frames from the FFmpeg pipe,
    inference on every sampled frame (YOLO_FRAME_SKIP applies only to the
    legacy loop). Events buffered until completion so a mid-run pipe failure
    discards partial results before the legacy fallback (no duplicates).
    Returns True when the run completed (or was cancelled); False → fallback.
    """
    source_fps        = float(source_info.get("fps") or 25.0)
    source_duration_s = float(source_info.get("duration_s") or 0.0)
    sample_fps = frame_source.sample_fps_for(scan_speed, source_fps)

    expected_total = max(source_duration_s * sample_fps, 1.0)
    progress_every = max(1, int(sample_fps * 2))  # ~every 2 s of video

    heatmap_accum = np.zeros((SAMPLED_H, SAMPLED_W), dtype=np.float32)
    pending: list[dict] = []
    active_start = None
    active_label = ""
    active_peak = 0.0
    last_event_end = 0.0
    event_index = 0
    frames_done = 0
    current_pts = 0.0
    _last_progress_at = _time_module.monotonic()

    import cv2

    def _close(end_s: float) -> None:
        nonlocal event_index, last_event_end
        if end_s - active_start >= min_event_s:
            from app.utils.time_utils import seconds_to_clock
            pending.append({
                "event_index":       event_index,
                "start_s":           round(active_start, 3),
                "end_s":             round(end_s, 3),
                "peak_motion_score": round(active_peak, 4),
                "zone_label":        active_label,
                "included":          True,
                "start_clock":       seconds_to_clock(active_start, recording_start) if recording_start else None,
                "end_clock":         seconds_to_clock(end_s, recording_start) if recording_start else None,
            })
            event_index += 1
            last_event_end = end_s

    stream = frame_source.open_frames(source_path, source_info, sample_fps,
                                      SAMPLED_W, SAMPLED_H, _log)
    with stream:
        for frame, pts in stream:
            if cancel_event.is_set():
                break
            current_pts = pts
            frames_done += 1

            results = model(frame, conf=conf_thresh, verbose=False,
                            device=ai_device.get_ai_device())
            detections = results[0].boxes if results else None

            score = 0.0
            best_label = ""
            if detections is not None and len(detections):
                for box in detections:
                    cls_id = int(box.cls[0])
                    conf   = float(box.conf[0])
                    label  = _LABEL_MAP.get(cls_id, "Object")
                    if conf > score:
                        score      = conf
                        best_label = label
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cv2.rectangle(heatmap_accum, (x1, y1), (x2, y2),
                                  color=conf, thickness=-1)

            if score >= score_thresh:
                if active_start is None:
                    if pts - last_event_end >= min_gap_s or last_event_end == 0.0:
                        active_start = max(0.0, pts - padding_s)
                        active_label = best_label
                        active_peak  = score
                else:
                    if score > active_peak:
                        active_peak  = score
                        active_label = best_label
            else:
                if active_start is not None:
                    _close(pts + padding_s)
                    active_start = None
                    active_peak  = 0.0
                    active_label = ""

            now = _time_module.monotonic()
            if frames_done % progress_every == 0 or now - _last_progress_at >= 2.0:
                on_progress(min(0.99, frames_done / expected_total))
                _last_progress_at = now

    def _finish() -> None:
        from app.core.detection_engine import _write_heatmap
        for ev in pending:
            on_event(ev)
        _write_heatmap(heatmap_accum, source_info, job_dir)
        heatmap_path = job_dir / "heatmap.png"
        if not heatmap_path.exists():
            h = int(source_info.get("height") or SAMPLED_H)
            w = int(source_info.get("width") or SAMPLED_W)
            cv2.imwrite(str(heatmap_path), np.zeros((h, w, 3), dtype=np.uint8))

    if cancel_event.is_set():
        _finish()
        return True

    if frames_done == 0:
        _log("[FASTSCAN] pipe delivered zero frames")
        return False

    rc = stream.returncode
    delivered_s = frames_done / sample_fps
    if rc not in (0, None) and source_duration_s > 0 \
            and delivered_s < 0.95 * source_duration_s:
        _log(f"[FASTSCAN] decoder exited {rc} after {delivered_s:.1f}s of "
             f"{source_duration_s:.1f}s ({stream.stderr_tail or 'no stderr'})")
        return False

    if active_start is not None:
        _close(frames_done / sample_fps)

    _finish()
    on_progress(1.0)
    _log(f"[FASTSCAN] complete — {frames_done} sampled frames "
         f"({stream.decoder}), {len(pending)} event(s)")
    return True


def _emit_event(
    events: list,
    on_event: Callable,
    start_s: float,
    end_s: float,
    peak_score: float,
    zone_label: str,
    recording_start: Optional[str],
    event_index: int,
) -> None:
    from app.utils.time_utils import seconds_to_clock

    start_clock = seconds_to_clock(start_s, recording_start) if recording_start else None
    end_clock   = seconds_to_clock(end_s,   recording_start) if recording_start else None

    ev = {
        "event_index":      event_index,
        "start_s":          round(start_s, 3),
        "end_s":            round(end_s, 3),
        "peak_motion_score": round(peak_score, 4),
        "zone_label":       zone_label,
        "included":         True,
        "start_clock":      start_clock,
        "end_clock":        end_clock,
    }
    events.append(ev)
    on_event(ev)
