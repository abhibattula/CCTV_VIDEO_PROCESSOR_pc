# CCTV Video Processor (PC)

A desktop app that takes a raw CCTV recording, automatically finds the moments with
activity, lets you review/filter/trim them in a browser-style UI, then exports only
the parts that matter — either as one merged clip or as individual files.

Runs entirely locally. No internet connection, cloud upload, or account required.

---

## Quick Start

```bash
# 1. Clone and enter the project
git clone https://github.com/abhibattula/CCTV_VIDEO_PROCESSOR_pc.git
cd CCTV_VIDEO_PROCESSOR_pc

# 2. (recommended) create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run it
python launcher.py
```

FFmpeg is bundled automatically (via `imageio-ffmpeg`) — nothing to install separately.

**Optional — AI object detection mode** (tags events as Person/Car/Dog/etc. instead of
generic motion):
```bash
pip install ultralytics
```
The app detects whether this is installed at runtime. If it isn't, the "Object
Detection" mode button is greyed out with an install hint instead of failing after
you click Start.

Requires **Python 3.11+**. Tested on Windows 10/11; the detection/export engines are
platform-agnostic (see [`RASPBERRY_PI_SETUP.md`](RASPBERRY_PI_SETUP.md) for the
Raspberry Pi port notes).

For a full click-by-click walkthrough of the UI, see [`USER_MANUAL.md`](USER_MANUAL.md).

---

## How It Works

The app is two processes glued together by `launcher.py`:

```
┌─────────────────────────────────────────────────────────────┐
│  launcher.py                                                │
│  ┌─────────────────────┐        ┌──────────────────────┐    │
│  │ FastAPI backend      │        │ PyQt6 shell           │    │
│  │ (uvicorn, daemon     │◄──────►│ QMainWindow +          │    │
│  │  thread, port 5151)  │  HTTP  │ QWebEngineView          │    │
│  └─────────────────────┘        └──────────────────────┘    │
│         │                                                    │
│         ▼                                                    │
│  app/session.py — single in-memory job, no database          │
└─────────────────────────────────────────────────────────────┘
```

- **Backend** (`app/`) — a FastAPI server bound to `127.0.0.1:5151`. Owns detection,
  export, and all job state. State lives in one in-memory dict
  (`app/session.py`), protected by a lock — no SQLite, no files, nothing to corrupt.
  On exit, everything is discarded by design (this is a review tool, not an archive).
- **Frontend** (`static/`) — a single-page app in vanilla JS (ES modules, no build
  step, no npm). Served by the same FastAPI process and rendered inside the PyQt6
  window's embedded Chromium (`QWebEngineView`).
- **Shell** (`shell/`) — the native window: opens file dialogs, handles drag-and-drop
  from Explorer, bridges native OS features into the web UI via a small JS bridge,
  and manages the system tray icon.

### The processing pipeline

1. **Load** — drag a video onto the window, or use the file picker. The backend
   probes it with `ffprobe` (codec, resolution, fps, audio) via `app/utils/ffprobe.py`.
2. **Detect** — pick a mode and sensitivity, click Start:
   - **MOG2** (`app/core/detection_engine.py`) — OpenCV background subtraction.
     Always available, fast, no model download.
   - **Object Detection** (`app/core/yolo_detector.py`) — YOLOv8 via `ultralytics`,
     optional. Tags each event with a label (Person/Car/Dog/...) instead of just
     "motion." Detection resolution auto-scales to available RAM.
   - Both engines are callback-driven (`on_progress`, `on_event`) — they never touch
     `session` directly, so they're testable in isolation and interchangeable behind
     one interface.
   - Progress streams to the UI over Server-Sent Events (`app/api/stream.py`); the
     Processing page renders a live per-label bar chart and an events/min counter.
3. **Review** (Timeline page) — every detected event becomes a card with a
   colour-coded confidence badge. From here you can:
   - Filter by label chip and/or a minimum-score slider (non-matching events grey out
     on the canvas strip rather than disappearing, so you keep context)
   - Multi-select with Ctrl+click or checkboxes, bulk include/exclude with a capped
     20-entry undo stack (not just the last operation — Ctrl+Z repeatedly walks back
     through your recent bulk actions in reverse order)
   - Navigate and act entirely by keyboard (arrows, Space, Enter, Ctrl+A/D/E, Esc)
   - Preview any event in a popup player before deciding whether to export it
4. **Export** (`app/core/export_engine.py`) — FFmpeg cuts and (optionally) merges
   the included events. Stream-copies when the source codec allows it (fast, lossless);
   re-encodes only when downscaling to 720p/480p or burning in an overlay. Three
   built-in one-click presets (Security Report / Evidence Pack / Quick Highlights)
   configure output type, quality, and label scope together — or save your own
   current settings as a named custom preset (`app/api/presets.py`), which persists
   across restarts and appears alongside the built-ins; an optional burn-in overlay
   stamps each clip with its timestamp and label via FFmpeg's `drawtext` filter.
5. **Report & data export** — after detection (or export), click "Generate PDF Report"
   on the Export page to produce a standalone incident report with per-event thumbnails
   (`app/core/thumbnail_gen.py`), the activity heatmap, and chain-of-custody hashes
   (`app/core/report_renderer.py` + `app/templates/report.html`). "Event Log (CSV/JSON)"
   exports the included event list as a spreadsheet or structured JSON.

### Region of interest, heatmap, theme, and app-level controls

- **Detection zones** — before starting detection, the Home page shows a preview of
  the video's first frame; draw one or more free-form regions on it
  (`static/js/roi.js`) and detection restricts its activity report to the union of
  those regions instead of the full frame. Zones are per-job only — drawing nothing
  analyzes the whole frame exactly as before, and loading a different file always
  starts with a blank slate.
- **Activity heatmap** — after detection completes, navigate back to the Home page
  and check "Show Activity Heatmap" in the zone-drawing toolbar; a JET-colormapped
  overlay appears on the preview, showing where across the frame motion accumulated
  during the run. The overlay is semi-transparent and pointer-events-none, so zone
  drawing still works through it.
- **Light/dark theme** — a toggle in the nav bar (`static/js/theme.js`) switches the
  whole UI instantly, with the choice remembered across restarts via `localStorage`.
- **Stop** — a nav-bar control that gracefully shuts down the backend after a
  confirmation (cancelling any in-progress work first), while the window itself
  stays open and shows a clear message once it's actually safe to close.
- **New Project** — reachable from every page, abandons the current job (warning
  first only if doing so would lose an active operation or unexported results) and
  returns to a clean upload screen without restarting the application.

### A platform quirk worth knowing about

`QWebEngineView`'s bundled Chromium (the PyPI `PyQt6-WebEngine` wheels) ships **without
proprietary codec support** — `canPlayType()` returns nothing for H.264/AAC but
`"probably"` for VP8/VP9 + Opus/Vorbis, confirmed by direct testing against this exact
build. Because of this:
- **Preview clips** (`app/core/export_engine.py:generate_preview`) are encoded to
  VP8/Opus (WebM), not H.264/AAC, specifically so they play inside the app's own
  embedded browser.
- **Exported files** are unaffected — they're H.264/AAC MP4s (or stream-copied as-is),
  meant for VLC/Windows Media Player/etc., which support those codecs natively.

### Debug Log panel

Because `QWebEngineView` exposes no DevTools to the end user, the app ships its own:
click **🐛 Debug** in the nav bar to open a drawer capturing console output, every
`fetch` request/response, uncaught JS errors, and `<video>` element lifecycle/errors —
with Copy and Clear controls. It's a single self-contained module
(`static/js/debug-log.js`) installed once at app startup; nothing else needs to know
it exists.

---

## Features

**Core loop:** load → (optionally draw detection zones) → detect (MOG2 or YOLO) →
review/filter on a timeline → export.

- Region-of-interest zones — restrict detection to one or more drawn areas of the frame
- **Activity heatmap** — after detection, an optional JET-colormapped overlay on the
  zone-drawing preview shows where motion accumulated across the whole run; toggle it
  on/off with a single checkbox without re-running detection
- Tag/label filtering with a score-threshold slider and live "N shown / M total" count
- Multi-select + bulk include/exclude with a 20-entry undo stack
- Keyboard-driven review (no mouse required end-to-end)
- Confidence badges, coloured label pills, compact post-detection label summary
- Three built-in export presets plus your own named, persisted custom presets,
  optional timestamp+label burn-in overlay
- **PDF/HTML incident report** — one click on the Export page generates a
  self-contained report: thumbnail grid per event, embedded activity heatmap,
  chain-of-custody SHA-256 hashes for source and exported files; prints directly to
  PDF via Qt's embedded Chromium with no extra tools or dependencies
- **CSV/JSON event log export** — download the included event list as a structured
  spreadsheet or machine-readable JSON (respects the current label filter; second
  click produces a new timestamped file, not an overwrite)
- **Quick Report PDF** — instant motion-only PDF with pre-validation (checks for completed
  job and included events before firing); truthful status feedback ("✅ Saved: …" or
  "❌ PDF save failed"); saved to the real Desktop even when OneDrive Desktop Folder
  Backup is enabled; side-by-side with the Intelligence Report button
- **Florence-2 AI Analysis** — task-driven frame captions, object detection, and region
  descriptions; 90 s hard timeout per task (64 max tokens) so the report always
  completes; CLIP ViT-B/32 indexes frames as semantic embeddings (`.clip.npy` sidecars)
  for future natural-language search
- **Report format choice** — a pre-generation modal lets you pick Markdown, PDF, or
  both; choice is remembered across sessions
- **Real-time 4-stage report progress** — live SSE bars for Thumbnails → AI Analysis
  → Writing → PDF; progress reflects actual work (thumbnail bar reaches 100% only after
  files are written); SSE stream handles browser disconnect without terminal errors
- **Scene Breakdown with annotated thumbnails** — bounding boxes, detected object label pills, and
  Florence-2 region captions per event in the HTML preview (confidence bars appear in the event timeline table)
- **SVG Activity Timeline** — visual event density strip at the top of every report
- Light/dark theme toggle, remembered across restarts
- In-app Stop control (graceful backend shutdown) and New Project control (abandon
  the current job and start over without restarting the app), both reachable from
  every page
- Live per-label detection chart + events/min counter while processing; log panel
  with timestamps, severity colours, Show/Hide toggle, and Copy button
- In-app preview player and in-app debug log (see above) — no external tools needed
- Proactive capability checks: the Object Detection button disables itself with an
  install hint if `ultralytics` isn't present, instead of failing after you start a job
- Crash recovery: a half-finished export from a previous crash is detected and
  cleaned up automatically on next launch

---

## Project Structure

```
CCTV VIDEO PROCESSOR PC/
├── launcher.py              ← entry point — run this
├── requirements.txt
│
├── app/                     ← FastAPI backend
│   ├── main.py              ← app factory, routes, startup/crash-recovery
│   ├── session.py           ← in-memory job state (thread-safe, single job)
│   ├── config.py            ← ports, paths, RAM-scaled detection resolution
│   ├── api/
│   │   ├── job.py           ← /api/job/* — create, start, cancel, events, export,
│   │   │                       preview-frame (first-frame extraction for ROI)
│   │   ├── stream.py        ← /api/stream — SSE live progress/log
│   │   ├── preview.py       ← /api/job/preview/* — clip preview (VP8/Opus)
│   │   ├── presets.py       ← /api/presets — custom export preset CRUD (persisted)
│   │   ├── shell_bridge.py  ← /api/shell/* — Qt ↔ web file-dialog bridge
│   │   └── system.py        ← /api/system/* — CPU/RAM stats, capability checks
│   ├── core/
│   │   ├── detection_engine.py  ← MOG2 background subtraction + heatmap accumulation
│   │   ├── yolo_detector.py     ← optional YOLO object detection + heatmap accumulation
│   │   ├── export_engine.py     ← FFmpeg cut/merge/burn-in/preview
│   │   ├── thumbnail_gen.py     ← poster frame extraction per event
│   │   ├── report_renderer.py   ← Jinja2 incident report renderer
│   │   └── log_buffer.py        ← SSE fan-out ring buffer
│   ├── templates/
│   │   └── report.html          ← standalone incident report template (base64 images, no external deps)
│   └── utils/                   ← ffprobe, bundled-ffmpeg resolver, time/system helpers
│
├── shell/                   ← PyQt6 desktop wrapper
│   ├── main_window.py       ← QMainWindow + QWebEngineView, JS bridge, drag & drop,
│   │                           Stop Application bridge flag
│   ├── tray.py              ← system tray icon
│   └── platform_utils.py    ← open_folder() per OS
│
├── static/                  ← web UI (served by FastAPI, no build step)
│   ├── index.html
│   ├── css/                 ← dark/light theme, per-page + ROI editor stylesheets
│   └── js/
│       ├── app.js           ← SPA router + global controls bootstrap
│       ├── debug-log.js     ← in-app console/network/error capture + drawer UI
│       ├── theme.js         ← light/dark theme toggle (localStorage-persisted)
│       ├── stop-app.js       ← Stop Application control + confirm/poll flow
│       ├── new-project.js   ← New Project control + status-aware warnings
│       ├── roi.js           ← ROI polygon-drawing canvas editor
│       ├── session-state.js ← shared UI state (filters, selection, undo) across pages
│       └── pages/           ← home.js, processing.js, timeline.js, export.js
│
├── specs/                   ← spec-driven design docs per feature (spec/plan/tasks)
├── docs/superpowers/        ← implementation plans for AI-assisted work sessions
└── tests/                   ← pytest suite (backend only — see below)
```

---

## Testing

```bash
python -m pytest tests/ -v
```

Expected: **≥ 193 passed, ≤ 2 skipped** (the skips are pre-existing video-dependent
cases; all new Phase 10 tests run without a real video file, GPU, or display).

The backend follows test-first development — every engine (`detection_engine`,
`yolo_detector`, `export_engine`) is covered in isolation via its callback interface,
with no running session or live video required.

There is intentionally no frontend test runner (no build step, no npm). Frontend
changes are verified by driving the real app — either manually, or via a temporary
script that runs a real `QWebEngineView`/`MainWindow` instance and is deleted after
use. See the plans under `docs/superpowers/plans/` for examples of this pattern.

---

## Further Reading

- [`ROADMAP.md`](ROADMAP.md) — future feature ideas and improvements, grouped by theme with effort/impact notes
- [`USER_MANUAL.md`](USER_MANUAL.md) — step-by-step usage guide with screenshots-in-words for every page
- [`RASPBERRY_PI_SETUP.md`](RASPBERRY_PI_SETUP.md) — notes on the Raspberry Pi port
- [`specs/`](specs/) — feature specs, plans, and task breakdowns for each phase of development
- [`.specify/memory/constitution.md`](.specify/memory/constitution.md) — the project's core engineering principles (session-first state, cross-platform paths, test-first, callback-driven engines, YAGNI)
