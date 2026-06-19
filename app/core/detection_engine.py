"""
8-step MOG2 detection pipeline — PC version.

Runs entirely in a worker thread. No database, no crash-resume, no RAM guard.
Progress and events are surfaced via callbacks (on_progress, on_event).

--- Frame source ---
cv2.VideoCapture with an automatic normalization fallback for malformed videos
(e.g. Android recordings with broken MP4 edit lists that cause early EOF).
"""
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

import app.config as config
from app.utils.ffmpeg_path import get_ffmpeg
from app.utils.time_utils import seconds_to_clock

# ── MOG2 tuning ───────────────────────────────────────────────────────────────
SENSITIVITY_HISTORY = {"low": 700, "medium": 500, "high": 200}
SENSITIVITY_VAR_THR  = {"low": 32,  "medium": 16,  "high": 8}
MOTION_THRESHOLD     = {"low": 0.01, "medium": 0.002, "high": 0.0005}

INITIAL_WARMUP = 30    # frames to feed MOG2 before event detection
PROBE_FRAMES   = 60    # frames to test-read for malformation check
PROBE_OK_MIN   = 48    # minimum successes (80 %) before normalizing
LOG_INTERVAL_S = 10.0  # minimum video-time gap between periodic log lines


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_zone_mask(zones: list) -> Optional[np.ndarray]:
    """Pre-render polygon mask from normalised [0–1] coordinates."""
    W, H = config.DETECT_WIDTH, config.DETECT_HEIGHT
    if not zones:
        return None
    mask = np.zeros((H, W), dtype=np.uint8)
    for zone in zones:
        pts = np.array(
            [[int(x * W), int(y * H)] for x, y in zone.get("points", [])],
            dtype=np.int32,
        )
        cv2.fillPoly(mask, [pts], 255)
    return mask


# ── Normalization fallback ────────────────────────────────────────────────────

def _normalize_via_vc(
    source_path: str,
    normalized_path: str,
    source_fps: float,
    source_w: int,
    source_h: int,
    logger: Callable,
) -> bool:
    """
    Re-encode source via VideoCapture→FFmpeg stdin pipe to produce a well-formed
    H.264 MP4.  Bypasses the libav INPUT path that causes early EOF on malformed
    files, while producing a clean OUTPUT that any VideoCapture can read.
    Returns True if > 100 frames were written successfully.
    """
    logger(
        f"[NORMALIZE] VideoCapture → FFmpeg pipe re-encode "
        f"({Path(source_path).name}, {source_w}×{source_h} @ {source_fps:.2f}fps)…"
    )

    cmd = [
        get_ffmpeg(), "-hide_banner", "-loglevel", "warning",
        "-y",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{source_w}x{source_h}",
        "-r", str(source_fps),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-an",
        normalized_path,
    ]

    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        logger("[NORMALIZE] Cannot open source with VideoCapture — aborting")
        return False

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        cap.release()
        logger("[NORMALIZE] ffmpeg not found — cannot normalize")
        return False

    frame_count = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            try:
                proc.stdin.write(frame.tobytes())
            except BrokenPipeError:
                logger("[NORMALIZE] FFmpeg stdin broken — aborting")
                break
            frame_count += 1
            if frame_count % 600 == 0:
                logger(f"[NORMALIZE] Extracting frames… {frame_count} so far")
    finally:
        cap.release()
        try:
            proc.stdin.close()
        except OSError:
            pass
        _, stderr_bytes = proc.communicate(timeout=60)
        rc = proc.returncode

    if rc != 0:
        snippet = stderr_bytes.decode("utf-8", errors="replace")[-600:]
        logger(f"[NORMALIZE] FFmpeg exited {rc}: {snippet}")
        return False

    if frame_count < 100:
        logger(f"[NORMALIZE] Only {frame_count} frames — source may be too short")
        return False

    try:
        size_mb = Path(normalized_path).stat().st_size / 1_048_576
    except OSError:
        size_mb = 0.0
    logger(f"[NORMALIZE] Complete — {frame_count} frames, {size_mb:.1f} MB → {Path(normalized_path).name}")
    return True


def _open_video(
    source_path: str,
    job_dir: Path,
    fallback_fps: float,
    logger: Callable,
) -> tuple:
    """
    Open VideoCapture for detection, probing first and normalizing if needed.
    Returns (cap, total_frames, actual_fps).
    """
    normalized_path = str(job_dir / "normalized.mp4")
    norm_file = job_dir / "normalized.mp4"

    # Reuse cached normalization if it exists from a previous run in this session
    if norm_file.exists() and norm_file.stat().st_size > 10_000:
        logger("[NORMALIZE] Cached normalized video found — using it")
        cap = cv2.VideoCapture(str(norm_file))
        if cap.isOpened():
            tf  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
            fps = cap.get(cv2.CAP_PROP_FPS) or fallback_fps
            return cap, tf, fps
        cap.release()

    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise RuntimeError(
            f"VideoCapture cannot open: {source_path}. "
            f"File may be corrupt or use an unsupported codec."
        )

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    actual_fps   = cap.get(cv2.CAP_PROP_FPS) or fallback_fps
    src_w        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h        = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if total_frames > PROBE_FRAMES * 2:
        probe_ok = 0
        for _ in range(PROBE_FRAMES):
            ret, _ = cap.read()
            if ret:
                probe_ok += 1
            else:
                break
        cap.release()

        if probe_ok < PROBE_OK_MIN:
            logger(
                f"[PROBE] VideoCapture read {probe_ok}/{PROBE_FRAMES} probe frames "
                f"— video is malformed on this platform. Normalizing…"
            )
            ok = _normalize_via_vc(source_path, normalized_path, actual_fps, src_w, src_h, logger)
            if ok and norm_file.exists():
                cap = cv2.VideoCapture(normalized_path)
                if cap.isOpened():
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or total_frames
                    actual_fps   = cap.get(cv2.CAP_PROP_FPS) or actual_fps
                    logger(f"[NORMALIZE] Ready — {total_frames} frames, {actual_fps:.2f}fps")
                    return cap, total_frames, actual_fps
                cap.release()
                logger("[NORMALIZE] Cannot open normalized file — falling back to original")

            cap = cv2.VideoCapture(source_path)
            if not cap.isOpened():
                raise RuntimeError(f"Cannot reopen original: {source_path}")
        else:
            logger(f"[PROBE] {probe_ok}/{PROBE_FRAMES} frames OK — VideoCapture is healthy")
            cap = cv2.VideoCapture(source_path)
            if not cap.isOpened():
                raise RuntimeError(f"Cannot reopen: {source_path}")

    return cap, total_frames, actual_fps


# ── Main detection entry point ────────────────────────────────────────────────

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
    Main MOG2 detection pipeline.

    Calls on_progress(0.0–1.0) periodically and on_event(ev_dict) for each
    confirmed motion event.  Runs to completion or until cancel_event is set.
    """
    W = config.DETECT_WIDTH
    H = config.DETECT_HEIGHT

    job_dir = Path(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)

    sensitivity     = settings.get("sensitivity", "medium")
    frame_skip      = int(settings.get("frame_skip", 0))
    padding_s       = float(settings.get("padding_s", 2))
    min_gap_s       = float(settings.get("min_gap_s", 2))
    min_event_s     = float(settings.get("min_event_s", 2))
    zones           = settings.get("zones", [])
    recording_start = settings.get("recording_start")

    source_fps        = float(source_info.get("fps") or 25.0)
    source_duration_s = float(source_info.get("duration_s") or 0.0)

    def _log(msg: str) -> None:
        # Local logger — caller can hook via on_event/on_progress; plain print for now
        pass  # log lines are surfaced via the SSE log buffer in the API layer

    # ── Open video ────────────────────────────────────────────────────────────
    cap, total_frames, actual_fps = _open_video(source_path, job_dir, source_fps, _log)

    # ── MOG2 initialisation ───────────────────────────────────────────────────
    history       = SENSITIVITY_HISTORY[sensitivity]
    var_threshold = SENSITIVITY_VAR_THR[sensitivity]
    mog2 = cv2.createBackgroundSubtractorMOG2(
        history=history, varThreshold=var_threshold, detectShadows=False
    )
    motion_ratio_threshold = MOTION_THRESHOLD[sensitivity]
    clahe  = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    zone_mask = _build_zone_mask(zones)

    frame_idx   = 0
    frames_done = 0

    # ── Initial warmup ────────────────────────────────────────────────────────
    for _ in range(INITIAL_WARMUP):
        ret, frame = cap.read()
        if not ret:
            break
        small = cv2.resize(frame, (W, H))
        gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        if sensitivity == "high":
            gray = clahe.apply(gray)
        mog2.apply(gray)
        frame_idx += 1

    # ── Segment state machine ─────────────────────────────────────────────────
    in_event          = False
    event_start       = 0.0
    event_start_clock = ""
    silence_start: Optional[float] = None   # PC-fix: None sentinel, not 0.0
    peak_score        = 0.0
    event_index       = 0

    current_pts    = 0.0
    first_frame_ok = False
    batch_max_ratio = 0.0
    last_log_pts    = -LOG_INTERVAL_S

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if cancel_event.is_set():
                break

            current_pts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

            if frame_skip > 0 and frame_idx % (frame_skip + 1) != 0:
                frame_idx += 1
                continue

            # ── Preprocess ───────────────────────────────────────────────────
            small = cv2.resize(frame, (W, H))
            gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            if sensitivity == "high":
                gray = clahe.apply(gray)

            # ── MOG2 ─────────────────────────────────────────────────────────
            fg_mask = mog2.apply(gray)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN,  kernel)
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

            if zone_mask is not None:
                fg_mask = cv2.bitwise_and(fg_mask, zone_mask)

            motion_ratio = cv2.countNonZero(fg_mask) / (W * H)
            is_motion    = motion_ratio >= motion_ratio_threshold
            if motion_ratio > batch_max_ratio:
                batch_max_ratio = motion_ratio

            # ── State machine ─────────────────────────────────────────────────
            if not in_event and is_motion:
                in_event          = True
                event_start       = max(0.0, current_pts - padding_s)
                event_start_clock = seconds_to_clock(event_start, recording_start)
                peak_score        = motion_ratio
                silence_start     = None

            elif in_event:
                if is_motion:
                    peak_score    = max(peak_score, motion_ratio)
                    silence_start = None
                else:
                    if silence_start is None:
                        silence_start = current_pts
                    if current_pts - silence_start >= min_gap_s:
                        event_end = silence_start + padding_s
                        duration  = event_end - event_start
                        if duration >= min_event_s:
                            ev = {
                                "event_index":       event_index,
                                "start_s":           round(event_start, 3),
                                "end_s":             round(event_end, 3),
                                "start_clock":       event_start_clock,
                                "end_clock":         seconds_to_clock(event_end, recording_start),
                                "peak_motion_score": round(peak_score, 4),
                                "zone_label":        zones[0]["label"] if zones else None,
                                "included":          True,
                            }
                            on_event(ev)
                            event_index += 1
                        in_event      = False
                        silence_start = None
                        peak_score    = 0.0

            frame_idx   += 1
            frames_done += 1

            # ── Progress callback every BATCH_SIZE frames ─────────────────────
            if frame_idx % config.BATCH_SIZE == 0:
                progress = min(frame_idx / max(total_frames, 1), 0.99)
                on_progress(progress)

                if cancel_event.is_set():
                    break

        # ── Zero-frames guard ─────────────────────────────────────────────────
        if frames_done == 0 and not cancel_event.is_set():
            raise RuntimeError(
                f"VideoCapture produced 0 frames from: {source_path}. "
                f"File may be corrupt, truncated, or use an unsupported codec."
            )

        # ── Close any open event at end of video ──────────────────────────────
        if in_event and not cancel_event.is_set():
            event_end = current_pts + padding_s
            if event_end - event_start >= min_event_s:
                ev = {
                    "event_index":       event_index,
                    "start_s":           round(event_start, 3),
                    "end_s":             round(event_end, 3),
                    "start_clock":       event_start_clock,
                    "end_clock":         seconds_to_clock(event_end, recording_start),
                    "peak_motion_score": round(peak_score, 4),
                    "zone_label":        zones[0]["label"] if zones else None,
                    "included":          True,
                }
                on_event(ev)

        if not cancel_event.is_set():
            on_progress(1.0)

    finally:
        cap.release()
