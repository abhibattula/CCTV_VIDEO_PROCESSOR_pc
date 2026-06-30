# Phase 11 — AI Fix, Performance & Cross-Platform Design

**Date:** 2026-06-30  
**Branch:** `011-ai-fix-perf-platform` off `master`  
**Goal:** Stabilise the existing app — fix AI garbage output, eliminate detection slowness, and make the full app run correctly on Windows, macOS, Linux desktop, Linux headless, and Raspberry Pi (2 GB / 4 GB).

---

## Scope

No new user-facing features. No new API endpoints. No new dependencies. Three parallel tracks:

| Track | What it fixes |
|-------|--------------|
| **Fix** | Florence-2 raw-token garbage, terminal error noise, log panel disappearing |
| **Performance** | YOLO cold-start lag, frame-processing speed, frozen progress bar |
| **Platform** | Mac/Linux/Pi support, AI auto-disable on low RAM, QSystemTray on GNOME |

---

## Architecture

```
011-ai-fix-perf-platform
│
├── Track 1 · Fix
│   ├── Florence-2 garbage output  → app/core/frame_analyzer.py
│   ├── Terminal error noise       → app/core/frame_analyzer.py
│   └── Log panel drops logs       → log_buffer.py + stream.py + processing.js
│
├── Track 2 · Performance
│   ├── YOLO cold-start lag        → app/core/yolo_detector.py
│   ├── Frame-skip (YOLO)          → app/core/yolo_detector.py + config.py
│   ├── Frozen progress bar        → detection_engine.py + yolo_detector.py
│   └── Pi-adaptive batch size     → app/config.py
│
└── Track 3 · Platform
    ├── Canonical get_desktop_path → app/utils/platform.py (new)
    ├── AI auto-disable ≤4 GB      → config.py + frame_analyzer.py
    ├── QSystemTray guard GNOME    → shell/main_window.py
    ├── Comment fix                → launcher.py
    └── Multi-platform README      → README.md
```

---

## Track 1: Fix

### 1A — Florence-2 Garbage Output

**Root causes (all three present simultaneously):**

1. **Manual image squaring adds 44% black padding.**  
   Lines 142–146 of `frame_analyzer.py` pad a 1920×1080 frame to 1920×1920 with black pixels before passing it to Florence-2. The AutoProcessor resizes this to 768×768, preserving all the black. The model describes darkness. Fix: delete these five lines entirely. The AutoProcessor handles aspect-ratio resizing internally — no manual squaring needed.

2. **`post_process_generation` leaks special tokens in transformers 5.x.**  
   The Florence-2 custom post-processor (loaded via `trust_remote_code`) returns caption values that still contain `</s>`, `<s>`, `<pad>`, and `<loc_NNN>` tokens. Fix: add a module-level sanitiser applied to every string extracted from the result dict:
   ```python
   _SPECIAL_TOKEN_RE = re.compile(r'</s>|<s>|<pad>|<loc_\d+>')
   
   def _clean_caption(text: str) -> str:
       return _SPECIAL_TOKEN_RE.sub('', text or '').strip()
   ```
   Applied at: `caption`, `object_caption`, and each detection label before they are stored.

3. **`max_new_tokens=64` causes mid-token truncation.**  
   64 tokens ≈ 48 words. When generation truncates mid-token, the partial fragment (`<loc_12`) is not parseable by the post-processor and leaks through. Fix: raise to `max_new_tokens=150`. At `num_beams=1` on CPU this stays within the existing 90-second task timeout.

**Files changed:** `app/core/frame_analyzer.py` only.

---

### 1B — Terminal Error Noise

Phase 9 suppressed MISSING-key weight tables and `FutureWarning` during **model loading**. Inference calls inside `_run_task()` are unguarded and emit `UserWarning` (torch), `DeprecationWarning` (numpy, PIL), and hub download notices.

Fix: wrap each of the three `_run_in_daemon(lambda: _run_task(...), ...)` call-sites in a `warnings.catch_warnings()` context (inside the lambda, not around the daemon call itself), suppressing:
- `UserWarning` from `torch` and `transformers`
- `DeprecationWarning` from `numpy`, `PIL`

The existing model-load suppression block (around `from_pretrained` calls) is left unchanged. `RuntimeError` and `ValueError` are explicitly **not** suppressed — those are genuine inference failures that belong in the log.

**Files changed:** `app/core/frame_analyzer.py` only.

---

### 1C — Log Panel Drops Logs on SSE Reconnect

**Root cause:** When the SSE stream disconnects (tab switch, brief network blip, Pi WiFi hiccup), the subscriber is removed from `LogBuffer`. On reconnect, a new subscriber is created but receives only future messages — all logs emitted during the disconnect are lost. The panel appears blank or frozen.

**Fix — three-part:**

1. **`LogBuffer.snapshot()` method** — returns all entries currently in the ring buffer as a list, in order. Called once per new subscriber to replay missed messages.

2. **`stream.py` SSE endpoint** — on each new subscriber connection, flush `snapshot()` entries as `data:` lines before entering the live-stream loop. Existing SSE format (JSON per line) is unchanged.

3. **Frontend auto-reconnect** (`static/js/pages/processing.js`) — replace bare `new EventSource(url)` with a thin wrapper that:
   - Listens for `onerror`
   - Waits 3 seconds, then creates a new `EventSource`
   - Stops retrying after 5 consecutive failures (shows "Connection lost" message)

The same reconnect wrapper applies to the log panel SSE stream — one implementation covers both.

**Files changed:** `app/core/log_buffer.py`, `app/api/stream.py`, `static/js/pages/processing.js`.

---

## Track 2: Performance

### 2A — YOLO Cold-Start Lag

YOLO loads model weights when `Start` is clicked — 5–10 s on PC, 20–40 s on Pi. The UI appears frozen.

**Fix — eager background warm-up:**  
When `POST /api/job/create` succeeds (file loaded, not yet started), fire a daemon thread that imports ultralytics and loads the model into a module-level cache. A `threading.Event` (`_model_ready`) signals completion. If the user clicks Start before warm-up completes, the detection thread waits on `_model_ready` (with a 60 s timeout) rather than loading cold.

If ultralytics is not installed, the warm-up thread is not started (guarded by `HAS_ULTRALYTICS` check).

**Files changed:** `app/core/yolo_detector.py`, `app/api/job.py` (trigger warm-up after create).

---

### 2B — YOLO Processes Every Frame

YOLO runs inference on every frame — 60 inferences/second of video on a 60 fps source. CPU throughput is ~0.5–2 fps, making a 2-minute clip take 60+ minutes.

**Fix — configurable frame skip:**

```python
# config.py
YOLO_FRAME_SKIP: int = 6 if IS_PI else 3
```

Inside `yolo_detector.run()`, only process frames where `frame_count % YOLO_FRAME_SKIP == 0`. The existing event-merging logic accumulates across frames, so events are still captured correctly — a person walking across frame is not missed because one frame is skipped.

**Files changed:** `app/config.py`, `app/core/yolo_detector.py`.

---

### 2C — Frozen Progress Bar (Batch-Size Bottleneck)

`BATCH_SIZE=500` means the progress callback fires every 500 frames — 8+ seconds at 60 fps with no UI movement. On Pi at slower processing, even longer.

**Fix — time-based dual trigger:**

```python
_last_cb = time.monotonic()
# inside detection loop:
elapsed = time.monotonic() - _last_cb
if frame_count % BATCH_SIZE == 0 or elapsed >= 2.0:
    on_progress(frame_count / total_frames)
    _last_cb = time.monotonic()
```

Progress now fires at least every 2 seconds regardless of batch size. Same pattern added to `yolo_detector.py`.

**Files changed:** `app/core/detection_engine.py`, `app/core/yolo_detector.py`.

---

### 2D — Pi-Adaptive Batch Size

```python
# config.py
BATCH_SIZE: int = 100 if IS_PI else 500
```

Smaller batches on Pi mean more frequent RAM-guard checks and more responsive cancellation. Combined with the 2-second timer above, progress is smooth even at low frame rates.

**Files changed:** `app/config.py`.

---

## Track 3: Platform

### 3A — Canonical `get_desktop_path()` (`app/utils/platform.py` — new file)

`_get_desktop_path()` is duplicated verbatim in `shell/main_window.py` and `app/api/job.py`. Move to a single canonical location with Linux/Pi awareness:

```python
def get_desktop_path() -> str:
    system = platform.system()
    if system == "Windows":
        # SHGetFolderPathW handles OneDrive Desktop Folder Backup
        try:
            import ctypes, ctypes.wintypes
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(0, 0, 0, 0, buf)
            if buf.value:
                return buf.value
        except Exception:
            pass
    elif system == "Darwin":
        return str(Path.home() / "Desktop")
    else:  # Linux, Pi
        xdg = os.environ.get("XDG_DESKTOP_DIR", "").strip()
        if xdg and Path(xdg).is_dir():
            return xdg
        desktop = Path.home() / "Desktop"
        if desktop.is_dir():
            return str(desktop)
        downloads = Path.home() / "Downloads"
        return str(downloads if downloads.is_dir() else Path.home())
```

Both callers import `from app.utils.platform import get_desktop_path`. Their local definitions are deleted.

**Files changed:** `app/utils/platform.py` (new), `shell/main_window.py`, `app/api/job.py`.

---

### 3B — AI Auto-Disable on Low-RAM Devices

Florence-2 needs ~3 GB RAM. On a 2 GB Pi it would crash the OS; on a 4 GB Pi it leaves under 1 GB for Qt + backend + OS.

```python
# config.py
AI_FEATURES_ENABLED: bool = _total_gb >= 5.0
```

```python
# frame_analyzer.py — is_available() first check
from app.config import AI_FEATURES_ENABLED

@classmethod
def is_available(cls) -> bool:
    if not AI_FEATURES_ENABLED:
        cls._availability_cache = False
        return False
    # ... existing logic unchanged
```

The `/api/system/capabilities` endpoint already surfaces `florence2_available` — it will now return `false` on Pi, and the frontend's existing capability-check pattern will show the feature as unavailable with no code changes needed in the UI.

**Files changed:** `app/config.py`, `app/core/frame_analyzer.py`.

---

### 3C — QSystemTray Guard for GNOME/Wayland

On GNOME 3/4, `QSystemTrayIcon.isVisible()` always returns `False`. The close-to-tray feature silently fails — an active job is lost instead of minimised.

```python
# shell/main_window.py __init__
self._tray_available = QSystemTrayIcon.isSystemTrayAvailable()

# closeEvent
if active_job and self._tray_available and tray and tray.isVisible():
    self.hide()
    event.ignore()
else:
    QApplication.instance().quit()
```

**Files changed:** `shell/main_window.py`.

---

### 3D — Comment Fix and `import os` Cleanup

- `launcher.py` line 111: `# Handle Ctrl+C on Windows` → `# Handle Ctrl+C — Qt blocks Python SIGINT on all platforms without this dummy timer`
- `app/api/job.py`: `import os` inside `export_job()` function body → moved to top-level imports

**Files changed:** `launcher.py`, `app/api/job.py`.

---

### 3E — Multi-Platform Installation Guide (`README.md`)

Four new sections added under a `## Installation by Platform` heading:

**macOS (Intel + Apple Silicon)**
- `pip install -r requirements.txt` works as-is
- `imageio-ffmpeg` bundles a universal binary — no Homebrew needed
- All packages have native ARM64 wheels for M-series

**Linux Desktop (Ubuntu 22.04+ / Fedora)**
- Prerequisites: `sudo apt install libgl1-mesa-glx libglib2.0-0`
- Wayland: `export QT_QPA_PLATFORM=xcb` before launching
- GNOME system tray note (close-to-tray not available on GNOME without libappindicator)

**Raspberry Pi (64-bit OS Bookworm, Pi 4 / Pi 5)**
- Prerequisites: `sudo apt install libgl1-mesa-glx libglib2.0-0 libwebp7`
- Install order: `pip install opencv-python-headless` first, then `pip install -r requirements.txt`
- AI Analysis auto-disabled on ≤4 GB RAM (Florence-2 cannot run safely)
- YOLO frame-skip auto-enabled (`config.YOLO_FRAME_SKIP=6`)
- Expected performance: MOG2 detection ~8–15 fps at 320×180 on Pi 4; ~15–25 fps on Pi 5

**Linux Headless / Server**
- Run backend only: `uvicorn app.main:app --host 0.0.0.0 --port 5151`
- Access UI from another device's browser at `http://<device-ip>:5151`
- PyQt6 and PyQt6-WebEngine not required in headless mode

---

## Complete File Change Surface

| File | Track | Type | Change summary |
|------|-------|------|---------------|
| `app/core/frame_analyzer.py` | Fix | Modify | Remove squaring, add sanitiser, raise max_new_tokens, suppress inference warnings, add AI_FEATURES_ENABLED gate |
| `app/core/log_buffer.py` | Fix | Modify | Add `snapshot()` method |
| `app/api/stream.py` | Fix | Modify | Flush snapshot to new SSE subscribers |
| `static/js/pages/processing.js` | Fix + Perf | Modify | SSE auto-reconnect wrapper |
| `app/core/yolo_detector.py` | Perf | Modify | Frame skip, eager warm-up thread, time-based progress |
| `app/core/detection_engine.py` | Perf | Modify | Time-based progress callbacks |
| `app/config.py` | Perf + Platform | Modify | `YOLO_FRAME_SKIP`, adaptive `BATCH_SIZE`, `AI_FEATURES_ENABLED` |
| `app/api/job.py` | Perf + Platform | Modify | Trigger YOLO warm-up after create; remove local `_get_desktop_path()`; move `import os` |
| `app/utils/platform.py` | Platform | **New** | Canonical `get_desktop_path()` |
| `shell/main_window.py` | Platform | Modify | Remove local `_get_desktop_path()`, import from platform.py; add tray guard |
| `launcher.py` | Platform | Modify | Fix comment |
| `README.md` | Platform | Modify | Multi-platform install guide |
| `tests/test_frame_analyzer.py` | All | **New** | Sanitiser unit tests; squaring-removal tests; AI_FEATURES_ENABLED gate test |

---

## Verification Checklist

1. **Florence-2 fix**: Generate Intelligence Report → captions contain readable English, no `</s>`, `<loc_NNN>`, `<s>` tokens.
2. **Terminal noise**: Run AI report generation → terminal shows zero `UserWarning`/`DeprecationWarning` lines from torch/numpy/PIL.
3. **Log panel**: Switch to another browser tab during detection, switch back → log entries resume; no gap in log sequence.
4. **YOLO warm-up**: Load a video file → click Start immediately → YOLO detection begins in <2 s (warm model already cached).
5. **Progress bar**: Run MOG2 on a 60 fps video → progress bar moves at least every 2 seconds.
6. **Pi AI gate**: On a machine with <5 GB RAM (simulate with `_total_gb = 3.0` in config): `FrameAnalyzer.is_available()` returns False; `/api/system/capabilities` shows `florence2_available: false`.
7. **Desktop path**: On Linux without `~/Desktop`: `get_desktop_path()` returns `$XDG_DESKTOP_DIR` if set, else `~/Downloads`, else `~/`.
8. **Tests**: `pytest tests/ -v` → ≥195 passed (193 prior + 2+ new frame_analyzer tests), 0 new failures.

---

## Constraints

- No new pip dependencies added to `requirements.txt`
- No new API endpoints
- No changes to the web UI page structure
- `trust_remote_code=True` authorised only for `microsoft/Florence-2-base` (unchanged)
- All tests must run without real video file, GPU, or display server
