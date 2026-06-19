# Implementation Plan: CCTV Video Processor PC

**Branch**: `001-cctv-pc-processor` | **Date**: 2026-06-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-cctv-pc-processor/spec.md`

## Summary

A cross-platform desktop application that detects motion events in CCTV video files,
lets users review and curate detected events on an interactive timeline, and exports
only the active segments as a merged MP4 or individual clips — eliminating dead footage
in seconds. Built as a PyQt6 native shell embedding a FastAPI web UI over localhost,
with OpenCV MOG2 (fast) and YOLOv8n (accurate) detection modes, bundled FFmpeg via
imageio-ffmpeg, and pure in-memory session state (no database).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: PyQt6 6.7, PyQt6-WebEngine 6.7, FastAPI 0.111, uvicorn 0.29,
opencv-python-headless 4.9, numpy 1.26, imageio-ffmpeg 0.5, psutil 5.9, aiofiles 23,
requests 2.31; ultralytics (optional — only required for object detection mode)
**Storage**: In-memory Python dict protected by `threading.RLock()` — no database,
no files beyond temp clips and the output video
**Testing**: pytest 8, pytest-asyncio 0.23, httpx 0.27
**Target Platform**: Windows 10+, macOS 12+, Linux (Ubuntu 20.04+) — single binary
per platform via PyInstaller (optional); primary delivery is `python launcher.py`
**Project Type**: Hybrid desktop app — PyQt6 native window hosts a QWebEngineView
pointing at a local FastAPI server (localhost:5151)
**Performance Goals**: Detection of a 1-hour H.264 file completes in under 10 minutes
on 4-core / 8 GB RAM; export via stream copy completes in under 30 seconds
**Constraints**: No system FFmpeg required (bundled); no database; single file at a
time; no internet required for core MOG2 mode; temp preview clips deleted on app close
**Scale/Scope**: Single user, single file at a time, session-only state

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|---------|
| I. Session-First, No Persistence | ✅ Pass | All job state in `app/session.py` RAM dict + RLock; SQLite never imported |
| II. Cross-Platform by Default | ✅ Pass | `pathlib.Path` everywhere; FFmpeg via `imageio-ffmpeg`; `QFileDialog` for file picker; `tempfile.gettempdir()` for temp dir |
| III. Test-First | ✅ Pass | `tests/` mirrors `app/`; every module has a failing test written before implementation |
| IV. Callback-Driven Processing | ✅ Pass | `detection_engine.run()` and `yolo_detector.run()` receive `on_progress`/`on_event` callbacks; engines never import `app.session` |
| V. Simplicity & YAGNI | ✅ Pass | No features beyond 3 user stories; `ultralytics` import is optional with graceful fallback; no premature abstraction |

**All gates pass. No Complexity Tracking entries required.**

## Project Structure

### Documentation (this feature)

```text
specs/001-cctv-pc-processor/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── rest-api.md      # FastAPI endpoint contracts
│   └── shell-bridge.md  # JS↔PyQt6 event bridge contracts
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
CCTV VIDEO PROCESSOR PC/
├── launcher.py                    # Entry point: starts FastAPI thread, opens PyQt6 window
├── requirements.txt
├── shell/                         # PyQt6 native shell
│   ├── __init__.py
│   ├── main_window.py             # QMainWindow + QWebEngineView + drag-and-drop
│   ├── tray.py                    # QSystemTrayIcon
│   └── platform_utils.py         # open_folder(), get_platform()
├── app/                           # FastAPI backend
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory + lifespan
│   ├── config.py                  # PC-adapted constants (resolution, threads, paths)
│   ├── session.py                 # In-memory session state + RLock
│   ├── api/
│   │   ├── __init__.py
│   │   ├── job.py                 # create, start, cancel, events, toggle, export
│   │   ├── preview.py             # temp clip extraction + serving
│   │   ├── stream.py              # SSE endpoint
│   │   └── shell_bridge.py       # filepath receiver + pending-path poll + open-folder
│   ├── core/
│   │   ├── __init__.py
│   │   ├── detection_engine.py    # MOG2 pipeline (PC fixes applied)
│   │   ├── yolo_detector.py       # YOLOv8n wrapper (optional)
│   │   ├── export_engine.py       # FFmpeg concat export
│   │   ├── log_buffer.py          # asyncio.Queue SSE fan-out
│   │   └── thumbnail_gen.py       # Frame thumbnails
│   └── utils/
│       ├── __init__.py
│       ├── ffmpeg_path.py         # imageio-ffmpeg binary resolver
│       ├── ffprobe.py             # Video metadata extraction
│       ├── system.py              # CPU%, RAM%, temp (cross-platform)
│       └── time_utils.py          # seconds_to_clock(), clock_to_seconds()
├── static/                        # Web frontend (served by FastAPI)
│   ├── css/
│   │   ├── base.css
│   │   ├── home.css
│   │   ├── processing.css
│   │   ├── timeline.css
│   │   └── export.css
│   ├── js/
│   │   ├── app.js                 # Client-side router
│   │   └── pages/
│   │       ├── home.js
│   │       ├── processing.js
│   │       ├── timeline.js
│   │       └── export.js
│   └── pages/
│       ├── home.html
│       ├── processing.html
│       ├── timeline.html
│       └── export.html
├── tests/
│   ├── conftest.py
│   ├── test_session.py
│   ├── test_ffmpeg_path.py
│   ├── test_ffprobe.py
│   ├── test_detection_engine.py
│   ├── test_yolo_detector.py
│   └── test_api_job.py
└── docs/
    └── superpowers/
        ├── specs/2026-06-19-cctv-pc-processor-design.md
        └── plans/2026-06-19-cctv-pc-processor.md
```

**Structure Decision**: Hybrid desktop app pattern. `shell/` owns the native PyQt6 layer;
`app/` owns the FastAPI backend; `static/` owns the web UI. Clean separation enables
testing the backend independently of the PyQt6 shell.
