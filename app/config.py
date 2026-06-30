"""
Runtime constants — auto-tuned to available RAM so the same codebase
runs acceptably on both a Windows PC (≥8 GB) and a Raspberry Pi 5 (2–4 GB).
"""
import os
import platform
from pathlib import Path

import psutil

# ── Detection resolution (scales with available RAM) ─────────────────────────
_total_gb: float = psutil.virtual_memory().total / 1e9
if _total_gb >= 8:
    DETECT_WIDTH: int = 640
    DETECT_HEIGHT: int = 360
elif _total_gb >= 4:
    DETECT_WIDTH = 480
    DETECT_HEIGHT = 270
elif _total_gb >= 2:
    # Raspberry Pi 5 (2 GB) — keep detection frame small to leave RAM for Qt
    DETECT_WIDTH = 320
    DETECT_HEIGHT = 180
else:
    # Very constrained (Pi Zero / 1 GB devices)
    DETECT_WIDTH = 160
    DETECT_HEIGHT = 90

# ── Platform flags ────────────────────────────────────────────────────────────
IS_PI: bool = platform.machine().startswith(("aarch64", "armv")) and platform.system() == "Linux"

# ── Server ────────────────────────────────────────────────────────────────────
BACKEND_PORT: int = 5151
BACKEND_HOST: str = "127.0.0.1"

# ── Paths (all under a hidden app-data folder in the user's home) ─────────────
_APP_DIR: Path = Path.home() / ".cctv_processor"
JOBS_DIR: Path = _APP_DIR / "jobs"
PREVIEW_DIR: Path = _APP_DIR / "previews"
MODEL_DIR: Path = _APP_DIR / "models"
PRESETS_FILE: Path = _APP_DIR / "presets.json"

# ── FFmpeg / OpenCV ───────────────────────────────────────────────────────────
FFMPEG_THREADS: int = max(1, (os.cpu_count() or 2) - 1)
STREAM_COPY_SAFE: frozenset = frozenset({"h264", "hevc", "mpeg2video", "mpeg4"})
MP4_AUDIO_SAFE: frozenset = frozenset({"aac", "mp3", "ac3", "opus"})

# ── Detection loop ────────────────────────────────────────────────────────────
BATCH_SIZE: int = 100 if IS_PI else 500   # frames between progress callbacks (Pi: responsive RAM-guard checks)
LOG_RING_SIZE: int = 2000                  # max log lines kept in LogBuffer per job
YOLO_FRAME_SKIP: int = 6 if IS_PI else 3  # process 1 in N frames for YOLO (Pi slower CPU)

# ── AI feature gate ───────────────────────────────────────────────────────────
AI_FEATURES_ENABLED: bool = _total_gb >= 5.0  # Florence-2 needs ~3GB weights + OS/Qt overhead

# ── RAM guard (detection loop) ────────────────────────────────────────────────
RAM_GUARD_PERCENT: int = 85    # pause detection if system RAM usage exceeds this %
