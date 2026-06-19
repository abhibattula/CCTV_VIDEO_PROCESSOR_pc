# CCTV Video Processor — User Manual

A desktop application that takes a raw CCTV recording and automatically finds the moments with motion, lets you review and trim them, then exports only the active segments as a clean video.

---

## What the App Does

Raw CCTV footage is mostly empty — hours of static scenes with a few seconds of actual activity scattered throughout. This tool:

1. **Ingests** a video file (MP4, AVI, MKV, MOV, etc.)
2. **Scans** every frame using motion detection to find activity
3. **Shows** you a timeline of detected events so you can review and toggle them on/off
4. **Exports** only the active segments — either merged into one MP4 or as individual clips

The result is a short highlight reel instead of hours of nothing.

---

## How It Works (Under the Hood)

The app has two parts that talk to each other:

| Layer | What it is | What it does |
|-------|-----------|--------------|
| **Backend** (FastAPI) | A local web server on `127.0.0.1:5151` | Runs detection, manages state, serves the UI |
| **Frontend** (PyQt6 shell) | A native window wrapping a browser view | Displays the web UI, opens file dialogs, handles drag-and-drop |

When you launch `launcher.py`, the backend starts in a background thread, the Qt window opens, and the web UI loads inside it. Everything runs locally — no internet required.

**Detection engine (MOG2):** Uses OpenCV's Mixture of Gaussians background subtractor. It builds a model of what "background" looks like, then flags frames where the foreground changes significantly. Sensitivity controls how aggressively it flags motion. High sensitivity = more events found, more false positives.

**Export engine (FFmpeg):** Cuts the source video at exact timestamps and joins the clips. When the source codec is H.264/HEVC, it uses stream-copy (no re-encoding = fast, lossless). It only re-encodes when you choose 720p/480p downscaling or when the source has an incompatible audio codec.

---

## Requirements

- **Python 3.10+** (tested on 3.12)
- **Windows 10/11** (macOS/Linux work but file-dialog integration is Windows-optimised)
- FFmpeg is bundled automatically via `imageio-ffmpeg` — no manual install needed

---

## Installation

```
# 1. Clone or download the project folder
cd "CCTV VIDEO PROCESSOR PC"

# 2. (Recommended) create a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt
```

**Optional — YOLO object detection mode:**
```
pip install ultralytics
```
This downloads a ~6 MB YOLOv8 model on first use and enables the "Object Detection" mode on the home page.

---

## Running the App

```
python launcher.py
```

The window opens in a few seconds. You'll see the home screen with a drop zone.

**First run is slower** — FFmpeg path is resolved on first call, and OpenCV needs a frame or two to warm up the background model.

---

## Step-by-Step Usage

### Step 1 — Load a Video

**Option A: Drag and drop** — drag a video file from File Explorer onto the app window.

**Option B: Browse** — click the **Browse…** button; a native file picker opens. Select your video.

After loading you'll see:
- The file name appears in the drop zone
- A source info card shows codec, FPS, resolution, duration, and audio info
- A "Re-encode: yes/no" field — if yes, the export will re-encode (slower but always compatible)

### Step 2 — Configure Detection Settings

| Setting | What it does | Recommended |
|---------|-------------|-------------|
| **Detection Mode** | MOG2 = background subtraction (fast). Object Detection = YOLO AI (slower, needs ultralytics) | MOG2 for most use cases |
| **Sensitivity** | Low: only strong motion. Medium: balanced. High: catches subtle movement | Medium to start; bump to High if events are missed |
| **Padding (s)** | Extra seconds added before and after each detected moment | 2s — gives context around each event |
| **Min Event Duration (s)** | Discard events shorter than this | 2s — filters out birds, headlights, reflections |
| **Recording Started At** | Optional. Enter the wall-clock time the recording began (e.g. `08:30:00`) | Fill in if you want real timestamps on events |

### Step 3 — Start Detection

Click **Start Detection**. You'll be taken to the Processing page.

The processing page shows:
- **Progress** — 0–100% through the video
- **Status** — detecting / completed / cancelled
- **Events Found** — count of motion segments found so far
- **ETA** — estimated time remaining
- **CPU %** — system load (updates every 3 seconds)
- A live log panel scrolling detection messages

Detection typically runs at **2–5× real-time** on a modern PC (a 1-hour video in 12–30 minutes). Click **Cancel** at any time to stop early — events found so far are kept.

### Step 4 — Review Events (Timeline)

After detection completes, you're taken to the Timeline page.

- **Canvas strip** at the top — a visual map of the whole video. Blue = included event, grey = excluded.
- **Event cards** — one card per detected moment, showing:
  - Wall-clock time if you set "Recording Started At" (e.g. `08:35:12 → 08:35:27`)
  - File-relative offset shown smaller below (e.g. `00:05:12 → 00:05:27`)
  - Duration and peak motion score
  - A **Preview** button to watch the clip in a pop-up player

**Click any card** to toggle it on (blue) or off (grey). Only toggled-on events get exported.

**Select All / Select None** — bulk toggle buttons in the toolbar.

**Quick Export** — skips to export with whatever is currently selected.

**No events found?** The diagnostic state gives two suggestions: try High sensitivity, or verify the source video actually has motion.

### Step 5 — Export

Click **Export Selected** (or **Quick Export** from the toolbar).

On the Export page:

| Option | Description |
|--------|-------------|
| **Merged MP4** | All selected events joined into one continuous file, with chapter markers for each event |
| **Individual Clips** | One MP4 file per event, named `{source}\_event\_001\_{timestamp}.mp4` |
| **Original quality** | Stream-copy — fastest, no quality loss |
| **720p** | Re-encode and downscale to 720p height |
| **480p** | Re-encode and downscale to 480p height (smallest file) |
| **Output Folder** | Click Browse… to choose where files are saved. Default: Desktop |

Click **Export Now**. A progress bar fills as FFmpeg processes the clips. When complete:
- The output file path is displayed
- **Open Folder** opens File Explorer at the export location
- **New Job** returns to the home screen

---

## Output File Naming

**Merged:**
```
{source_name}_activity_{YYYYMMDD_HHMMSS}.mp4
```
Example: `parking_lot_activity_20260619_143022.mp4`

**Individual clips (no recording start):**
```
{source_name}_event_001_00012s.mp4    ← offset 12 seconds into file
{source_name}_event_002_00145s.mp4
```

**Individual clips (with recording start `08:30:00`):**
```
{source_name}_event_001_083012.mp4    ← wall-clock 08:30:12
{source_name}_event_002_084537.mp4    ← wall-clock 08:45:37
```

---

## Crash Recovery

If the app crashes during export, the next launch will automatically:
1. Detect the incomplete output file (via a write-in-progress sentinel file)
2. Delete the partial file
3. Start fresh — you can re-export immediately

---

## Keyboard / Interaction Notes

- The app window supports **native drag-and-drop** from File Explorer
- If you drag a new video onto the window while a completed job has un-exported events, a **confirmation dialog** appears asking whether to export first or discard
- The window can be **minimised to the system tray** — right-click the tray icon for Show / Quit
- Preview clips are temporary — they're cleaned up automatically every 60 seconds during the session and fully deleted when the app closes

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| Window opens but page is blank | Backend didn't start in time | Wait 3–5 seconds and refresh (Ctrl+R in the web view), or restart the app |
| "Cannot probe video" error | FFmpeg can't read the file format | Try converting to MP4 with VLC first |
| No events detected | Sensitivity too low, or video has no motion | Switch to High sensitivity; verify the source has visible activity |
| Export is very slow | Source codec requires re-encoding | Normal — 720p/480p or PCM audio trigger re-encode. Let it run. |
| "ultralytics not installed" error | Object Detection mode selected without the library | Run `pip install ultralytics` then restart |
| Preview shows blank video | Some phone/drone videos have MP4 edit lists | Preview still works; the export will be correct |

---

## Running Tests

```
python -m pytest tests/ -v
```

Expected result: **49 passed, 2 skipped** (the 2 skips are for `ffprobe` which isn't bundled on Windows — FFmpeg itself is bundled and everything works fine).

---

## Project Structure

```
CCTV VIDEO PROCESSOR PC/
├── launcher.py              ← Entry point — run this
├── requirements.txt
│
├── app/                     ← FastAPI backend
│   ├── main.py              ← App factory, routes, startup/shutdown
│   ├── session.py           ← In-memory job state (thread-safe)
│   ├── config.py            ← Constants (ports, paths, thresholds)
│   ├── api/
│   │   ├── job.py           ← /api/job/* — create, start, cancel, export
│   │   ├── stream.py        ← /api/stream — SSE live log
│   │   ├── preview.py       ← /api/job/preview/* — clip preview
│   │   ├── shell_bridge.py  ← /api/shell/* — Qt↔web file dialog bridge
│   │   └── system.py        ← /api/system/stats — CPU/RAM
│   ├── core/
│   │   ├── detection_engine.py  ← MOG2 background subtraction
│   │   ├── export_engine.py     ← FFmpeg-based clip cutting & merging
│   │   ├── yolo_detector.py     ← Optional YOLO object detection
│   │   ├── thumbnail_gen.py     ← Poster frame extraction
│   │   └── log_buffer.py        ← SSE fan-out ring buffer
│   └── utils/
│       ├── ffprobe.py       ← Video metadata probing
│       ├── ffmpeg_path.py   ← Bundled FFmpeg resolver
│       ├── time_utils.py    ← HH:MM:SS ↔ seconds conversion
│       └── system.py        ← CPU/RAM/temp via psutil
│
├── shell/                   ← PyQt6 desktop wrapper
│   ├── main_window.py       ← QMainWindow + QWebEngineView
│   ├── tray.py              ← System tray icon
│   └── platform_utils.py   ← open_folder() per OS
│
├── static/                  ← Web UI (served by FastAPI)
│   ├── index.html           ← SPA shell
│   ├── css/                 ← Dark theme stylesheets
│   └── js/
│       ├── app.js           ← SPA router (pushState)
│       └── pages/
│           ├── home.js      ← Drop zone, settings, start
│           ├── processing.js ← SSE progress, log panel
│           ├── timeline.js  ← Event cards, canvas strip, preview
│           └── export.js    ← Output type, quality, folder, progress
│
└── tests/                   ← pytest test suite
    ├── test_session.py
    ├── test_ffprobe.py
    ├── test_api_job.py
    ├── test_detection_engine.py
    ├── test_export_engine.py
    └── test_yolo_detector.py
```

---

## Version Info

| Component | Version |
|-----------|---------|
| Python | 3.12 |
| PyQt6 | 6.7.0 |
| FastAPI | 0.111.0 |
| OpenCV | 4.9.0 |
| FFmpeg (bundled) | 7.1 (via imageio-ffmpeg 0.5.1) |
