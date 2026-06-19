"""
PC-adapted constants.  All values chosen for desktop hardware
(multi-core CPU, ≥4 GB RAM) rather than Raspberry Pi constraints.
"""
import os
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
else:
    DETECT_WIDTH = 320
    DETECT_HEIGHT = 180

# ── Server ────────────────────────────────────────────────────────────────────
BACKEND_PORT: int = 5151
BACKEND_HOST: str = "127.0.0.1"

# ── Paths (all under a hidden app-data folder in the user's home) ─────────────
_APP_DIR: Path = Path.home() / ".cctv_processor"
JOBS_DIR: Path = _APP_DIR / "jobs"
PREVIEW_DIR: Path = _APP_DIR / "previews"
MODEL_DIR: Path = _APP_DIR / "models"

# ── FFmpeg / OpenCV ───────────────────────────────────────────────────────────
FFMPEG_THREADS: int = max(1, (os.cpu_count() or 2) - 1)
STREAM_COPY_SAFE: frozenset = frozenset({"h264", "hevc", "mpeg2video", "mpeg4"})
MP4_AUDIO_SAFE: frozenset = frozenset({"aac", "mp3", "ac3", "opus"})

# ── Detection loop ────────────────────────────────────────────────────────────
BATCH_SIZE: int = 500          # frames between progress callbacks
LOG_RING_SIZE: int = 2000      # max log lines kept in LogBuffer per job

# ── RAM guard (detection loop) ────────────────────────────────────────────────
RAM_GUARD_PERCENT: int = 85    # pause detection if system RAM usage exceeds this %
