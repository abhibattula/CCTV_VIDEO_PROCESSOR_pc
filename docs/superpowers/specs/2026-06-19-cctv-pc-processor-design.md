# CCTV Video Processor — PC Edition — Design Spec

**Date:** 2026-06-19  
**Status:** Approved  
**Platform:** Windows / macOS / Linux (any PC with Python 3.11+)

---

## 1. What It Does

A cross-platform desktop application that takes a CCTV recording, finds every moment something moved, lets the user review those moments on an interactive timeline, and exports only the active clips as a single merged MP4 (or individual files) — eliminating hours of dead footage in seconds.

**Core loop:**
1. User drops a video file onto the app
2. Detection engine scans for motion events
3. User optionally reviews the timeline and excludes false positives
4. Export produces a clean output file containing only the active portions

---

## 2. Decisions Made

| Question | Decision | Reason |
|---|---|---|
| UI paradigm | Hybrid: PyQt6 shell + QWebEngineView | Rich HTML/CSS/JS UI inside a native window — no browser required, drag-and-drop works, system tray works |
| Workflow | Quick Export + Review Timeline modes | Quick for routine days; review when something important happened |
| Input | Single file at a time | Keeps UX focused; no batch complexity |
| Detection | MOG2 (default, fast) + YOLO (optional, smart) — user chooses per job | Flexibility without forcing everyone to wait for YOLO |
| Output | User chooses: single merged MP4 or individual clips per export | Default merged, toggle for individual |
| Persistence | Session-only (no database) | Clean slate each launch; no history clutter |
| Architecture | FastAPI backend (port from Pi) + in-memory session state | Reuses battle-tested detection pipeline; 17 known bugs already fixed |

---

## 3. Architecture

```
User (Windows / macOS / Linux)
        │
        ▼ launches
┌─────────────────────────────────────────────────────┐
│  PyQt6 Shell                                        │
│  ├── QWebEngineView  → localhost:5151 (web UI)      │
│  ├── QFileDialog     → native OS file picker        │
│  ├── QSystemTrayIcon → processing in background     │
│  └── drag-and-drop   → intercepted, path forwarded  │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (localhost only)
        ┌──────────────▼──────────────┐
        │  FastAPI Backend            │
        │  (uvicorn, 1 worker,        │
        │   localhost:5151)           │
        │                             │
        │  Session State (RAM dict)   │
        │  REST API + SSE endpoint    │
        └──────────┬──────────────────┘
                   │
        ┌──────────▼──────────────────┐
        │  Background Worker Thread   │
        │  ├── MOG2 Detector          │
        │  ├── YOLO Detector          │
        │  └── FFmpeg Export Engine   │
        └─────────────────────────────┘
```

**Key constraint:** The FastAPI server binds to `127.0.0.1:5151` only — never exposed on the network. The PyQt6 shell starts uvicorn as a background thread at launch and shuts it down on close.

---

## 4. Component Inventory

### 4.1 PyQt6 Shell (`launcher.py` + `shell/`)

| Responsibility | Implementation |
|---|---|
| Main window | `QMainWindow` with `QWebEngineView` filling the entire client area |
| Start backend | `threading.Thread` runs `uvicorn.run(app, host="127.0.0.1", port=5151)` |
| File picker | `QFileDialog.getOpenFileName()` with video format filter; result posted to `/api/job/create` |
| Drag and drop | Override `dragEnterEvent` / `dropEvent` on `QWebEngineView`; forward file path to backend |
| System tray | `QSystemTrayIcon` — shows when minimised; double-click restores; right-click menu: Show / Cancel / Quit |
| Open output folder | Platform-specific: `explorer` (Win) / `open` (mac) / `xdg-open` (Linux) |
| JS → Python bridge | `QWebEnginePage.runJavaScript()` for file picker trigger; result sent back via `/api/shell/filepath` |
| Window title | Updates dynamically: "Detecting… 63%" / "14 events found" / "Export complete" |

### 4.2 FastAPI Backend (`app/`)

Ported from the Pi version. Removed: SQLite, upload API, file browser API, PWA/HTTPS, audit log, analytics, PDF reports, system temperature. Added: session state manager, callback-based detection, YOLO dispatcher, output folder setting.

**API surface:**

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/job/create` | Validate file, create session job, return job_id + warnings |
| GET | `/api/job` | Return current session job state |
| POST | `/api/job/start` | Start detection in background thread |
| POST | `/api/job/cancel` | Set cancel event; preserve partial events |
| GET | `/api/job/events` | Return events list with included flags |
| PUT | `/api/job/events/{idx}/toggle` | Toggle included/excluded for one event |
| POST | `/api/job/preview/{idx}` | Extract 10s temp clip; return URL |
| POST | `/api/job/export` | Run FFmpeg export; return output path |
| GET | `/api/stream` | SSE — live log lines + progress + event count |
| POST | `/api/shell/filepath` | Receives file path from PyQt6 shell |
| GET | `/api/health` | Returns `{"status":"ok"}` — used by shell to confirm startup |

### 4.3 Session State (`app/session.py`)

Replaces SQLite entirely. One Python dict protected by `threading.RLock()`.

```python
SESSION = {
    "job_id":      str,           # uuid4
    "status":      str,           # idle | detecting | completed | exporting | failed | cancelled
    "source_path": Path,          # absolute path to source video
    "source_info": dict,          # codec, fps, width, height, duration_s, has_audio, needs_reencode
    "settings":    dict,          # sensitivity, mode, padding_s, min_gap_s, min_event_s
    "progress":    float,         # 0.0 → 1.0
    "events":      list[dict],    # {start_s, end_s, peak_score, included, label}
    "output_path": Path | None,   # set after export
    "output_dir":  Path,          # user-chosen destination folder
    "error":       str | None,    # human-readable error if status == "failed"
}
```

Thread safety: all writes go through `session.update(**kwargs)` which acquires the lock. Reads use `session.snapshot()` which returns a deep copy.

### 4.4 Detection Engine (`app/core/detection_engine.py`)

Ported from Pi with the following changes:

| Change | Detail |
|---|---|
| **PC-01 fix** | CLAHE applied during warmup when `sensitivity == "high"` — warmup and main loop now use identical preprocessing |
| **PC-02 fix** | SQLite removed; replaced with `on_progress(pct: float)` and `on_event(ev: dict)` callbacks passed at call time |
| **PC-04 fix** | Default detection resolution `640×360` (up from `320×240`); auto-scales down if RAM < 4 GB |
| **PC-06 fix** | `mode` parameter (`"mog2"` or `"yolo"`) replaces global `ENABLE_YOLO` flag |
| **silence_start** | Changed from `0.0` float sentinel to `Optional[float] = None` (cleaner, eliminates edge case) |
| Checkpoint | Retained as JSON file in temp dir — crash recovery still works |

Detection resolution selection:
```
Available RAM ≥ 8 GB  → 640×360
Available RAM 4–8 GB  → 480×270
Available RAM < 4 GB  → 320×180
```

### 4.5 YOLO Detector (`app/core/yolo_detector.py`)

New module. Wraps `ultralytics.YOLO("yolov8n.pt")`.

- Model auto-downloaded on first use to `~/.cctv_processor/models/`
- Runs on CPU by default; uses GPU if `torch.cuda.is_available()`
- Labels detected: Person, Vehicle, Animal (maps from YOLO class IDs)
- Events tagged with detected labels — shown in event cards on the timeline
- Falls back to MOG2 if ultralytics is not installed (with a one-time install prompt)

### 4.6 Export Engine (`app/core/export_engine.py`)

Identical to Pi version. No changes needed — all fixes already in place:
- `-fflags +genpts+igndts` on all segment extractions
- `-avoid_negative_ts make_zero`
- `-movflags faststart` on output
- Stream copy for H.264/HEVC; re-encode for others
- Chapter markers in merged output
- Individual clips mode: each event saved as `{source_stem}_event_{N:03d}_{timestamp}.mp4`

### 4.7 FFmpeg Bundling (`app/utils/ffmpeg_path.py`)

```python
def get_ffmpeg() -> str:
    """Return absolute path to ffmpeg binary. Never fails silently."""
    import imageio_ffmpeg
    path = imageio_ffmpeg.get_ffmpeg_exe()
    if not Path(path).exists():
        raise RuntimeError("Bundled ffmpeg not found. Reinstall the app.")
    return path
```

All subprocess calls use `get_ffmpeg()` instead of the bare string `"ffmpeg"`. This means the app works on a machine with no system FFmpeg installed.

### 4.8 Web Frontend (`static/`)

Ported from Pi version. Removed pages: History, Settings, System, Audit, Reports. Kept and redesigned: Home (was New Job), Processing (was Job Detail), Timeline (was Timeline), Export.

Design system: dark theme (`#0d1117` background, `#e6edf3` text, `#1f6feb` accent, `#238636` success, `#da3633` error) — matches the approved mockups.

---

## 5. Bugs Fixed vs Pi Version

All 7 PC-specific issues identified in the audit are fixed:

| ID | Issue | Fix |
|---|---|---|
| PC-01 | CLAHE warmup/detection mismatch at high sensitivity | Apply CLAHE during warmup when `sensitivity == "high"` |
| PC-02 | SQLite hardwired in detection loop | Callback injection: `on_progress`, `on_event` |
| PC-03 | Chunked HTTP upload (Pi-only) | Native file picker via `QFileDialog`; local path only |
| PC-04 | Detection resolution 320×240 (Pi RAM limit) | Auto-scale: 640×360 default on PC |
| PC-05 | File browser browses Linux paths | Removed; replaced by native OS dialog |
| PC-06 | YOLO globally disabled | Per-job `mode` setting: `"mog2"` or `"yolo"` |
| PC-07 | Output folder hardcoded to `./outputs/` | User-choosable via `QFileDialog.getExistingDirectory()` |

All 17 original Pi issues and all 9 detection bugs remain fixed (inherited from Pi version).

---

## 6. Cross-Platform Matrix

| Concern | Windows | macOS | Linux |
|---|---|---|---|
| FFmpeg | `imageio-ffmpeg` bundled `.exe` | `imageio-ffmpeg` bundled binary | `imageio-ffmpeg` bundled binary |
| File paths | `pathlib.Path` (handles `\` automatically) | `pathlib.Path` | `pathlib.Path` |
| Temp dir | `tempfile.gettempdir()` | same | same |
| CPU temp | N/A → shows "N/A" | `smc` subprocess | `/sys/class/thermal/thermal_zone0/temp` |
| File picker | `QFileDialog` → Windows Open dialog | `QFileDialog` → macOS sheet | `QFileDialog` → GTK/KDE dialog |
| Open output folder | `subprocess.run(["explorer", path])` | `subprocess.run(["open", path])` | `subprocess.run(["xdg-open", path])` |
| App launch | `python launcher.py` or `.exe` (PyInstaller) | `python launcher.py` or `.app` | `python launcher.py` or `.AppImage` |
| YOLO model cache | `%USERPROFILE%\.cctv_processor\models\` | `~/.cctv_processor/models/` | `~/.cctv_processor/models/` |

---

## 7. UI Flow

```
[Home]
  File drop / Browse → settings panel (mode, sensitivity, padding, min duration)
  → ffprobe validation → warnings if any → Start Detection button

[Processing]
  Live progress bar (0→100%) · ETA · CPU % · event counter
  Scrolling log (SSE) · Cancel button
  → auto-navigates to Timeline on completion

[Timeline]
  Summary bar (source duration, events found, activity %) 
  Full-width canvas strip · Blue = included · Grey = excluded
  Event cards (thumbnail preview, timestamp, duration, peak score)
  ▶ Preview button per event · Click card to toggle include/exclude
  Quick Export button (skips review, exports all included)
  Export Selected → button

[Export]
  Output type: Merged MP4 | Individual clips
  Quality: Original | 720p | 480p
  Output folder picker (native dialog, defaults to Desktop)
  Summary panel (event count, total duration, codec, est. size, est. time)
  Export Now → progress bar → "Done! Open Folder" button
```

---

## 8. Error Handling

| Scenario | User-facing message | Blocking? |
|---|---|---|
| File unreadable / bad codec | "VideoCapture could not read this file. Try re-encoding with HandBrake." | Yes — cannot start |
| Slow codec (MJPEG, VP9, AV1) | Amber warning: "Export will re-encode to H.264 — may take longer." | No — amber banner |
| Insufficient disk space | "Need ~X GB free (2× source size). Currently Y GB available." | Yes — cannot start |
| 0 events detected | Shows DIAG data + suggestions: Try High Sensitivity / Check source has motion | No — shown on timeline |
| FFmpeg missing | "FFmpeg not found. Click to reinstall." | Yes — at startup |
| Detection cancelled | "Cancelled — X events found so far. Export partial results or start over." | No — user chooses |
| Export failed | Full error from FFmpeg stderr shown in a scrollable panel | No — retry button |
| YOLO model download fails (no internet) | "Could not download YOLOv8n model. Check your internet connection, or switch to MOG2 mode." Falls back to MOG2 automatically. | No — auto-fallback |

---

## 9. Project Structure

```
CCTV VIDEO PROCESSOR PC/
├── launcher.py                  # Entry point — starts backend, opens PyQt6 window
├── shell/
│   ├── main_window.py           # QMainWindow + QWebEngineView
│   ├── tray.py                  # QSystemTrayIcon
│   └── platform.py              # open_folder(), get_platform()
├── app/
│   ├── main.py                  # FastAPI app factory + lifespan
│   ├── config.py                # PC-adapted constants (resolution, threads, paths)
│   ├── session.py               # In-memory session state + RLock
│   ├── api/
│   │   ├── job.py               # create, start, cancel, events, toggle, export
│   │   ├── preview.py           # temp clip extraction + serving
│   │   ├── stream.py            # SSE endpoint
│   │   └── shell.py             # filepath receiver from PyQt6
│   ├── core/
│   │   ├── detection_engine.py  # MOG2 pipeline (PC-01, PC-02, PC-04 fixed)
│   │   ├── yolo_detector.py     # YOLOv8n wrapper (new)
│   │   ├── export_engine.py     # FFmpeg export (unchanged from Pi)
│   │   ├── log_buffer.py        # asyncio.Queue SSE fan-out (unchanged)
│   │   └── thumbnail_gen.py     # Frame thumbnails for event cards
│   └── utils/
│       ├── ffmpeg_path.py       # imageio-ffmpeg bundled binary resolver (new)
│       ├── ffprobe.py           # Video metadata extraction
│       └── system.py            # CPU%, RAM%, temp (cross-platform)
├── static/
│   ├── css/                     # Design system — dark theme
│   ├── js/
│   │   ├── app.js               # Client-side router
│   │   └── pages/
│   │       ├── home.js
│   │       ├── processing.js
│   │       ├── timeline.js
│   │       └── export.js
│   └── pages/                   # HTML shells
│       ├── home.html
│       ├── processing.html
│       ├── timeline.html
│       └── export.html
├── requirements.txt
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-06-19-cctv-pc-processor-design.md  ← this file
```

---

## 10. Dependencies

```
# requirements.txt
fastapi==0.111.*
uvicorn[standard]==0.29.*
opencv-python-headless==4.9.*
numpy==1.26.*
psutil==5.9.*
imageio-ffmpeg==0.5.*          # bundled FFmpeg — no system install needed
PyQt6==6.7.*
PyQt6-WebEngine==6.7.*
aiofiles==23.*
# Optional — installed on first YOLO job:
# ultralytics==8.*
```

---

## 11. Success Criteria

| ID | Criterion | Target |
|---|---|---|
| SC-01 | App launches on Windows, macOS, Linux | Cold start < 5s |
| SC-02 | 1h 1080p H.264 detection time | < 8 min on a 4-core / 8 GB RAM PC |
| SC-03 | H.264 export time (stream copy) | < 30s for any duration |
| SC-04 | Timestamps accurate | ±1s vs source |
| SC-05 | 0-events hint shown when detection finds nothing | Always |
| SC-06 | YOLO mode detects a walking person | ≥ 90% of test clips |
| SC-07 | App works with no system FFmpeg installed | Always (imageio-ffmpeg) |
| SC-08 | File with spaces in path works | Always (pathlib.Path) |
| SC-09 | Cancel mid-detection preserves partial events | Always |
| SC-10 | Quick Export skips timeline review | Always |
