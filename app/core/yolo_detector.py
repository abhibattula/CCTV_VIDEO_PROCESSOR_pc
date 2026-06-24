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

from app.config import MODEL_DIR, BATCH_SIZE

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


def run(
    source_path: str,
    source_info: dict,
    settings: dict,
    cancel_event: threading.Event,
    on_progress: Callable[[float], None],
    on_event: Callable[[dict], None],
    job_dir: Path,
) -> None:
    """
    Run YOLO object detection on source_path.

    Emits events via on_event(dict) and progress via on_progress(float 0-1).
    Raises ImportError if ultralytics is not installed.
    """
    _require_ultralytics()

    from ultralytics import YOLO  # type: ignore

    sensitivity = settings.get("sensitivity", "medium")
    padding_s   = float(settings.get("padding_s", 1.0))
    min_event_s = float(settings.get("min_event_s", 1.0))
    min_gap_s   = float(settings.get("min_gap_s", 1.0))
    recording_start = settings.get("recording_start")

    conf_thresh  = _CONF.get(sensitivity, 0.4)
    score_thresh = _SCORE_THRESH.get(sensitivity, 0.3)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "yolov8n.pt"
    model = YOLO(str(model_path))  # auto-downloads if absent

    import cv2
    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {source_path}")

    fps         = source_info.get("fps") or cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1

    events: list[dict] = []
    active_start: Optional[float] = None
    active_label: str = ""
    active_peak: float = 0.0
    last_event_end: float = 0.0
    event_index: int = 0

    frame_idx = 0

    try:
        while True:
            if cancel_event.is_set():
                break

            ret, frame = cap.read()
            if not ret:
                break

            t_s = frame_idx / fps
            frame_idx += 1

            # Progress
            if frame_idx % BATCH_SIZE == 0:
                on_progress(min(0.99, frame_idx / total_frames))

            # Run inference (returns Results object)
            results = model(frame, conf=conf_thresh, verbose=False)
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

    on_progress(1.0)


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
