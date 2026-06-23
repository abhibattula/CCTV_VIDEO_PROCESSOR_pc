# CCTV Video Processor — User Manual

A desktop application that takes a raw CCTV recording and automatically finds the moments with motion or objects, lets you filter/review/trim them, then exports only the active segments — optionally with a professional timestamp overlay.

---

## What the App Does

Raw CCTV footage is mostly empty — hours of static scenes with a few seconds of actual activity scattered throughout. This tool:

1. **Ingests** a video file (MP4, AVI, MKV, MOV, etc.)
2. **Scans** every frame for motion (MOG2) or specific objects (YOLO — Person, Car, Dog, etc.)
3. **Shows** you a filterable timeline of detected events — tag by label, threshold by confidence, multi-select, bulk include/exclude with undo
4. **Exports** only the events you keep — merged or individual clips, with one-click presets and an optional timestamp+label overlay

The result is a short, labelled highlight reel instead of hours of nothing.

---

## How It Works (Under the Hood)

The app has two parts that talk to each other:

| Layer | What it is | What it does |
|-------|-----------|--------------|
| **Backend** (FastAPI) | A local web server on `127.0.0.1:5151` | Runs detection, manages state, serves the UI |
| **Frontend** (PyQt6 shell) | A native window wrapping a browser view | Displays the web UI, opens file dialogs, handles drag-and-drop |

When you launch `launcher.py`, the backend starts in a background thread, the Qt window opens, and the web UI loads inside it. Everything runs locally — no internet required.

**Detection engines:**
- **MOG2** — OpenCV's Mixture of Gaussians background subtractor. Builds a model of "background," flags frames where the foreground changes significantly. Always available, no setup. Events from this mode have no label (shown as "Unlabelled").
- **Object Detection (YOLO)** — optional, requires `pip install ultralytics`. Tags each event with what it actually saw (Person, Car, Dog, Cat, Bus, Bicycle, ...), enabling label filtering and label-aware export presets. If `ultralytics` isn't installed, the home page detects this automatically and greys out the mode button with an install hint instead of letting you hit an error after starting a job.

**Export engine (FFmpeg):** Cuts the source video at exact timestamps and joins the clips. When the source codec is H.264/HEVC, it uses stream-copy (no re-encoding = fast, lossless). It re-encodes only when you choose 720p/480p downscaling, when burn-in is enabled, or when the source has an incompatible audio codec.

**Debug Log panel:** the app's embedded browser view has no DevTools console, so the app ships its own — click **🐛 Debug** in the nav bar (any page) to open a drawer showing console output, network activity, and errors. Useful if something looks wrong and you want to see what the app is actually doing.

**Nav bar controls (every page):**
- **☀️ / 🌙** — toggles light/dark theme instantly; remembered across restarts.
- **Stop** — gracefully shuts down the backend after a confirmation, while the window stays open until you close it.
- **New Project** — abandons the current job (with a warning only if it would lose real work) and returns to a clean upload screen.

See "Stopping the Application" and "Starting a New Project" further down for details on the last two.

---

## Requirements

- **Python 3.11+** (tested on 3.12)
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
This downloads a ~6 MB YOLOv8 model on first use and enables the "Object Detection" mode on the home page. Without it, that mode button is disabled with a tooltip explaining why — MOG2 motion detection still works fully.

---

## Running the App

```
python launcher.py
```

The window opens in a few seconds. You'll see the home screen with a drop zone and detection settings laid out in two columns.

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
- A **Detection Zones** card showing a preview of the video's first frame

### Step 1b — Draw Detection Zones (optional)

If you only care about activity in part of the frame — a doorway, a parking spot,
one camera's overlapping field of view — draw a region on the preview instead of
analysing the whole frame:

1. Click on the preview to place a point; keep clicking to add more points.
2. Once you've placed at least 3 points, click back near your first point to close
   the shape into a region.
3. Repeat to draw additional regions — detection reports activity inside *any* of
   them, not just one.
4. Each region gets a label chip below the preview (e.g. "Region 1") — click into
   the chip to rename it, or click its **×** to delete just that region.
5. **Clear All** removes every region and starts over.

If you draw nothing, detection analyses the full frame exactly as before — drawing
zones is entirely optional. Zones are **per-video only**: loading a different file
always starts with a blank preview and no regions, they're never saved or reused
across videos. If the preview can't be generated (a corrupted or zero-duration
file), you'll see "Preview unavailable — detection will run on the full frame"
instead, and detection still works normally.

### Step 2 — Configure Detection Settings

| Setting | What it does | Recommended |
|---------|-------------|-------------|
| **Detection Mode** | MOG2 = background subtraction (fast, unlabelled). Object Detection = YOLO AI (slower, labels each event) | MOG2 for general review; Object Detection when you need to filter by what's in frame |
| **Sensitivity** | Low: only strong motion. Medium: balanced. High: catches subtle movement | Medium to start; bump to High if events are missed |
| **Padding (s)** | Extra seconds added before and after each detected moment | 2s — gives context around each event |
| **Min Event Duration (s)** | Discard events shorter than this | 2s — filters out birds, headlights, reflections |
| **Recording Started At** | Optional. Enter the wall-clock time the recording began (e.g. `08:30:00`) | Fill in if you want real timestamps on events and in burn-in overlays |

If "Object Detection" is greyed out, `ultralytics` isn't installed — see Installation above, or just use MOG2.

### Step 3 — Start Detection

Click **Start Detection**. You'll be taken to the Processing page, which shows:

- **Progress** — 0–100% through the video
- **Status** — detecting / completed / cancelled
- **Events Found** — running count of segments found so far
- **ETA** — estimated time remaining
- **CPU %** — system load (updates every 3 seconds)
- **Live detection chart** — a bar per label updating in real time as events are found (one bar labelled "Motion" in MOG2 mode), plus an events/min rate once a minute of detection has elapsed — useful for catching a misconfigured sensitivity early (e.g. zero events after 20% of the video usually means sensitivity is too low)
- A live log panel scrolling detection messages

Detection typically runs at **2–5× real-time** on a modern PC (a 1-hour video in 12–30 minutes). Click **Cancel** at any time to stop early — events found so far are kept.

### Step 4 — Review Events (Timeline)

After detection completes, you're taken to the Timeline page.

**Canvas strip** at the top — a visual map of the whole video. Coloured blocks = events matching the active filter; grey/dimmed blocks = events hidden by a filter (still there, just deprioritised so you keep context); plain grey = excluded.

**Event cards** — one per detected moment, showing:
- Wall-clock time if you set "Recording Started At" (e.g. `08:35:12 → 08:35:27`), with the file-relative offset shown smaller below
- A colour-coded **confidence badge**: green (score ≥ 0.7), amber (0.4–0.69), red (< 0.4) — triage at a glance
- A coloured **label pill** (Person/Car/Dog/...) if detected in Object Detection mode — **click it to instantly filter the timeline to that label**
- A **Preview** button to watch the clip in a pop-up player (clips re-encode for in-app playback, so there's a short "Generating preview clip…" wait — typically a few seconds, longer for high-resolution sources)

**Click any card** to toggle it on (blue) or off (grey/struck-through). Only toggled-on events get exported.

#### Filtering

- A **label filter bar** at the top shows one chip per label found in the job (plus "Unlabelled" for MOG2 events). Click a chip to show only matching events; click multiple chips to show events matching *any* of them.
- A **score threshold slider** hides events below the chosen confidence — they're hidden, not excluded, so clearing the filter brings them right back.
- The toolbar always shows **"N shown / M total"**.
- If a filter combination matches nothing, you'll see "No events match this filter" with a one-click **Clear Filters** button instead of an empty list.
- **Clear Filters** resets both the label chips and the score slider.

#### Multi-select & bulk operations

- **Ctrl+click** a card (or click its checkbox) to enter multi-select mode; the toolbar shows a bulk-action bar:

  | Button | What it does |
  |--------|--------------|
  | **Include** / **Exclude** | Set all selected events included/excluded in one action |
  | **Invert Selection** | Swap which visible events are selected (doesn't change include/exclude state) |
  | **Select Visible** | Select every event matching the current filter |
  | **Undo** | Revert the most recent bulk include/exclude (also `Ctrl+Z`) — press repeatedly to step back through up to 20 recent bulk operations, most recent first |
  | **Clear Selection** | Exit multi-select (also `Escape`) |

- If a bulk-exclude (or a string of individual toggles) leaves **zero events included**, a warning appears: *"No events selected for export — adjust filters or include more events."* It clears itself as soon as anything is included again.

#### Keyboard shortcuts

The whole review step can be done without a mouse:

| Key | Action |
|-----|--------|
| `↓` / `↑` | Move focus to next/previous visible card |
| `Space` | Toggle the focused card included/excluded |
| `Enter` | Open Preview for the focused card |
| `Ctrl+A` | Select all visible events |
| `Ctrl+D` | Deselect all |
| `Ctrl+Z` | Undo last bulk operation |
| `Ctrl+E` | Go to Export |
| `Escape` | Clear selection / close multi-select |

Shortcuts are automatically suppressed while typing in a text field or dragging the score slider, so they won't interfere with normal input.

**No events found?** The diagnostic state gives two suggestions: try High sensitivity, or verify the source video actually has motion.

### Step 5 — Export

Click **Quick Export** from the timeline toolbar, or navigate to Export directly (`Ctrl+E`).

**Quick presets** — one click configures everything below:

| Preset | Output | Quality | Burn-in | Label scope |
|--------|--------|---------|---------|-------------|
| **Security Report** | Merged | Original | On | Person *(requires Object Detection mode — greyed out with a tooltip in MOG2-only jobs, since there's no "Person" label to filter on)* |
| **Evidence Pack** | Individual clips | Original | Off | All |
| **Quick Highlights** | Merged | 720p | Off | Auto-selects the top 10 events by score (or all, if fewer than 10 exist) |

**Custom presets** — if you reconfigure the same combination of settings every time
(e.g. always merged + 720p + burn-in + "Person" only), save it once:

1. Configure output type, quality, burn-in, and label scope manually (below).
2. Click **Save as Preset**, give it a name (anything except a built-in preset's
   name, case-insensitive — e.g. "security report" collides with "Security Report").
3. It appears as a fourth (fifth, sixth, ...) one-click button alongside the
   built-ins, and **persists across app restarts** — load a different video next
   week and it's still there.
4. Click the small **×** on a custom preset's button to delete it; this never
   affects the 3 built-in presets.

Or configure manually:

| Option | Description |
|--------|-------------|
| **Merged MP4** | All selected events joined into one continuous file |
| **Individual Clips** | One MP4 file per event |
| **Original quality** | Stream-copy — fastest, no quality loss |
| **720p / 480p** | Re-encode and downscale (480p = smallest file) |
| **Burn-in timestamp & label** | Stamps each clip with a semi-transparent overlay reading `HH:MM:SS • Label` in the bottom-left corner, via FFmpeg's `drawtext` filter |
| **Label Scope** | Restrict export to one label (e.g. only "Person" events), or "All labels" |
| **Output Folder** | Click Browse… to choose where files are saved. Default: Desktop |

Click **Export Now**. A progress bar fills as FFmpeg processes the clips. When complete:
- The output file path is displayed
- **Open Folder** opens File Explorer at the export location
- **New Job** returns to the home screen (this also resets all timeline filters/selection/undo history for the next job) — see also the nav bar's **New Project** control below, which does the same thing from any page, not just after a finished export

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

## Stopping the Application

Closing the window doesn't fully stop the app on its own — the backend keeps
running in the background so the window can reopen quickly. To shut everything
down deliberately:

1. Click **Stop** in the nav bar (any page).
2. Confirm — you're warned that any in-progress detection or export will be
   cancelled first.
3. The page shows "Stopping…", then within about 15 seconds either:
   - **"✅ Application stopped. You can close this window now."** — the backend is
     confirmed gone; close the window whenever you like.
   - **"Could not confirm the application stopped"** — rare, happens only if this
     window's backend is shared with another already-open window of the app;
     closing the window directly is still safe in that case.

The window itself never disappears on its own — you always close it yourself once
you see one of those two messages.

## Starting a New Project

To abandon the current video and load a different one, click **New Project** in
the nav bar from anywhere — Home, Processing, Timeline, or Export:

- If detection or export is **actively running**, you're warned it will be
  cancelled.
- If the current job **finished but hasn't been exported yet**, you're warned
  those events will be discarded.
- Otherwise (nothing started yet, or already exported), it jumps straight to a
  clean upload screen with no warning — there's nothing to lose.

Either way, once you're back at the upload screen, the next video you load starts
with zero leftover filters, selections, undo history, or drawn detection zones
from the previous job.

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
- See the Timeline keyboard shortcuts table above for the full mouse-free review workflow

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| Window opens but page is blank | Backend didn't start in time | Wait 3–5 seconds and refresh (Ctrl+R in the web view), or restart the app |
| "Cannot probe video" error | FFmpeg can't read the file format | Try converting to MP4 with VLC first |
| No events detected | Sensitivity too low, or video has no motion | Switch to High sensitivity; verify the source has visible activity |
| Object Detection mode is greyed out | `ultralytics` isn't installed | Run `pip install ultralytics` then restart |
| "Security Report" preset is greyed out | The job has no labels (MOG2 mode) — there's nothing to filter to "Person" | Re-run detection in Object Detection mode, or use a different preset |
| Bulk-excluding everything shows a warning, not an error | By design — it's a heads-up that export will have nothing to do until you include something again | Adjust filters or re-include events |
| Export is very slow | Source codec requires re-encoding | Normal — 720p/480p, burn-in, or PCM audio trigger re-encode. Let it run. |
| Preview takes a long time to load | Full-resolution clips take longer to re-encode for in-app playback (a 1080p clip can take 15–20s) | Wait for it — the "Generating preview clip…" state covers this; the export itself isn't affected |
| Not sure what the app is doing / something looks broken | No visibility into console/network errors | Open the **🐛 Debug** drawer (nav bar) to see live console, fetch, and error activity; **Copy** it if reporting an issue |

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Expected result: **74 passed, 2 skipped** (the 2 skips are for `ffprobe`-specific cases that don't apply on Windows — FFmpeg itself is bundled and everything works fine). There is no frontend test runner; frontend behaviour is verified by driving the real app directly.

---

## Project Structure

```
CCTV VIDEO PROCESSOR PC/
├── launcher.py              ← Entry point — run this
├── requirements.txt
│
├── app/                     ← FastAPI backend
│   ├── main.py              ← App factory, routes, startup/shutdown, crash recovery
│   ├── session.py           ← In-memory job state (thread-safe)
│   ├── config.py            ← Constants (ports, paths, RAM-scaled detection resolution)
│   ├── api/
│   │   ├── job.py           ← /api/job/* — create, start, cancel, events, bulk toggle,
│   │   │                       export, preview-frame (first-frame extraction for ROI)
│   │   ├── stream.py        ← /api/stream — SSE live log/progress
│   │   ├── preview.py       ← /api/job/preview/* — clip preview (VP8/Opus)
│   │   ├── presets.py       ← /api/presets — custom export preset CRUD (persisted)
│   │   ├── shell_bridge.py  ← /api/shell/* — Qt↔web file dialog bridge
│   │   └── system.py        ← /api/system/* — CPU/RAM stats, YOLO capability check
│   ├── core/
│   │   ├── detection_engine.py  ← MOG2 background subtraction
│   │   ├── yolo_detector.py     ← Optional YOLO object detection
│   │   ├── export_engine.py     ← FFmpeg cut/merge/burn-in/preview
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
│   ├── css/                 ← Dark/light theme + per-page + ROI editor stylesheets
│   └── js/
│       ├── app.js           ← SPA router (pushState) + global controls bootstrap
│       ├── debug-log.js     ← In-app console/network/error capture + drawer UI
│       ├── theme.js         ← Light/dark theme toggle (localStorage-persisted)
│       ├── stop-app.js       ← Stop Application control + confirm/poll flow
│       ├── new-project.js   ← New Project control + status-aware warnings
│       ├── roi.js           ← ROI polygon-drawing canvas editor
│       ├── session-state.js ← Shared filter/selection/undo state across pages
│       └── pages/
│           ├── home.js      ← Drop zone, settings, capability checks, start
│           ├── processing.js ← SSE progress, live label chart, log panel
│           ├── timeline.js  ← Event cards, filtering, multi-select, preview
│           └── export.js    ← Presets, output type, quality, burn-in, folder
│
└── tests/                   ← pytest test suite (backend only)
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
