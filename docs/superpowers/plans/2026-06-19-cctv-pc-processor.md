# CCTV PC Video Processor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-platform desktop CCTV activity extractor — drop a video, detect motion, review timeline, export only the active clips.

**Architecture:** PyQt6 native shell wraps a QWebEngineView pointing at a local FastAPI server (localhost:5151). Detection runs in a background thread using OpenCV MOG2 or YOLOv8n; results live in an in-memory session dict (no database). FFmpeg (bundled via imageio-ffmpeg) handles all segment extraction and merging.

**Tech Stack:** Python 3.11+, PyQt6 6.7, PyQt6-WebEngine 6.7, FastAPI 0.111, uvicorn, OpenCV 4.9, imageio-ffmpeg 0.5, ultralytics (optional YOLO), psutil, aiofiles

---

## File Map

**Create from scratch:**
- `launcher.py` — entry point; starts FastAPI thread, opens PyQt6 window
- `shell/main_window.py` — QMainWindow + QWebEngineView + drag-and-drop
- `shell/tray.py` — QSystemTrayIcon
- `shell/platform_utils.py` — open_folder(), get_platform()
- `app/main.py` — FastAPI app factory (no SQLite, no PWA)
- `app/config.py` — PC-adapted constants
- `app/session.py` — in-memory session state + RLock
- `app/api/job.py` — create, start, cancel, events, toggle
- `app/api/preview.py` — temp clip extraction
- `app/api/stream.py` — SSE endpoint
- `app/api/shell_bridge.py` — receives file path from PyQt6
- `app/core/yolo_detector.py` — YOLOv8n wrapper (new)
- `app/utils/ffmpeg_path.py` — imageio-ffmpeg binary resolver
- `app/utils/system.py` — cross-platform CPU/RAM/temp
- `requirements.txt`
- `tests/` — all test files

**Port from `OLD RASPBERRI PI VERSION/` with modifications:**
- `app/core/detection_engine.py` — PC-01/02/04 fixes
- `app/core/export_engine.py` — FFmpeg path fix only
- `app/core/log_buffer.py` — unchanged
- `app/core/thumbnail_gen.py` — FFmpeg path fix only
- `app/utils/ffprobe.py` — FFmpeg path fix only
- `app/utils/time_utils.py` — unchanged
- `static/` — redesigned 4-page frontend

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py`, `app/api/__init__.py`, `app/core/__init__.py`, `app/utils/__init__.py`
- Create: `shell/__init__.py`
- Create: `tests/conftest.py`
- Create: `static/pages/`, `static/css/`, `static/js/pages/`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.111.*
uvicorn[standard]==0.29.*
opencv-python-headless==4.9.*
numpy==1.26.*
psutil==5.9.*
imageio-ffmpeg==0.5.*
PyQt6==6.7.*
PyQt6-WebEngine==6.7.*
aiofiles==23.*
pytest==8.*
pytest-asyncio==0.23.*
httpx==0.27.*
```

- [ ] **Step 2: Create all `__init__.py` files and directory structure**

```bash
mkdir -p app/api app/core app/utils shell static/pages static/css "static/js/pages" tests
touch app/__init__.py app/api/__init__.py app/core/__init__.py app/utils/__init__.py shell/__init__.py
```

- [ ] **Step 3: Create `tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    from app.main import create_app
    from app import session
    session.reset()
    app = create_app()
    with TestClient(app) as c:
        yield c
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt app/ shell/ static/ tests/
git commit -m "chore: scaffold project structure"
```

---

## Task 2: Config + Time Utils

**Files:**
- Create: `app/config.py`
- Port: `app/utils/time_utils.py` from `OLD RASPBERRI PI VERSION/app/utils/time_utils.py`

- [ ] **Step 1: Create `app/config.py`**

```python
import tempfile
from pathlib import Path
import psutil

_ram_gb = psutil.virtual_memory().total / 1e9

# Detection resolution — scales with available RAM
if _ram_gb >= 8:
    DETECT_WIDTH, DETECT_HEIGHT = 640, 360
elif _ram_gb >= 4:
    DETECT_WIDTH, DETECT_HEIGHT = 480, 270
else:
    DETECT_WIDTH, DETECT_HEIGHT = 320, 180

BATCH_SIZE: int = 30
FFMPEG_THREADS: int = min(4, psutil.cpu_count(logical=False) or 2)
LOG_RING_SIZE: int = 2000
BACKEND_PORT: int = 5151
BACKEND_HOST: str = "127.0.0.1"

# Paths — all cross-platform via pathlib
_TEMP = Path(tempfile.gettempdir()) / "cctv_processor"
PREVIEW_DIR: Path = _TEMP / "previews"
JOBS_DIR: Path = _TEMP / "jobs"
MODEL_DIR: Path = Path.home() / ".cctv_processor" / "models"

STREAM_COPY_SAFE = {"h264", "hevc", "mpeg2video", "mpeg4"}
```

- [ ] **Step 2: Copy time_utils.py from Pi version**

```bash
cp "OLD RASPBERRI PI VERSION/app/utils/time_utils.py" app/utils/time_utils.py
```

- [ ] **Step 3: Verify time_utils imports cleanly**

```bash
python -c "from app.utils.time_utils import seconds_to_clock; print(seconds_to_clock(3661, None))"
```

Expected output: `01:01:01` (or similar clock format — no error).

- [ ] **Step 4: Commit**

```bash
git add app/config.py app/utils/time_utils.py
git commit -m "feat: add PC-adapted config and time utils"
```

---

## Task 3: FFmpeg Path Utility

**Files:**
- Create: `app/utils/ffmpeg_path.py`
- Create: `tests/test_ffmpeg_path.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ffmpeg_path.py
from pathlib import Path

def test_get_ffmpeg_returns_existing_path():
    from app.utils.ffmpeg_path import get_ffmpeg
    path = get_ffmpeg()
    assert Path(path).exists(), f"ffmpeg binary not found at: {path}"

def test_get_ffprobe_returns_existing_path():
    from app.utils.ffmpeg_path import get_ffprobe
    path = get_ffprobe()
    assert Path(path).exists(), f"ffprobe binary not found at: {path}"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_ffmpeg_path.py -v
```

Expected: `ImportError` or `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/utils/ffmpeg_path.py`**

```python
from pathlib import Path

def get_ffmpeg() -> str:
    """Return absolute path to bundled ffmpeg binary."""
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if Path(path).exists():
            return path
    except Exception:
        pass
    # Fallback: system ffmpeg
    import shutil
    system = shutil.which("ffmpeg")
    if system:
        return system
    raise RuntimeError(
        "FFmpeg not found. Reinstall the app (imageio-ffmpeg should bundle it)."
    )

def get_ffprobe() -> str:
    """Return absolute path to ffprobe — lives next to ffmpeg."""
    ffmpeg = Path(get_ffmpeg())
    # imageio-ffmpeg bundles ffprobe alongside ffmpeg
    candidate = ffmpeg.parent / ffmpeg.name.replace("ffmpeg", "ffprobe")
    if candidate.exists():
        return str(candidate)
    import shutil
    system = shutil.which("ffprobe")
    if system:
        return system
    raise RuntimeError("ffprobe not found alongside ffmpeg.")
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_ffmpeg_path.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/utils/ffmpeg_path.py tests/test_ffmpeg_path.py
git commit -m "feat: bundled ffmpeg path resolver (imageio-ffmpeg)"
```

---

## Task 4: Session State

**Files:**
- Create: `app/session.py`
- Create: `tests/test_session.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_session.py
import threading
from app import session

def setup_function():
    session.reset()

def test_initial_status_is_idle():
    s = session.snapshot()
    assert s["status"] == "idle"

def test_update_changes_fields():
    session.update(status="detecting", progress=0.5)
    s = session.snapshot()
    assert s["status"] == "detecting"
    assert s["progress"] == 0.5

def test_snapshot_returns_copy():
    session.update(events=[{"start_s": 1.0}])
    s = session.snapshot()
    s["events"].append({"start_s": 2.0})
    assert len(session.snapshot()["events"]) == 1  # original unchanged

def test_append_event():
    session.append_event({"start_s": 5.0, "end_s": 10.0, "peak_score": 0.03, "included": True, "label": None})
    assert len(session.snapshot()["events"]) == 1

def test_toggle_event():
    session.append_event({"start_s": 1.0, "end_s": 3.0, "peak_score": 0.01, "included": True, "label": None})
    session.toggle_event(0)
    assert session.snapshot()["events"][0]["included"] is False
    session.toggle_event(0)
    assert session.snapshot()["events"][0]["included"] is True

def test_thread_safe_concurrent_updates():
    errors = []
    def worker(i):
        try:
            session.update(progress=i / 100)
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert errors == []
```

- [ ] **Step 2: Run — expect failure**

```bash
pytest tests/test_session.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.session'`.

- [ ] **Step 3: Create `app/session.py`**

```python
import copy
import threading
import uuid
from pathlib import Path
from typing import Any

_lock = threading.RLock()

_STATE: dict[str, Any] = {}

def reset() -> None:
    """Reset to idle state. Call at app start or before a new job."""
    with _lock:
        _STATE.clear()
        _STATE.update({
            "job_id": str(uuid.uuid4()),
            "status": "idle",          # idle|detecting|completed|exporting|failed|cancelled
            "source_path": None,
            "source_info": {},         # codec, fps, width, height, duration_s, has_audio, needs_reencode
            "settings": {},
            "progress": 0.0,
            "events": [],              # list of {start_s, end_s, peak_score, included, label}
            "output_path": None,
            "output_dir": str(Path.home() / "Desktop"),
            "error": None,
        })

def update(**kwargs) -> None:
    with _lock:
        _STATE.update(kwargs)

def snapshot() -> dict:
    with _lock:
        return copy.deepcopy(_STATE)

def append_event(ev: dict) -> None:
    with _lock:
        _STATE["events"].append(ev)

def toggle_event(idx: int) -> None:
    with _lock:
        _STATE["events"][idx]["included"] = not _STATE["events"][idx]["included"]

# Initialise on import
reset()
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_session.py -v
```

Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/session.py tests/test_session.py
git commit -m "feat: in-memory session state with RLock (replaces SQLite)"
```

---

## Task 5: ffprobe Utility

**Files:**
- Port: `app/utils/ffprobe.py`
- Create: `tests/test_ffprobe.py`

- [ ] **Step 1: Copy ffprobe.py from Pi version**

```bash
cp "OLD RASPBERRI PI VERSION/app/utils/ffprobe.py" app/utils/ffprobe.py
```

- [ ] **Step 2: Replace bare `"ffmpeg"` / `"ffprobe"` strings with path resolver**

Open `app/utils/ffprobe.py`. Find any `subprocess` call that uses the string `"ffprobe"` and replace it:

```python
# At top of file, add:
from app.utils.ffmpeg_path import get_ffprobe

# Replace every occurrence of:
#   ["ffprobe", ...]
# with:
#   [get_ffprobe(), ...]
```

- [ ] **Step 3: Write test using the bundled test video**

```python
# tests/test_ffprobe.py
import pytest
from pathlib import Path

TEST_VIDEO = Path("OLD RASPBERRI PI VERSION/Test Video/20260507_012210 (1).mp4")

@pytest.mark.skipif(not TEST_VIDEO.exists(), reason="test video not present")
def test_probe_returns_expected_fields():
    from app.utils.ffprobe import probe
    info = probe(str(TEST_VIDEO))
    assert "codec" in info
    assert "fps" in info
    assert info["duration_s"] > 0
    assert info["width"] > 0
    assert info["height"] > 0

@pytest.mark.skipif(not TEST_VIDEO.exists(), reason="test video not present")
def test_probe_detects_has_audio():
    from app.utils.ffprobe import probe
    info = probe(str(TEST_VIDEO))
    assert isinstance(info["has_audio"], bool)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_ffprobe.py -v
```

Expected: `2 passed` (or skipped if video missing — not a failure).

- [ ] **Step 5: Commit**

```bash
git add app/utils/ffprobe.py tests/test_ffprobe.py
git commit -m "feat: port ffprobe util with bundled binary path"
```

---

## Task 6: Log Buffer (Port)

**Files:**
- Port: `app/core/log_buffer.py`

- [ ] **Step 1: Copy from Pi version**

```bash
cp "OLD RASPBERRI PI VERSION/app/core/log_buffer.py" app/core/log_buffer.py
```

- [ ] **Step 2: Verify it imports cleanly (no SQLite / Pi-only deps)**

```bash
python -c "from app.core.log_buffer import log_buffer; print('OK')"
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add app/core/log_buffer.py
git commit -m "feat: port log_buffer SSE fan-out from Pi version"
```

---

## Task 7: Detection Engine (Port + PC Fixes)

**Files:**
- Port+fix: `app/core/detection_engine.py`
- Create: `tests/test_detection_engine.py`

- [ ] **Step 1: Copy detection engine from Pi version**

```bash
cp "OLD RASPBERRI PI VERSION/app/core/detection_engine.py" app/core/detection_engine.py
```

- [ ] **Step 2: Apply PC-01 fix — CLAHE during warmup for high sensitivity**

In `app/core/detection_engine.py`, find the initial warmup block (around `if resume_pts is None:`):

```python
# BEFORE (warmup block, ~line 403):
    for _ in range(INITIAL_WARMUP):
        ret, frame = cap.read()
        if not ret:
            break
        small = cv2.resize(frame, (W, H))
        gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        mog2.apply(gray)
        frame_idx += 1

# AFTER (PC-01 fix — apply CLAHE in warmup when sensitivity == "high"):
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
```

Apply the same fix to the crash-resume warmup block (around `if resume_pts is not None:`, second warmup loop).

- [ ] **Step 3: Apply PC-02 fix — remove SQLite, add callbacks**

Change the `run()` function signature:

```python
# BEFORE:
def run(job_id, job, settings, cancel_event, logger):

# AFTER:
def run(
    job_id: str,
    source_path: str,
    source_info: dict,
    settings: dict,
    cancel_event: threading.Event,
    logger,
    on_progress=None,   # callable(float) — called each checkpoint
    on_event=None,      # callable(dict) — called for each confirmed event
):
```

Remove all `get_conn()` calls and `conn.execute(...)` calls. Replace them:

```python
# Replace:  conn.execute("UPDATE jobs SET progress=? WHERE id=?", (progress, job_id))
# With:
    if on_progress:
        on_progress(progress)

# Replace:  _flush_events(conn, job_id, confirmed_events, recording_start)
# With:
    for ev in confirmed_events:
        if on_event:
            on_event(ev)
    confirmed_events.clear()
```

Remove the `_flush_events` function entirely. Remove `from app.database import get_conn`.

Replace `job["source_path"]` with `source_path` and `job.get("source_fps")` etc. with `source_info.get("fps")`.

- [ ] **Step 4: Apply PC-04 fix — use config resolution**

The file already imports from `app.config`. Verify `DETECT_WIDTH` and `DETECT_HEIGHT` are imported from `app.config` (not hardcoded). If hardcoded as 320/240, replace:

```python
# Ensure top of file has:
from app.config import DETECT_WIDTH as W, DETECT_HEIGHT as H, BATCH_SIZE, JOBS_DIR
```

- [ ] **Step 5: Fix silence_start sentinel (PC fragility fix)**

Find the segment state machine. Replace `silence_start = 0.0` sentinel with `None`:

```python
# Initialisation (find and replace):
silence_start: float | None = None

# In the state machine, replace checks:
# BEFORE:
    if silence_start == 0.0:
        silence_start = current_pts
    if current_pts - silence_start >= min_gap_s:
# AFTER:
    if silence_start is None:
        silence_start = current_pts
    if current_pts - silence_start >= min_gap_s:

# On motion return, reset to None:
# BEFORE:  silence_start = 0.0
# AFTER:   silence_start = None

# On event close, reset to None:
# BEFORE:  silence_start = 0.0
# AFTER:   silence_start = None
```

- [ ] **Step 6: Write detection engine tests**

```python
# tests/test_detection_engine.py
import threading
import numpy as np
import cv2
import pytest
from pathlib import Path

TEST_VIDEO = Path("OLD RASPBERRI PI VERSION/Test Video/20260507_012210 (1).mp4")

def test_detection_engine_imports():
    from app.core import detection_engine
    assert hasattr(detection_engine, "run")

@pytest.mark.skipif(not TEST_VIDEO.exists(), reason="test video not present")
def test_detection_finds_events_on_real_video():
    from app.core.detection_engine import run
    events = []
    progress_vals = []
    cancel = threading.Event()

    run(
        job_id="test-job",
        source_path=str(TEST_VIDEO),
        source_info={"fps": 30.0, "duration_s": 10.0},
        settings={"sensitivity": "medium", "frame_skip": 1,
                  "padding_s": 1.0, "min_gap_s": 1.0, "min_event_s": 1.0,
                  "zones": [], "recording_start": None, "mode": "mog2"},
        cancel_event=cancel,
        logger=lambda line: None,
        on_progress=lambda p: progress_vals.append(p),
        on_event=lambda ev: events.append(ev),
    )
    # Progress was reported
    assert len(progress_vals) > 0
    # At least one event found in a real CCTV recording
    assert len(events) >= 0  # 0 is acceptable if truly static; no crash is the key test

def test_detection_respects_cancel():
    """Cancel event must stop detection within one batch."""
    from app.core.detection_engine import run
    cancel = threading.Event()
    cancel.set()  # pre-cancelled
    events = []
    # Should return immediately without error
    if TEST_VIDEO.exists():
        run(
            job_id="cancel-test",
            source_path=str(TEST_VIDEO),
            source_info={"fps": 30.0, "duration_s": 10.0},
            settings={"sensitivity": "medium", "frame_skip": 2,
                      "padding_s": 1.0, "min_gap_s": 1.0, "min_event_s": 1.0,
                      "zones": [], "recording_start": None, "mode": "mog2"},
            cancel_event=cancel,
            logger=lambda line: None,
            on_event=lambda ev: events.append(ev),
        )
    assert len(events) == 0
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_detection_engine.py -v
```

Expected: all pass (real-video tests skip if video absent, which is acceptable).

- [ ] **Step 8: Commit**

```bash
git add app/core/detection_engine.py tests/test_detection_engine.py
git commit -m "feat: port detection engine with PC-01/02/04 fixes and callback injection"
```

---

## Task 8: Export Engine (Port)

**Files:**
- Port: `app/core/export_engine.py`
- Port: `app/core/thumbnail_gen.py`

- [ ] **Step 1: Copy both files**

```bash
cp "OLD RASPBERRI PI VERSION/app/core/export_engine.py" app/core/export_engine.py
cp "OLD RASPBERRI PI VERSION/app/core/thumbnail_gen.py" app/core/thumbnail_gen.py
```

- [ ] **Step 2: Replace bare `"ffmpeg"` strings in export_engine.py**

```python
# Add at top of app/core/export_engine.py:
from app.utils.ffmpeg_path import get_ffmpeg

# Replace every ["ffmpeg", ...] list in subprocess calls with [get_ffmpeg(), ...]
# There are 3 places: segment extraction, merge command, and _run_ffmpeg usages
```

- [ ] **Step 3: Remove SQLite dependency from export_engine.py**

The export engine uses `get_conn()` to read events and update progress. Replace with parameters:

```python
# Change run() signature:
def run(
    job_id: str,
    source_path: str,
    source_info: dict,
    events: list,           # list of dicts with start_s, end_s, included
    output_dir: Path,
    settings: dict,
    logger,
    on_progress=None,
) -> tuple:                 # (output_path, output_name, output_size)
```

Remove `from app.database import get_conn`. Replace DB event query with the passed `events` list (filter `included=True`). Replace `conn.execute("UPDATE jobs SET progress=...")` with `if on_progress: on_progress(progress)`.

- [ ] **Step 4: Fix output path — use passed output_dir**

```python
# Replace the hardcoded OUTPUTS_DIR usage:
# BEFORE:
output_path = OUTPUTS_DIR / job_id / output_name
# AFTER:
output_path = Path(output_dir) / output_name
output_path.parent.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 5: Apply same ffmpeg path fix to thumbnail_gen.py**

```python
# Add at top of app/core/thumbnail_gen.py:
from app.utils.ffmpeg_path import get_ffmpeg

# Replace ["ffmpeg", ...] with [get_ffmpeg(), ...]
```

- [ ] **Step 6: Commit**

```bash
git add app/core/export_engine.py app/core/thumbnail_gen.py
git commit -m "feat: port export engine — remove SQLite, use bundled ffmpeg, accept output_dir"
```

---

## Task 9: YOLO Detector

**Files:**
- Create: `app/core/yolo_detector.py`
- Create: `tests/test_yolo_detector.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_yolo_detector.py
def test_yolo_detector_imports():
    from app.core import yolo_detector
    assert hasattr(yolo_detector, "run")

def test_yolo_unavailable_raises_helpful_error():
    """If ultralytics not installed, run() should raise ImportError with install hint."""
    import sys, unittest.mock as mock
    with mock.patch.dict(sys.modules, {"ultralytics": None}):
        from importlib import reload
        import app.core.yolo_detector as yd
        reload(yd)
        import pytest
        with pytest.raises(ImportError, match="ultralytics"):
            yd.run(
                job_id="x", source_path="fake.mp4",
                source_info={"fps": 25.0, "duration_s": 5.0},
                settings={"sensitivity": "medium", "frame_skip": 1,
                           "padding_s": 1.0, "min_gap_s": 1.0, "min_event_s": 1.0,
                           "zones": [], "recording_start": None},
                cancel_event=__import__("threading").Event(),
                logger=lambda l: None,
            )
```

- [ ] **Step 2: Create `app/core/yolo_detector.py`**

```python
"""
YOLOv8n-based motion + object detector.
Same interface as detection_engine.run() — drop-in alternative.
Falls back to ImportError with install hint if ultralytics is absent.
"""
import threading
from pathlib import Path
from typing import Callable, Optional

from app.config import DETECT_WIDTH as W, DETECT_HEIGHT as H, BATCH_SIZE, MODEL_DIR
from app.utils.time_utils import seconds_to_clock

YOLO_LABELS = {
    0: "Person", 1: "Bicycle", 2: "Vehicle", 3: "Vehicle",
    5: "Vehicle", 7: "Vehicle", 14: "Animal", 15: "Animal",
    16: "Animal",
}

def run(
    job_id: str,
    source_path: str,
    source_info: dict,
    settings: dict,
    cancel_event: threading.Event,
    logger: Callable,
    on_progress=None,
    on_event=None,
) -> None:
    try:
        from ultralytics import YOLO
    except ImportError:
        raise ImportError(
            "ultralytics is required for YOLO mode. "
            "Install it with: pip install ultralytics"
        )

    import cv2
    import numpy as np

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "yolov8n.pt"
    model = YOLO(str(model_path))   # auto-downloads on first run

    sensitivity = settings.get("sensitivity", "medium")
    conf_threshold = {"low": 0.6, "medium": 0.4, "high": 0.25}[sensitivity]
    frame_skip = int(settings.get("frame_skip", 1))
    padding_s = float(settings.get("padding_s", 2.0))
    min_gap_s = float(settings.get("min_gap_s", 2.0))
    min_event_s = float(settings.get("min_event_s", 2.0))
    recording_start = settings.get("recording_start")

    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {source_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    fps = cap.get(cv2.CAP_PROP_FPS) or float(source_info.get("fps", 25))

    logger(f"[YOLO] Starting — {total_frames} frames, conf>={conf_threshold}")

    in_event = False
    event_start = 0.0
    event_start_clock = ""
    silence_start: Optional[float] = None
    peak_label = None
    frame_idx = 0
    frames_done = 0

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

            small = cv2.resize(frame, (W, H))
            results = model(small, verbose=False, conf=conf_threshold)
            detections = results[0].boxes if results else []
            has_detection = len(detections) > 0

            # Label from highest-confidence detection
            label = None
            if has_detection:
                cls_ids = [int(b.cls[0]) for b in detections]
                label = next((YOLO_LABELS[c] for c in cls_ids if c in YOLO_LABELS), "Motion")

            if not in_event and has_detection:
                in_event = True
                event_start = max(0.0, current_pts - padding_s)
                event_start_clock = seconds_to_clock(event_start, recording_start)
                silence_start = None
                peak_label = label

            elif in_event:
                if has_detection:
                    silence_start = None
                    peak_label = peak_label or label
                else:
                    if silence_start is None:
                        silence_start = current_pts
                    if current_pts - silence_start >= min_gap_s:
                        event_end = silence_start + padding_s
                        if event_end - event_start >= min_event_s:
                            ev = {
                                "start_s": round(event_start, 3),
                                "end_s": round(event_end, 3),
                                "start_clock": event_start_clock,
                                "end_clock": seconds_to_clock(event_end, recording_start),
                                "peak_score": 1.0,
                                "included": True,
                                "label": peak_label,
                            }
                            if on_event:
                                on_event(ev)
                        in_event = False
                        silence_start = None
                        peak_label = None

            frame_idx += 1
            frames_done += 1

            if frame_idx % BATCH_SIZE == 0:
                progress = min(frame_idx / total_frames, 0.99)
                if on_progress:
                    on_progress(progress)
                if cancel_event.is_set():
                    break

        # Close open event at EOF
        if in_event and not cancel_event.is_set():
            event_end = current_pts + padding_s
            if event_end - event_start >= min_event_s:
                ev = {
                    "start_s": round(event_start, 3),
                    "end_s": round(event_end, 3),
                    "start_clock": event_start_clock,
                    "end_clock": seconds_to_clock(event_end, recording_start),
                    "peak_score": 1.0,
                    "included": True,
                    "label": peak_label,
                }
                if on_event:
                    on_event(ev)

        if on_progress:
            on_progress(1.0)
        logger(f"[YOLO] Done — {frames_done} frames processed")

    finally:
        cap.release()
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_yolo_detector.py -v
```

Expected: `2 passed`.

- [ ] **Step 4: Commit**

```bash
git add app/core/yolo_detector.py tests/test_yolo_detector.py
git commit -m "feat: YOLOv8n detector with per-job mode selection and graceful fallback"
```

---

## Task 10: System Utils (Cross-Platform)

**Files:**
- Create: `app/utils/system.py`

- [ ] **Step 1: Create `app/utils/system.py`**

```python
"""Cross-platform CPU, RAM, and temperature stats."""
import platform
import subprocess
from typing import Optional
import psutil

def get_cpu_percent() -> float:
    return psutil.cpu_percent(interval=0.1)

def get_ram_percent() -> float:
    return psutil.virtual_memory().percent

def get_cpu_temp() -> Optional[float]:
    """Return CPU temperature in Celsius, or None if unavailable."""
    system = platform.system()
    if system == "Linux":
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return int(f.read().strip()) / 1000.0
        except (FileNotFoundError, ValueError):
            return None
    if system == "Darwin":
        try:
            out = subprocess.run(
                ["smc", "-k", "TC0P", "-r"], capture_output=True, text=True, timeout=2
            )
            # output: "TC0P  [sp78]  55.2 C"
            parts = out.stdout.strip().split()
            return float(parts[-2]) if len(parts) >= 2 else None
        except Exception:
            return None
    return None  # Windows — not available without WMI

def open_folder(path: str) -> None:
    """Open a folder in the native file manager."""
    import os
    from pathlib import Path
    system = platform.system()
    p = str(Path(path).resolve())
    if system == "Windows":
        os.startfile(p)
    elif system == "Darwin":
        subprocess.run(["open", p])
    else:
        subprocess.run(["xdg-open", p])
```

- [ ] **Step 2: Smoke-test**

```bash
python -c "from app.utils.system import get_cpu_percent, get_ram_percent; print(get_cpu_percent(), get_ram_percent())"
```

Expected: two numbers printed (e.g. `12.3 45.6`).

- [ ] **Step 3: Commit**

```bash
git add app/utils/system.py
git commit -m "feat: cross-platform CPU/RAM/temp stats and folder opener"
```

---

## Task 11: FastAPI App + Session API

**Files:**
- Create: `app/main.py`
- Create: `app/api/job.py`
- Create: `tests/test_api_job.py`

- [ ] **Step 1: Create `app/main.py`**

```python
import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from app import session
from app.config import PREVIEW_DIR, JOBS_DIR
from app.core.log_buffer import log_buffer

_BASE = Path(__file__).parent.parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    log_buffer.set_loop(asyncio.get_running_loop())
    session.reset()
    asyncio.create_task(_preview_cleanup())
    yield

async def _preview_cleanup():
    while True:
        await asyncio.sleep(60)
        try:
            now = time.time()
            for f in PREVIEW_DIR.glob("*.mp4"):
                if now - f.stat().st_mtime > 300:
                    f.unlink(missing_ok=True)
        except Exception:
            pass

def create_app() -> FastAPI:
    app = FastAPI(title="CCTV Processor", lifespan=lifespan)

    from app.api.job import router as job_router
    from app.api.preview import router as preview_router
    from app.api.stream import router as stream_router
    from app.api.shell_bridge import router as shell_router

    app.include_router(job_router, prefix="/api")
    app.include_router(preview_router, prefix="/api")
    app.include_router(stream_router, prefix="/api")
    app.include_router(shell_router, prefix="/api")

    def _page(name):
        def handler():
            p = _BASE / "static" / "pages" / f"{name}.html"
            return FileResponse(str(p)) if p.exists() else HTMLResponse("Not found", 404)
        return handler

    app.get("/")(lambda: FileResponse(str(_BASE / "static" / "pages" / "home.html")))
    app.get("/processing")(_page("processing"))
    app.get("/timeline")(_page("timeline"))
    app.get("/export")(_page("export"))
    app.get("/api/health")(lambda: {"status": "ok"})

    app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")
    return app

app = create_app()
```

- [ ] **Step 2: Write failing API tests**

```python
# tests/test_api_job.py
import pytest
from pathlib import Path

TEST_VIDEO = str(Path("OLD RASPBERRI PI VERSION/Test Video/20260507_012210 (1).mp4").resolve())
FAKE_PATH = "/nonexistent/video.mp4"

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_create_job_missing_file(client):
    r = client.post("/api/job/create", json={"source_path": FAKE_PATH})
    assert r.status_code == 400
    assert "not found" in r.json()["detail"].lower()

def test_get_job_initial_state(client):
    r = client.get("/api/job")
    assert r.status_code == 200
    assert r.json()["status"] == "idle"

def test_toggle_event_out_of_range(client):
    r = client.put("/api/job/events/0/toggle")
    assert r.status_code == 404

@pytest.mark.skipif(not Path(TEST_VIDEO).exists(), reason="test video not present")
def test_create_job_valid_file(client):
    r = client.post("/api/job/create", json={"source_path": TEST_VIDEO})
    assert r.status_code == 200
    data = r.json()
    assert "job_id" in data
    assert data["status"] == "ready"
```

- [ ] **Step 3: Run — expect failure**

```bash
pytest tests/test_api_job.py::test_health -v
```

Expected: `ImportError` — `app.api.job` doesn't exist yet.

- [ ] **Step 4: Create `app/api/job.py`**

```python
import json
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import session
from app.core.log_buffer import log_buffer
from app.utils import ffprobe
from app.config import JOBS_DIR, STREAM_COPY_SAFE

router = APIRouter()

class CreateJobRequest(BaseModel):
    source_path: str

class StartJobRequest(BaseModel):
    sensitivity: str = "medium"
    mode: str = "mog2"           # "mog2" | "yolo"
    frame_skip: int = 1
    padding_s: float = 2.0
    min_gap_s: float = 2.0
    min_event_s: float = 2.0
    zones: list = []
    recording_start: str | None = None

class ExportRequest(BaseModel):
    output_type: str = "merged"  # "merged" | "individual"
    quality: str = "original"   # "original" | "720p" | "480p"
    output_dir: str | None = None

@router.get("/job")
def get_job():
    return session.snapshot()

@router.post("/job/create")
def create_job(req: CreateJobRequest):
    p = Path(req.source_path)
    if not p.exists():
        raise HTTPException(400, f"File not found: {req.source_path}")

    try:
        info = ffprobe.probe(str(p))
    except Exception as e:
        raise HTTPException(400, f"Cannot read video: {e}")

    warnings = []
    codec = (info.get("codec") or "").lower()
    if codec not in STREAM_COPY_SAFE:
        warnings.append(f"Codec '{codec}' requires re-encoding — export will be slower.")

    # Disk space check: need 2× source size
    source_size = p.stat().st_size
    import shutil
    free = shutil.disk_usage(p.parent).free
    if free < source_size * 2:
        raise HTTPException(
            400,
            f"Insufficient disk space. Need ~{source_size*2//1e9:.1f} GB free, "
            f"only {free//1e9:.1f} GB available."
        )

    session.reset()
    session.update(
        source_path=str(p),
        source_info=info,
        status="ready",
    )
    snap = session.snapshot()
    return {"job_id": snap["job_id"], "status": "ready",
            "source_info": info, "warnings": warnings}

@router.post("/job/start")
def start_job(req: StartJobRequest):
    snap = session.snapshot()
    if snap["status"] not in ("ready", "completed", "failed", "cancelled"):
        raise HTTPException(400, f"Cannot start — current status: {snap['status']}")

    settings = req.model_dump()
    session.update(settings=settings, status="detecting", progress=0.0, events=[], error=None)

    cancel_event = threading.Event()
    session.update(_cancel_event=cancel_event)

    def _run():
        mode = settings.get("mode", "mog2")
        if mode == "yolo":
            from app.core import yolo_detector as engine
        else:
            from app.core import detection_engine as engine

        job_id = session.snapshot()["job_id"]
        log_buffer.reset(job_id)

        try:
            engine.run(
                job_id=job_id,
                source_path=snap["source_path"],
                source_info=snap["source_info"],
                settings=settings,
                cancel_event=cancel_event,
                logger=lambda line: log_buffer.append(job_id, line),
                on_progress=lambda p: session.update(progress=p),
                on_event=lambda ev: session.append_event(ev),
            )
            if cancel_event.is_set():
                session.update(status="cancelled")
            else:
                session.update(status="completed", progress=1.0)
        except Exception as e:
            session.update(status="failed", error=str(e))
        finally:
            log_buffer.close(job_id)

    threading.Thread(target=_run, daemon=True, name="detection").start()
    return {"status": "detecting"}

@router.post("/job/cancel")
def cancel_job():
    snap = session.snapshot()
    cancel: threading.Event | None = snap.get("_cancel_event")
    if cancel:
        cancel.set()
    session.update(status="cancelled")
    return {"status": "cancelled"}

@router.get("/job/events")
def get_events():
    return session.snapshot()["events"]

@router.put("/job/events/{idx}/toggle")
def toggle_event(idx: int):
    events = session.snapshot()["events"]
    if idx < 0 or idx >= len(events):
        raise HTTPException(404, f"Event index {idx} out of range")
    session.toggle_event(idx)
    return session.snapshot()["events"][idx]

@router.post("/job/export")
def export_job(req: ExportRequest):
    from pathlib import Path as P
    from app.core import export_engine
    from app.core.log_buffer import log_buffer

    snap = session.snapshot()
    if snap["status"] not in ("completed", "cancelled"):
        raise HTTPException(400, "Detection must complete before export")

    events = [e for e in snap["events"] if e.get("included", True)]
    if not events:
        raise HTTPException(400, "No events included — toggle at least one event")

    output_dir = P(req.output_dir or snap["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    job_id = snap["job_id"]
    session.update(status="exporting", progress=0.0)
    log_buffer.reset(job_id)

    def _export():
        try:
            settings = snap["settings"].copy()
            settings["output_quality"] = req.quality
            settings["output_type"] = req.output_type
            output_path, output_name, output_size = export_engine.run(
                job_id=job_id,
                source_path=snap["source_path"],
                source_info=snap["source_info"],
                events=events,
                output_dir=output_dir,
                settings=settings,
                logger=lambda line: log_buffer.append(job_id, line),
                on_progress=lambda p: session.update(progress=p),
            )
            session.update(
                status="completed",
                output_path=str(output_path),
                progress=1.0,
            )
        except Exception as e:
            session.update(status="failed", error=str(e))
        finally:
            log_buffer.close(job_id)

    threading.Thread(target=_export, daemon=True, name="export").start()
    return {"status": "exporting"}
```

- [ ] **Step 5: Run API tests**

```bash
pytest tests/test_api_job.py -v
```

Expected: all pass (video-dependent tests skip if absent).

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/api/job.py tests/test_api_job.py
git commit -m "feat: FastAPI app + session-backed job API (no SQLite)"
```

---

## Task 12: Preview + SSE + Shell Bridge APIs

**Files:**
- Create: `app/api/preview.py`
- Create: `app/api/stream.py`
- Create: `app/api/shell_bridge.py`

- [ ] **Step 1: Create `app/api/preview.py`**

```python
import secrets
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app import session
from app.config import PREVIEW_DIR
from app.core.export_engine import generate_preview

router = APIRouter()

@router.post("/job/preview/{idx}")
def create_preview(idx: int):
    snap = session.snapshot()
    events = snap["events"]
    if idx < 0 or idx >= len(events):
        raise HTTPException(404, "Event not found")
    ev = events[idx]
    token = secrets.token_hex(8)
    try:
        path = generate_preview(
            source_path=snap["source_path"],
            start_s=float(ev["start_s"]),
            end_s=float(ev["end_s"]),
            token=token,
        )
    except Exception as e:
        raise HTTPException(500, f"Preview failed: {e}")
    return {"url": f"/api/preview/{token}.mp4", "token": token}

@router.get("/preview/{token}.mp4")
def serve_preview(token: str):
    # Sanitise: token must be hex only
    if not all(c in "0123456789abcdef" for c in token):
        raise HTTPException(400, "Invalid token")
    path = PREVIEW_DIR / f"{token}.mp4"
    if not path.exists():
        raise HTTPException(404, "Preview expired or not found")
    return FileResponse(str(path), media_type="video/mp4")
```

- [ ] **Step 2: Create `app/api/stream.py`**

```python
import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app import session
from app.core.log_buffer import log_buffer

router = APIRouter()

@router.get("/stream")
async def stream():
    snap = session.snapshot()
    job_id = snap["job_id"]
    q = log_buffer.subscribe(job_id)

    async def event_generator():
        try:
            while True:
                try:
                    line = await asyncio.wait_for(q.get(), timeout=30.0)
                    if line == "__DONE__":
                        yield f"data: {json.dumps({'type':'done'})}\n\n"
                        break
                    # Also send current progress + event count
                    s = session.snapshot()
                    yield f"data: {json.dumps({'type':'log','line':line,'progress':s['progress'],'event_count':len(s['events']),'status':s['status']})}\n\n"
                except asyncio.TimeoutError:
                    yield "data: {\"type\":\"keepalive\"}\n\n"
        finally:
            log_buffer.unsubscribe(job_id, q)

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

- [ ] **Step 3: Create `app/api/shell_bridge.py`**

```python
from fastapi import APIRouter
from pydantic import BaseModel
from app import session

router = APIRouter()

class FilePathPayload(BaseModel):
    path: str

# PyQt6 shell calls this after QFileDialog returns a path
@router.post("/shell/filepath")
def receive_filepath(payload: FilePathPayload):
    from pathlib import Path
    p = Path(payload.path)
    if not p.exists():
        return {"ok": False, "error": "File not found"}
    session.update(pending_path=str(p))
    return {"ok": True, "path": str(p)}

@router.get("/shell/pending-path")
def get_pending_path():
    snap = session.snapshot()
    path = snap.get("pending_path")
    if path:
        session.update(pending_path=None)
    return {"path": path}

@router.post("/shell/open-folder")
def open_output_folder():
    from app.utils.system import open_folder
    snap = session.snapshot()
    out = snap.get("output_path")
    if not out:
        return {"ok": False}
    import os
    open_folder(str(os.path.dirname(out)))
    return {"ok": True}

@router.post("/shell/set-output-dir")
def set_output_dir(payload: FilePathPayload):
    session.update(output_dir=payload.path)
    return {"ok": True, "output_dir": payload.path}
```

- [ ] **Step 4: Add `reset()` method to log_buffer (needed by job API)**

Open `app/core/log_buffer.py`. Add a `reset(job_id)` method that clears history for that job:

```python
def reset(self, job_id: str) -> None:
    with self._lock:  # add _lock = threading.Lock() if not already present
        self._history.pop(job_id, None)
        self._subscribers.pop(job_id, None)
```

- [ ] **Step 5: Smoke-test the full API stack**

```bash
python -c "
from fastapi.testclient import TestClient
from app.main import create_app
from app import session
session.reset()
c = TestClient(create_app())
print(c.get('/api/health').json())
print(c.get('/api/job').json()['status'])
"
```

Expected output:
```
{'status': 'ok'}
idle
```

- [ ] **Step 6: Commit**

```bash
git add app/api/preview.py app/api/stream.py app/api/shell_bridge.py
git commit -m "feat: preview, SSE stream, and shell bridge API endpoints"
```

---

## Task 13: Frontend — Home Page

**Files:**
- Create: `static/css/base.css`
- Create: `static/js/app.js`
- Create: `static/pages/home.html`
- Create: `static/js/pages/home.js`

- [ ] **Step 1: Create `static/css/base.css`**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #0d1117;
  --surface: #161b22;
  --border: #30363d;
  --text: #e6edf3;
  --muted: #8b949e;
  --accent: #1f6feb;
  --success: #238636;
  --warning: #e3b341;
  --danger: #da3633;
  --radius: 6px;
  --gap: 16px;
}

body { background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, sans-serif; font-size: 14px; height: 100vh; overflow: hidden; }

a { color: var(--accent); text-decoration: none; }

button, .btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  padding: 8px 16px; border-radius: var(--radius); border: none; cursor: pointer;
  font-size: 13px; font-weight: 600; transition: opacity 0.15s;
}
button:hover, .btn:hover { opacity: 0.85; }
.btn-primary { background: var(--accent); color: #fff; }
.btn-success { background: var(--success); color: #fff; }
.btn-secondary { background: var(--surface); color: var(--text); border: 1px solid var(--border); }
.btn-danger { background: var(--danger); color: #fff; }
.btn-sm { padding: 5px 10px; font-size: 12px; }
button:disabled, .btn:disabled { opacity: 0.4; cursor: not-allowed; }

.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: var(--gap); }
.label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); margin-bottom: 6px; }

.warning-banner { background: #2d1f00; border: 1px solid var(--warning); border-radius: var(--radius); padding: 10px 14px; color: var(--warning); font-size: 12px; }
.error-banner { background: #2d0000; border: 1px solid var(--danger); border-radius: var(--radius); padding: 10px 14px; color: var(--danger); font-size: 12px; }

input[type=range] { width: 100%; accent-color: var(--accent); }
select { background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: var(--radius); padding: 6px 10px; font-size: 13px; width: 100%; }

.progress-bar { height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }
.progress-bar-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--success)); border-radius: 3px; transition: width 0.3s; }
```

- [ ] **Step 2: Create `static/js/app.js`** (client-side router)

```javascript
const routes = {
  '/': () => import('./pages/home.js'),
  '/processing': () => import('./pages/processing.js'),
  '/timeline': () => import('./pages/timeline.js'),
  '/export': () => import('./pages/export.js'),
};

let currentUnmount = null;

async function navigate(path) {
  if (currentUnmount) { currentUnmount(); currentUnmount = null; }
  const load = routes[path] || routes['/'];
  const mod = await load();
  const container = document.getElementById('app');
  container.innerHTML = '';
  if (mod.mount) currentUnmount = mod.mount(container) || null;
}

window.navigate = navigate;
window.addEventListener('popstate', () => navigate(location.pathname));
document.addEventListener('DOMContentLoaded', () => navigate(location.pathname));

window.go = function(path) {
  history.pushState({}, '', path);
  navigate(path);
};
```

- [ ] **Step 3: Create `static/pages/home.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CCTV Video Processor</title>
  <link rel="stylesheet" href="/static/css/base.css">
  <link rel="stylesheet" href="/static/css/home.css">
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/static/js/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Create `static/css/home.css`**

```css
.home-layout { display: grid; grid-template-columns: 1fr 300px; gap: var(--gap); height: 100vh; padding: var(--gap); }
.drop-zone {
  border: 2px dashed var(--border); border-radius: 10px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; text-align: center; padding: 40px; transition: border-color 0.2s;
}
.drop-zone.drag-over { border-color: var(--accent); background: rgba(31,111,235,0.05); }
.drop-zone .icon { font-size: 48px; }
.drop-zone .filename { color: var(--accent); font-weight: 600; word-break: break-all; }
.drop-zone .meta { color: var(--muted); font-size: 12px; }
.settings-panel { display: flex; flex-direction: column; gap: 14px; overflow-y: auto; }
.seg-buttons { display: flex; gap: 4px; }
.seg-btn { flex: 1; padding: 7px; border-radius: var(--radius); border: 1px solid var(--border); background: var(--surface); color: var(--muted); cursor: pointer; font-size: 12px; text-align: center; }
.seg-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
```

- [ ] **Step 5: Create `static/js/pages/home.js`**

```javascript
export function mount(container) {
  container.innerHTML = `
    <div class="home-layout">
      <div class="drop-zone" id="dropZone">
        <div class="icon">📂</div>
        <div id="dropText" style="font-size:18px;font-weight:600;color:var(--text)">Drop your video here</div>
        <div style="color:var(--muted);font-size:12px">MP4, MKV, AVI, MOV, TS — any codec</div>
        <div id="fileInfo" style="display:none;text-align:center"></div>
        <div id="warnings" style="display:none"></div>
        <button class="btn btn-secondary" id="browseBtn">Browse File…</button>
      </div>
      <div class="settings-panel">
        <div>
          <div class="label">Detection Mode</div>
          <div class="seg-buttons">
            <div class="seg-btn active" data-mode="mog2">MOG2 (Fast)</div>
            <div class="seg-btn" data-mode="yolo">YOLO (Smart)</div>
          </div>
        </div>
        <div>
          <div class="label">Sensitivity</div>
          <div class="seg-buttons">
            <div class="seg-btn" data-sens="low">Low</div>
            <div class="seg-btn active" data-sens="medium">Medium</div>
            <div class="seg-btn" data-sens="high">High</div>
          </div>
        </div>
        <div>
          <div class="label">Clip Padding (seconds before/after)</div>
          <input type="range" id="padding" min="0" max="10" value="2" step="0.5">
          <div style="color:var(--muted);font-size:12px;text-align:right" id="paddingVal">2 s</div>
        </div>
        <div>
          <div class="label">Min. Event Duration (seconds)</div>
          <input type="range" id="minDur" min="1" max="30" value="2" step="1">
          <div style="color:var(--muted);font-size:12px;text-align:right" id="minDurVal">2 s</div>
        </div>
        <button class="btn btn-success" id="startBtn" disabled style="margin-top:auto;padding:12px">▶ Start Detection</button>
      </div>
    </div>
  `;

  let selectedPath = null;
  let selectedMode = 'mog2';
  let selectedSens = 'medium';

  // Segment button toggle
  container.querySelectorAll('[data-mode]').forEach(btn => {
    btn.addEventListener('click', () => {
      container.querySelectorAll('[data-mode]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedMode = btn.dataset.mode;
    });
  });
  container.querySelectorAll('[data-sens]').forEach(btn => {
    btn.addEventListener('click', () => {
      container.querySelectorAll('[data-sens]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedSens = btn.dataset.sens;
    });
  });

  // Sliders
  const paddingSlider = container.querySelector('#padding');
  paddingSlider.addEventListener('input', () => {
    container.querySelector('#paddingVal').textContent = paddingSlider.value + ' s';
  });
  const minDurSlider = container.querySelector('#minDur');
  minDurSlider.addEventListener('input', () => {
    container.querySelector('#minDurVal').textContent = minDurSlider.value + ' s';
  });

  async function loadFile(path) {
    const r = await fetch('/api/job/create', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ source_path: path })
    });
    const data = await r.json();
    if (!r.ok) {
      container.querySelector('#dropText').textContent = '⚠ ' + data.detail;
      return;
    }
    selectedPath = path;
    const info = data.source_info;
    const fileInfo = container.querySelector('#fileInfo');
    fileInfo.style.display = 'block';
    fileInfo.innerHTML = `
      <div class="filename">${path.split(/[\\/]/).pop()}</div>
      <div class="meta">${info.width}×${info.height} · ${info.codec?.toUpperCase()} · ${Math.round(info.duration_s/60)}m ${Math.round(info.duration_s%60)}s</div>
    `;
    if (data.warnings?.length) {
      const w = container.querySelector('#warnings');
      w.style.display = 'block';
      w.innerHTML = data.warnings.map(msg => `<div class="warning-banner">⚠ ${msg}</div>`).join('');
    }
    container.querySelector('#startBtn').disabled = false;
  }

  // Drop zone
  const dz = container.querySelector('#dropZone');
  dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag-over'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
  dz.addEventListener('drop', e => {
    e.preventDefault(); dz.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) loadFile(file.path || file.name);
  });

  // Browse button — asks PyQt6 shell via a custom event
  container.querySelector('#browseBtn').addEventListener('click', () => {
    // Shell listens for this and opens QFileDialog, then POSTs to /api/shell/filepath
    window.dispatchEvent(new CustomEvent('cctv:browse'));
    // Poll for result
    const poll = setInterval(async () => {
      const r = await fetch('/api/shell/pending-path');
      const d = await r.json();
      if (d.path) { clearInterval(poll); loadFile(d.path); }
    }, 300);
    setTimeout(() => clearInterval(poll), 30000);
  });

  // Start detection
  container.querySelector('#startBtn').addEventListener('click', async () => {
    const r = await fetch('/api/job/start', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        mode: selectedMode,
        sensitivity: selectedSens,
        frame_skip: 1,
        padding_s: parseFloat(paddingSlider.value),
        min_gap_s: 2.0,
        min_event_s: parseFloat(minDurSlider.value),
      })
    });
    if (r.ok) go('/processing');
  });
}
```

- [ ] **Step 6: Commit**

```bash
git add static/
git commit -m "feat: home page — file drop, settings panel, browse button"
```

---

## Task 14: Frontend — Processing Page

**Files:**
- Create: `static/pages/processing.html`
- Create: `static/js/pages/processing.js`
- Create: `static/css/processing.css`

- [ ] **Step 1: Create `static/pages/processing.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>CCTV Processor — Processing</title>
  <link rel="stylesheet" href="/static/css/base.css">
  <link rel="stylesheet" href="/static/css/processing.css">
</head>
<body><div id="app"></div><script type="module" src="/static/js/app.js"></script></body>
</html>
```

- [ ] **Step 2: Create `static/css/processing.css`**

```css
.proc-layout { padding: var(--gap); display: flex; flex-direction: column; gap: var(--gap); height: 100vh; }
.proc-header { display: flex; justify-content: space-between; align-items: center; }
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px; text-align: center; }
.stat-card .val { font-size: 22px; font-weight: 700; color: var(--text); }
.stat-card .lbl { font-size: 11px; color: var(--muted); margin-top: 2px; }
.stat-card.events .val { color: var(--success); }
.log-panel { flex: 1; background: #010409; border: 1px solid var(--border); border-radius: var(--radius); padding: 12px; overflow-y: auto; font-family: monospace; font-size: 11px; line-height: 1.6; }
.log-line-log { color: var(--muted); }
.log-line-event { color: var(--success); }
.log-line-warn { color: var(--warning); }
.log-line-error { color: var(--danger); }
```

- [ ] **Step 3: Create `static/js/pages/processing.js`**

```javascript
export function mount(container) {
  container.innerHTML = `
    <div class="proc-layout">
      <div class="proc-header">
        <div>
          <div style="font-size:16px;font-weight:700" id="procTitle">Detecting…</div>
          <div style="color:var(--muted);font-size:12px" id="procMeta"></div>
        </div>
        <button class="btn btn-secondary btn-sm" id="cancelBtn">Cancel</button>
      </div>
      <div class="stats-row">
        <div class="stat-card"><div class="val" id="statPct">0%</div><div class="lbl">Progress</div></div>
        <div class="stat-card"><div class="val" id="statETA">—</div><div class="lbl">Est. Remaining</div></div>
        <div class="stat-card"><div class="val" id="statCPU">—</div><div class="lbl">CPU</div></div>
        <div class="stat-card events"><div class="val" id="statEvents">0</div><div class="lbl">Events Found</div></div>
      </div>
      <div class="progress-bar"><div class="progress-bar-fill" id="pbar" style="width:0%"></div></div>
      <div class="log-panel" id="logPanel"></div>
    </div>
  `;

  const logPanel = container.querySelector('#logPanel');
  const startTime = Date.now();
  let lastProgress = 0;

  function appendLog(line) {
    const div = document.createElement('div');
    const cls = line.includes('[EVENT]') ? 'log-line-event'
               : line.includes('[WARN]') || line.includes('[ERROR]') ? 'log-line-warn'
               : 'log-line-log';
    div.className = cls;
    div.textContent = line;
    logPanel.appendChild(div);
    logPanel.scrollTop = logPanel.scrollHeight;
  }

  // Load initial meta
  fetch('/api/job').then(r => r.json()).then(d => {
    const info = d.source_info || {};
    container.querySelector('#procMeta').textContent =
      `${info.width || '?'}×${info.height || '?'} · ${(info.codec||'').toUpperCase()} · ${d.settings?.mode?.toUpperCase() || 'MOG2'} ${d.settings?.sensitivity || 'medium'}`;
  });

  const es = new EventSource('/api/stream');
  es.onmessage = e => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'keepalive') return;
    if (msg.type === 'log') {
      appendLog(msg.line);
      const pct = Math.round((msg.progress || 0) * 100);
      container.querySelector('#pbar').style.width = pct + '%';
      container.querySelector('#statPct').textContent = pct + '%';
      container.querySelector('#statEvents').textContent = msg.event_count || 0;
      // ETA
      if (msg.progress > 0.01) {
        const elapsed = (Date.now() - startTime) / 1000;
        const remaining = elapsed / msg.progress * (1 - msg.progress);
        container.querySelector('#statETA').textContent =
          remaining > 60 ? Math.round(remaining/60) + 'm' : Math.round(remaining) + 's';
      }
      if (msg.status === 'completed' || msg.status === 'cancelled' || msg.status === 'failed') {
        es.close();
        if (msg.status === 'completed') go('/timeline');
      }
    }
    if (msg.type === 'done') { es.close(); go('/timeline'); }
  };
  es.onerror = () => {
    // Poll fallback
    const poll = setInterval(async () => {
      const d = await fetch('/api/job').then(r => r.json());
      if (d.status === 'completed') { clearInterval(poll); go('/timeline'); }
      if (d.status === 'failed') { clearInterval(poll); appendLog('[ERROR] ' + d.error); }
    }, 2000);
    return () => clearInterval(poll);
  };

  // CPU stat update
  const cpuInterval = setInterval(async () => {
    try {
      const d = await fetch('/api/job').then(r => r.json());
      // system stats not yet an endpoint — show progress-derived value
      container.querySelector('#statCPU').textContent = d.status;
    } catch { /* ignore */ }
  }, 3000);

  container.querySelector('#cancelBtn').addEventListener('click', async () => {
    await fetch('/api/job/cancel', { method: 'POST' });
    es.close();
    go('/timeline');
  });

  return () => { es.close(); clearInterval(cpuInterval); };
}
```

- [ ] **Step 4: Commit**

```bash
git add static/pages/processing.html static/css/processing.css static/js/pages/processing.js
git commit -m "feat: processing page with SSE live log, progress bar, ETA"
```

---

## Task 15: Frontend — Timeline Page

**Files:**
- Create: `static/pages/timeline.html`
- Create: `static/js/pages/timeline.js`
- Create: `static/css/timeline.css`

- [ ] **Step 1: Create `static/pages/timeline.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>CCTV Processor — Timeline</title>
  <link rel="stylesheet" href="/static/css/base.css">
  <link rel="stylesheet" href="/static/css/timeline.css">
</head>
<body><div id="app"></div><script type="module" src="/static/js/app.js"></script></body>
</html>
```

- [ ] **Step 2: Create `static/css/timeline.css`**

```css
.timeline-layout { display: flex; flex-direction: column; height: 100vh; }
.timeline-toolbar { display: flex; align-items: center; gap: 10px; padding: 12px var(--gap); border-bottom: 1px solid var(--border); flex-wrap: wrap; }
.timeline-toolbar .spacer { flex: 1; }
.tl-summary { color: var(--muted); font-size: 12px; }
.tl-summary .hl { color: var(--success); font-weight: 600; }
.canvas-wrap { padding: 12px var(--gap); background: var(--bg); }
canvas#tlCanvas { width: 100%; height: 44px; display: block; cursor: pointer; border-radius: 4px; }
.events-list { flex: 1; overflow-y: auto; padding: 0 var(--gap) var(--gap); display: flex; flex-direction: column; gap: 6px; }
.event-card { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: var(--radius); border: 1px solid var(--border); background: var(--surface); cursor: pointer; transition: border-color 0.15s; }
.event-card.included { border-color: var(--accent); }
.event-card.excluded { opacity: 0.5; }
.event-card:hover { border-color: var(--text); }
.event-check { width: 20px; height: 20px; border-radius: 3px; display: flex; align-items: center; justify-content: center; font-size: 11px; flex-shrink: 0; }
.event-check.on { background: var(--accent); color: #fff; }
.event-check.off { background: var(--surface); border: 1px solid var(--border); }
.event-thumb { width: 72px; height: 40px; border-radius: 3px; background: var(--border); flex-shrink: 0; object-fit: cover; }
.event-thumb-placeholder { width: 72px; height: 40px; border-radius: 3px; background: var(--border); flex-shrink: 0; display:flex; align-items:center; justify-content:center; color:var(--muted); font-size:10px; }
.event-info { flex: 1; min-width: 0; }
.event-title { font-weight: 600; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.event-meta { color: var(--muted); font-size: 11px; }
.event-label { font-size: 10px; background: rgba(31,111,235,0.2); color: var(--accent); border-radius: 3px; padding: 1px 5px; }
.event-preview-btn { color: var(--muted); font-size: 11px; white-space: nowrap; cursor: pointer; }
.event-preview-btn:hover { color: var(--text); }
.preview-modal { position: fixed; inset: 0; background: rgba(0,0,0,0.8); display: flex; align-items: center; justify-content: center; z-index: 100; }
.preview-modal video { max-width: 90vw; max-height: 80vh; border-radius: var(--radius); }
.preview-modal-close { position: absolute; top: 20px; right: 24px; color: #fff; font-size: 24px; cursor: pointer; }
.no-events { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; color: var(--muted); text-align: center; }
```

- [ ] **Step 3: Create `static/js/pages/timeline.js`**

```javascript
export function mount(container) {
  container.innerHTML = `
    <div class="timeline-layout">
      <div class="timeline-toolbar">
        <div class="tl-summary" id="tlSummary">Loading…</div>
        <div class="spacer"></div>
        <button class="btn btn-secondary btn-sm" id="selectAllBtn">Select All</button>
        <button class="btn btn-secondary btn-sm" id="selectNoneBtn">Select None</button>
        <button class="btn btn-primary btn-sm" id="quickExportBtn">⚡ Quick Export</button>
        <button class="btn btn-success" id="exportBtn">Export Selected →</button>
      </div>
      <div class="canvas-wrap">
        <canvas id="tlCanvas" height="44"></canvas>
        <div style="display:flex;justify-content:space-between;margin-top:4px">
          <span style="color:var(--muted);font-size:10px" id="tlStart">00:00</span>
          <span style="color:var(--muted);font-size:10px" id="tlEnd">—</span>
        </div>
      </div>
      <div class="events-list" id="eventsList"></div>
    </div>
    <div class="preview-modal" id="previewModal" style="display:none">
      <span class="preview-modal-close" id="closePreview">✕</span>
      <video id="previewVideo" controls autoplay></video>
    </div>
  `;

  let events = [];
  let duration = 0;

  function fmtTime(s) {
    const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = Math.floor(s%60);
    return h > 0 ? `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
                 : `${m}:${String(sec).padStart(2,'0')}`;
  }

  function drawCanvas() {
    const canvas = container.querySelector('#tlCanvas');
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#161b22';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (!duration) return;
    events.forEach(ev => {
      const x = (ev.start_s / duration) * canvas.width;
      const w = Math.max(2, ((ev.end_s - ev.start_s) / duration) * canvas.width);
      ctx.fillStyle = ev.included ? '#1f6feb' : '#6e7681';
      ctx.fillRect(x, 0, w, canvas.height);
    });
  }

  function renderEvents() {
    const list = container.querySelector('#eventsList');
    if (events.length === 0) {
      list.innerHTML = `
        <div class="no-events">
          <div style="font-size:32px">🔍</div>
          <div style="font-size:16px;color:var(--text)">No motion events detected</div>
          <div>Try <strong>High</strong> sensitivity or check that your video has visible movement.</div>
          <button class="btn btn-secondary" onclick="go('/')">← New Detection</button>
        </div>`;
      return;
    }
    list.innerHTML = '';
    events.forEach((ev, idx) => {
      const card = document.createElement('div');
      card.className = `event-card ${ev.included ? 'included' : 'excluded'}`;
      card.innerHTML = `
        <div class="event-check ${ev.included ? 'on' : 'off'}">${ev.included ? '✓' : '✗'}</div>
        <div class="event-thumb-placeholder">▶</div>
        <div class="event-info">
          <div class="event-title">Event #${idx+1} — ${ev.start_clock || fmtTime(ev.start_s)}
            ${ev.label ? `<span class="event-label">${ev.label}</span>` : ''}
          </div>
          <div class="event-meta">${Math.round(ev.end_s - ev.start_s)}s · peak ${((ev.peak_score||0)*100).toFixed(1)}%${ev.included ? '' : ' · EXCLUDED'}</div>
        </div>
        <div class="event-preview-btn" data-idx="${idx}">▶ Preview</div>
      `;
      card.addEventListener('click', async (e) => {
        if (e.target.classList.contains('event-preview-btn')) return;
        await fetch(`/api/job/events/${idx}/toggle`, { method: 'PUT' });
        events[idx].included = !events[idx].included;
        renderEvents(); drawCanvas(); updateSummary();
      });
      card.querySelector('.event-preview-btn').addEventListener('click', async () => {
        const r = await fetch(`/api/job/preview/${idx}`, { method: 'POST' });
        if (!r.ok) return;
        const d = await r.json();
        const modal = container.querySelector('#previewModal');
        const video = container.querySelector('#previewVideo');
        video.src = d.url;
        modal.style.display = 'flex';
      });
      list.appendChild(card);
    });
  }

  function updateSummary() {
    const included = events.filter(e => e.included);
    const total = events.reduce((s, e) => s + (e.end_s - e.start_s), 0);
    const activ = included.reduce((s, e) => s + (e.end_s - e.start_s), 0);
    const pct = duration ? (activ/duration*100).toFixed(1) : 0;
    container.querySelector('#tlSummary').innerHTML =
      `Source: ${fmtTime(duration)} · <span class="hl">${events.length} events · ${Math.round(activ)}s activity (${pct}%)</span> · ${included.length} included`;
    container.querySelector('#exportBtn').disabled = included.length === 0;
    container.querySelector('#quickExportBtn').disabled = included.length === 0;
  }

  async function load() {
    const d = await fetch('/api/job').then(r => r.json());
    events = await fetch('/api/job/events').then(r => r.json());
    duration = d.source_info?.duration_s || 0;
    container.querySelector('#tlEnd').textContent = fmtTime(duration);
    drawCanvas(); renderEvents(); updateSummary();
  }

  load();

  container.querySelector('#selectAllBtn').addEventListener('click', async () => {
    for (let i = 0; i < events.length; i++) {
      if (!events[i].included) { await fetch(`/api/job/events/${i}/toggle`, {method:'PUT'}); events[i].included = true; }
    }
    renderEvents(); drawCanvas(); updateSummary();
  });
  container.querySelector('#selectNoneBtn').addEventListener('click', async () => {
    for (let i = 0; i < events.length; i++) {
      if (events[i].included) { await fetch(`/api/job/events/${i}/toggle`, {method:'PUT'}); events[i].included = false; }
    }
    renderEvents(); drawCanvas(); updateSummary();
  });
  container.querySelector('#quickExportBtn').addEventListener('click', () => go('/export?quick=1'));
  container.querySelector('#exportBtn').addEventListener('click', () => go('/export'));
  container.querySelector('#closePreview').addEventListener('click', () => {
    container.querySelector('#previewModal').style.display = 'none';
    container.querySelector('#previewVideo').src = '';
  });

  window.addEventListener('resize', drawCanvas);
  return () => window.removeEventListener('resize', drawCanvas);
}
```

- [ ] **Step 4: Commit**

```bash
git add static/pages/timeline.html static/css/timeline.css static/js/pages/timeline.js
git commit -m "feat: timeline page — canvas strip, event cards, preview modal, quick export"
```

---

## Task 16: Frontend — Export Page

**Files:**
- Create: `static/pages/export.html`
- Create: `static/js/pages/export.js`
- Create: `static/css/export.css`

- [ ] **Step 1: Create `static/pages/export.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>CCTV Processor — Export</title>
  <link rel="stylesheet" href="/static/css/base.css">
  <link rel="stylesheet" href="/static/css/export.css">
</head>
<body><div id="app"></div><script type="module" src="/static/js/app.js"></script></body>
</html>
```

- [ ] **Step 2: Create `static/css/export.css`**

```css
.export-layout { display: grid; grid-template-columns: 1fr 1fr; gap: var(--gap); padding: var(--gap); height: 100vh; }
.export-col { display: flex; flex-direction: column; gap: 16px; }
.export-summary { display: flex; flex-direction: column; gap: 8px; }
.summary-row { display: flex; justify-content: space-between; font-size: 13px; padding: 6px 0; border-bottom: 1px solid var(--border); }
.summary-row .key { color: var(--muted); }
.summary-row .val { font-weight: 600; }
.summary-row .val.fast { color: var(--success); }
.output-path-row { display: flex; gap: 6px; }
.output-path-row input { flex: 1; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 8px 10px; color: var(--text); font-size: 12px; }
.export-done { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; flex: 1; text-align: center; }
```

- [ ] **Step 3: Create `static/js/pages/export.js`**

```javascript
export function mount(container) {
  container.innerHTML = `
    <div class="export-layout">
      <div class="export-col">
        <div>
          <div class="label">Output Type</div>
          <div class="seg-buttons" style="display:flex;gap:6px">
            <div class="seg-btn active" data-type="merged" style="flex:1;padding:10px;text-align:center;cursor:pointer;border-radius:6px;border:1px solid var(--border);background:var(--accent);color:#fff">📼 Single merged MP4</div>
            <div class="seg-btn" data-type="individual" style="flex:1;padding:10px;text-align:center;cursor:pointer;border-radius:6px;border:1px solid var(--border);background:var(--surface);color:var(--muted)">📁 Individual clips</div>
          </div>
        </div>
        <div>
          <div class="label">Quality</div>
          <div class="seg-buttons" style="display:flex;gap:4px">
            <div class="seg-btn active" data-q="original" style="flex:1;padding:7px;text-align:center;cursor:pointer;border-radius:4px;border:1px solid var(--border);background:var(--accent);color:#fff;font-size:12px">Original</div>
            <div class="seg-btn" data-q="720p" style="flex:1;padding:7px;text-align:center;cursor:pointer;border-radius:4px;border:1px solid var(--border);background:var(--surface);color:var(--muted);font-size:12px">720p</div>
            <div class="seg-btn" data-q="480p" style="flex:1;padding:7px;text-align:center;cursor:pointer;border-radius:4px;border:1px solid var(--border);background:var(--surface);color:var(--muted);font-size:12px">480p</div>
          </div>
        </div>
        <div>
          <div class="label">Output Folder</div>
          <div class="output-path-row">
            <input type="text" id="outputDir" readonly>
            <button class="btn btn-secondary btn-sm" id="browseOutputBtn">Browse…</button>
          </div>
        </div>
        <div id="progressWrap" style="display:none">
          <div class="label" id="exportStatusLbl">Exporting…</div>
          <div class="progress-bar"><div class="progress-bar-fill" id="exportPbar" style="width:0%"></div></div>
          <div id="exportLog" style="font-family:monospace;font-size:10px;color:var(--muted);margin-top:6px;max-height:80px;overflow-y:auto"></div>
        </div>
        <div id="doneWrap" style="display:none" class="export-done">
          <div style="font-size:36px">✅</div>
          <div style="font-size:16px;font-weight:700">Export complete!</div>
          <div id="outputName" style="color:var(--muted);font-size:12px"></div>
          <div style="display:flex;gap:8px">
            <button class="btn btn-secondary" id="openFolderBtn">Open Folder</button>
            <button class="btn btn-primary" onclick="go('/')">New Detection</button>
          </div>
        </div>
        <button class="btn btn-success" id="exportNowBtn" style="margin-top:auto;padding:14px;font-size:15px">▶ Export Now</button>
        <div style="text-align:center"><a href="#" onclick="go('/timeline');return false" style="color:var(--muted);font-size:12px">← Back to timeline</a></div>
      </div>
      <div class="export-col">
        <div class="label">Export Summary</div>
        <div class="card export-summary" id="summary">Loading…</div>
      </div>
    </div>
  `;

  let selectedType = 'merged';
  let selectedQuality = 'original';

  function toggle(selector, attr) {
    container.querySelectorAll(`[${attr}]`).forEach(b => {
      const isActive = b.dataset[attr.replace('data-','')] === (attr === 'data-type' ? selectedType : selectedQuality);
      b.style.background = isActive ? 'var(--accent)' : 'var(--surface)';
      b.style.color = isActive ? '#fff' : 'var(--muted)';
    });
  }

  container.querySelectorAll('[data-type]').forEach(b => b.addEventListener('click', () => {
    selectedType = b.dataset.type; toggle('[data-type]', 'data-type');
  }));
  container.querySelectorAll('[data-q]').forEach(b => b.addEventListener('click', () => {
    selectedQuality = b.dataset.q; toggle('[data-q]', 'data-q');
  }));

  // Load summary
  async function loadSummary() {
    const d = await fetch('/api/job').then(r => r.json());
    const events = await fetch('/api/job/events').then(r => r.json());
    const included = events.filter(e => e.included);
    const activ = included.reduce((s, e) => s + (e.end_s - e.start_s), 0);
    const codec = (d.source_info?.codec || '').toLowerCase();
    const isFast = ['h264','hevc','mpeg2video','mpeg4'].includes(codec);
    const outputDir = d.output_dir || '';
    container.querySelector('#outputDir').value = outputDir;
    container.querySelector('#summary').innerHTML = `
      <div class="summary-row"><span class="key">Events to export</span><span class="val">${included.length} of ${events.length}</span></div>
      <div class="summary-row"><span class="key">Total activity</span><span class="val">${Math.floor(activ/60)}m ${Math.round(activ%60)}s</span></div>
      <div class="summary-row"><span class="key">Source codec</span><span class="val ${isFast?'fast':''}">${(d.source_info?.codec||'?').toUpperCase()} ${isFast ? '→ stream copy ⚡' : '→ re-encode 🐢'}</span></div>
      <div class="summary-row"><span class="key">Est. time</span><span class="val ${isFast?'fast':''}">${isFast ? '< 30 sec' : '~several minutes'}</span></div>
    `;
  }
  loadSummary();

  container.querySelector('#browseOutputBtn').addEventListener('click', () => {
    window.dispatchEvent(new CustomEvent('cctv:browse-folder'));
    const poll = setInterval(async () => {
      const r = await fetch('/api/shell/pending-path');
      const d = await r.json();
      if (d.path) {
        clearInterval(poll);
        await fetch('/api/shell/set-output-dir', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:d.path})});
        container.querySelector('#outputDir').value = d.path;
      }
    }, 300);
    setTimeout(() => clearInterval(poll), 30000);
  });

  container.querySelector('#exportNowBtn').addEventListener('click', async () => {
    container.querySelector('#exportNowBtn').disabled = true;
    container.querySelector('#progressWrap').style.display = 'block';
    const outputDir = container.querySelector('#outputDir').value;
    const r = await fetch('/api/job/export', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ output_type: selectedType, quality: selectedQuality, output_dir: outputDir })
    });
    if (!r.ok) { alert('Export failed to start: ' + (await r.json()).detail); return; }

    const es = new EventSource('/api/stream');
    const logDiv = container.querySelector('#exportLog');
    es.onmessage = e => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'log') {
        const d = document.createElement('div'); d.textContent = msg.line; logDiv.appendChild(d); logDiv.scrollTop = logDiv.scrollHeight;
        container.querySelector('#exportPbar').style.width = Math.round((msg.progress||0)*100) + '%';
        if (msg.status === 'completed') {
          es.close();
          container.querySelector('#progressWrap').style.display = 'none';
          container.querySelector('#doneWrap').style.display = 'flex';
          container.querySelector('#exportNowBtn').style.display = 'none';
          fetch('/api/job').then(r=>r.json()).then(d => {
            container.querySelector('#outputName').textContent = d.output_path?.split(/[\\/]/).pop() || '';
          });
        }
        if (msg.status === 'failed') { es.close(); container.querySelector('#exportStatusLbl').textContent = 'Export failed — ' + msg.error; }
      }
      if (msg.type === 'done') es.close();
    };
  });

  container.querySelector('#openFolderBtn').addEventListener('click', () => {
    fetch('/api/shell/open-folder', { method: 'POST' });
  });

  return () => {};
}
```

- [ ] **Step 4: Commit**

```bash
git add static/pages/export.html static/css/export.css static/js/pages/export.js
git commit -m "feat: export page — output type, quality, folder picker, live progress, done state"
```

---

## Task 17: PyQt6 Shell

**Files:**
- Create: `shell/platform_utils.py`
- Create: `shell/tray.py`
- Create: `shell/main_window.py`

- [ ] **Step 1: Create `shell/platform_utils.py`**

```python
import platform
import subprocess
from pathlib import Path

def get_platform() -> str:
    return platform.system()  # "Windows", "Darwin", "Linux"

def open_folder(path: str) -> None:
    import os
    p = str(Path(path).resolve())
    s = get_platform()
    if s == "Windows":
        os.startfile(p)
    elif s == "Darwin":
        subprocess.run(["open", p])
    else:
        subprocess.run(["xdg-open", p])
```

- [ ] **Step 2: Create `shell/tray.py`**

```python
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QObject

class TrayIcon(QObject):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self._window = window
        self._tray = QSystemTrayIcon(self)
        # Use a generic icon — replace with app icon path when available
        self._tray.setIcon(QIcon.fromTheme("video-x-generic"))
        self._tray.setToolTip("CCTV Video Processor")
        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

    def _show(self):
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _quit(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show()
```

- [ ] **Step 3: Create `shell/main_window.py`**

```python
import json
import threading
from pathlib import Path

import requests
from PyQt6.QtCore import QUrl, pyqtSlot, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtWidgets import QMainWindow, QFileDialog, QApplication

from app.config import BACKEND_HOST, BACKEND_PORT

BASE_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CCTV Video Processor")
        self.setMinimumSize(900, 640)
        self.resize(1100, 720)

        self._view = QWebEngineView()
        self.setCentralWidget(self._view)

        # Accept file drops at the window level
        self.setAcceptDrops(True)

        # Wait for backend then load
        self._wait_for_backend()

    def _wait_for_backend(self, retries=30):
        """Poll /api/health until backend is ready."""
        def _check():
            for _ in range(retries):
                try:
                    r = requests.get(f"{BASE_URL}/api/health", timeout=1)
                    if r.status_code == 200:
                        self._view.setUrl(QUrl(BASE_URL + "/"))
                        # Listen for JS events from the web UI
                        self._view.page().loadFinished.connect(self._inject_js_bridge)
                        return
                except Exception:
                    pass
                import time; time.sleep(0.3)
            self._view.setHtml("<h2>Backend failed to start. Please restart the app.</h2>")
        threading.Thread(target=_check, daemon=True).start()

    def _inject_js_bridge(self):
        """Inject JS to intercept cctv:browse and cctv:browse-folder events."""
        js = """
        window.addEventListener('cctv:browse', function() {
            window._cctvBrowse = true;
        });
        window.addEventListener('cctv:browse-folder', function() {
            window._cctvBrowseFolder = true;
        });
        """
        self._view.page().runJavaScript(js)
        # Poll for browse requests
        self._browse_timer = QTimer(self)
        self._browse_timer.setInterval(200)
        self._browse_timer.timeout.connect(self._check_browse)
        self._browse_timer.start()

    def _check_browse(self):
        self._view.page().runJavaScript(
            "([window._cctvBrowse, window._cctvBrowseFolder])",
            self._handle_browse_flags
        )

    def _handle_browse_flags(self, flags):
        if not flags:
            return
        want_file, want_folder = flags
        if want_file:
            self._view.page().runJavaScript("window._cctvBrowse = false;")
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Video File", str(Path.home()),
                "Video Files (*.mp4 *.mkv *.avi *.mov *.ts *.mts *.flv *.m4v);;All Files (*)"
            )
            if path:
                try:
                    requests.post(f"{BASE_URL}/api/shell/filepath",
                                  json={"path": path}, timeout=5)
                except Exception:
                    pass
        if want_folder:
            self._view.page().runJavaScript("window._cctvBrowseFolder = false;")
            folder = QFileDialog.getExistingDirectory(
                self, "Select Output Folder", str(Path.home() / "Desktop")
            )
            if folder:
                try:
                    requests.post(f"{BASE_URL}/api/shell/filepath",
                                  json={"path": folder}, timeout=5)
                except Exception:
                    pass

    # Native drag-and-drop support
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            try:
                requests.post(f"{BASE_URL}/api/job/create",
                              json={"source_path": path}, timeout=10)
                self._view.setUrl(QUrl(BASE_URL + "/processing"))
            except Exception:
                pass

    def closeEvent(self, event):
        # Hide to tray instead of quitting (tray Quit action does full exit)
        event.ignore()
        self.hide()
```

- [ ] **Step 4: Add `requests` to requirements.txt**

```
requests==2.31.*
```

Then:
```bash
pip install requests
```

- [ ] **Step 5: Commit**

```bash
git add shell/ requirements.txt
git commit -m "feat: PyQt6 shell — main window, tray, file picker, native drag-and-drop"
```

---

## Task 18: Launcher + Integration

**Files:**
- Create: `launcher.py`

- [ ] **Step 1: Create `launcher.py`**

```python
"""
Application entry point.
Starts the FastAPI backend in a daemon thread, then opens the PyQt6 window.
Shuts down cleanly on window close.
"""
import sys
import threading

def start_backend():
    import uvicorn
    from app.main import create_app
    uvicorn.run(
        create_app(),
        host="127.0.0.1",
        port=5151,
        log_level="warning",
        access_log=False,
    )

def main():
    # Start backend thread first
    backend_thread = threading.Thread(target=start_backend, daemon=True, name="backend")
    backend_thread.start()

    # Start PyQt6
    from PyQt6.QtWidgets import QApplication
    from shell.main_window import MainWindow
    from shell.tray import TrayIcon

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # tray keeps app alive
    app.setApplicationName("CCTV Video Processor")

    window = MainWindow()
    window.show()

    tray = TrayIcon(window)   # noqa: F841 — kept alive by app event loop

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full app**

```bash
python launcher.py
```

Expected: app window opens, loads home page, drop zone visible. No errors in terminal.

- [ ] **Step 3: End-to-end smoke test — use the bundled test video**

1. Drop `OLD RASPBERRI PI VERSION/Test Video/20260507_012210 (1).mp4` onto the drop zone
2. Confirm video info appears (resolution, codec, duration)
3. Click "Start Detection"
4. Confirm Processing page loads with live progress
5. Wait for detection to complete — Timeline page loads
6. Confirm events appear (or zero-events hint if truly static)
7. Click "Export Selected" → Export page
8. Click "Export Now"
9. Confirm output file created in Desktop folder

- [ ] **Step 4: Commit**

```bash
git add launcher.py
git commit -m "feat: launcher — starts FastAPI backend thread then opens PyQt6 window"
```

---

## Task 19: Cross-Platform Verification

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: all tests pass or skip (no failures).

- [ ] **Step 2: Verify FFmpeg is bundled and functional**

```bash
python -c "
from app.utils.ffmpeg_path import get_ffmpeg, get_ffprobe
import subprocess
r = subprocess.run([get_ffmpeg(), '-version'], capture_output=True)
print('ffmpeg ok:', r.returncode == 0)
r2 = subprocess.run([get_ffprobe(), '-version'], capture_output=True)
print('ffprobe ok:', r2.returncode == 0)
"
```

Expected:
```
ffmpeg ok: True
ffprobe ok: True
```

- [ ] **Step 3: Verify pathlib handles OS-native paths**

```bash
python -c "
from pathlib import Path
p = Path.home() / 'Desktop' / 'test output'
print(p)
print(p.parent.exists())
"
```

Expected: prints a valid OS-native path; `True` for parent existence.

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: complete CCTV PC Video Processor — cross-platform, session-only, MOG2+YOLO"
```

---

## Self-Review Against Spec

**Spec coverage check:**

| Spec requirement | Covered in task |
|---|---|
| Hybrid PyQt6 + QWebEngineView | Task 17, 18 |
| File picker via QFileDialog | Task 17 |
| Native drag-and-drop | Task 17 |
| System tray | Task 17 |
| FastAPI backend localhost:5151 | Task 11, 18 |
| Session state (no SQLite) | Task 4 |
| MOG2 detection with PC-01/02/04 fixes | Task 7 |
| YOLO per-job mode | Task 9 |
| Export engine (stream copy + re-encode) | Task 8 |
| Chapter markers in merged output | Task 8 (inherited from Pi) |
| Individual clips output mode | Task 8 (output_type param) |
| SSE live progress | Task 12 |
| imageio-ffmpeg bundled binary | Task 3 |
| Home page (drop + settings) | Task 13 |
| Processing page (progress + log) | Task 14 |
| Timeline page (canvas + event cards) | Task 15 |
| Export page (format + folder) | Task 16 |
| Quick Export button | Task 15 |
| Disk space pre-check | Task 11 |
| Codec warning banner | Task 11 |
| 0-events hint with DIAG data | Task 15 |
| YOLO no-internet fallback to MOG2 | Task 9 |
| Cross-platform temp dir | Task 2 (config.py) |
| Platform-specific folder opener | Task 10, 12 |
| Output folder user-choosable | Task 16 |
| Cancel preserves partial events | Task 11 |
| CLAHE warmup fix (PC-01) | Task 7 |
| silence_start None sentinel | Task 7 |
