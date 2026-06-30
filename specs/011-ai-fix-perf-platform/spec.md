# Feature Specification: AI Fix, Performance & Cross-Platform Support

**Feature Branch**: `011-ai-fix-perf-platform`  
**Created**: 2026-06-30  
**Status**: Draft  

## Overview

Stabilise the existing CCTV Video Processor application across three parallel tracks — fix Florence-2 AI garbage output in Intelligence Reports, eliminate detection slowness and UI freezes, and extend full support to Windows, macOS, Linux desktop, Linux headless, and Raspberry Pi (2 GB / 4 GB RAM). No new user-facing features or API endpoints are introduced; this is a quality and compatibility stabilisation release.

---

## User Scenarios & Testing

### User Story 1 — Readable AI Descriptions in Intelligence Reports (Priority: P1)

A user runs YOLO detection on a CCTV video then clicks "Generate Intelligence Report". Currently the Timeline, Scene Breakdown, and Key Moments sections show raw model tokens (`</s>`, `<loc_123>`, `<s>`) or describe a black image. After this fix, every caption field in the report is a readable English description of what the camera saw.

**Why this priority**: The Intelligence Report is the primary AI output that justifies running AI analysis. Garbage output makes the feature unusable.

**Independent Test**: Generate an Intelligence Report on any video with detected events. Without a GPU or real video file, unit-test the caption sanitiser directly and mock `post_process_generation` returning raw tokens — assert the stored caption is clean English.

**Acceptance Scenarios**:

1. **Given** a video with detected motion events, **When** the user generates an Intelligence Report, **Then** all caption fields contain readable English sentences with no `</s>`, `<loc_NNN>`, `<s>`, or `<pad>` tokens.
2. **Given** a 1920×1080 video frame, **When** Florence-2 analyses it, **Then** the image passed to the model is not padded with black borders (aspect-ratio handling is done by the model's own processor).
3. **Given** a caption that would require >64 tokens to express, **When** generation completes, **Then** the stored caption is not truncated mid-token (no partial `<loc_` fragments remain).
4. **Given** a device with <5 GB RAM, **When** the user attempts to generate an Intelligence Report, **Then** the AI Analysis option is shown as unavailable (not silently failing or crashing).

---

### User Story 2 — Responsive Detection with Live Progress (Priority: P2)

A user loads a video file and starts detection. Currently YOLO takes 5–40 seconds to load before anything happens, the progress bar freezes for 8+ seconds at a time, and a long video can take 60+ minutes on a CPU. After this fix, detection starts quickly, the progress bar moves every 2 seconds, and the overall run time is significantly shorter.

**Why this priority**: A frozen UI during a 60-minute operation causes users to think the app has crashed. Fast feedback is essential for usability.

**Independent Test**: Unit-test the time-based progress trigger: mock a slow frame loop and assert the callback fires at least once per 2 seconds regardless of frame count. Test the frame-skip counter: assert only 1 in N frames is submitted to the YOLO model.

**Acceptance Scenarios**:

1. **Given** YOLO is the selected detection mode and ultralytics is installed, **When** the user loads a video file (before clicking Start), **Then** model loading begins in the background; if it has not completed by the time Start is clicked, detection waits up to 60 seconds for the model to be ready before falling back to a cold load.
2. **Given** detection is running at any frame rate, **When** more than 2 seconds elapse since the last progress update, **Then** the progress bar advances without waiting for the next batch boundary.
3. **Given** a 60 fps video, **When** YOLO detection runs, **Then** only 1 in 3 frames (PC) or 1 in 6 frames (Raspberry Pi) is submitted to the model — not every frame.
4. **Given** the app runs on a Raspberry Pi, **When** detection starts, **Then** the batch size is 100 frames (not 500) so RAM-guard checks and cancellation are more responsive.

---

### User Story 3 — Persistent Log Panel During Long Jobs (Priority: P3)

A user switches browser tabs or their WiFi drops briefly while detection is running. Currently the log panel goes blank on reconnect — all log messages emitted during the disconnect are lost. After this fix, switching back to the tab replays all recent log messages so the user can see what happened while they were away.

**Why this priority**: Lost logs make it impossible to debug or review what the job did during extended runs (especially on Pi over WiFi).

**Independent Test**: `LogBuffer.subscribe()` already replays the last 100 ring-buffer entries to a new subscriber (confirmed by research.md Decision 1 — no new `snapshot()` method needed). The server-side fix is therefore zero lines. Test the frontend reconnect by verifying `connectSSE()` retries on `onerror` (quickstart.md S3 — no automated test, frontend JS exemption).

**Acceptance Scenarios**:

1. **Given** detection is running and log messages are accumulating, **When** the user switches to another browser tab and back, **Then** no log messages visible before the tab switch are missing from the panel.
2. **Given** the SSE connection drops and reconnects, **When** the log panel reconnects, **Then** it automatically retries up to 5 times with 3-second backoff before showing a "Connection lost" message.
3. **Given** the log panel reconnects successfully, **Then** the snapshot of recent log messages is displayed before any new live messages arrive.

---

### User Story 4 — Full App Runs on macOS, Linux, and Raspberry Pi (Priority: P4)

A user on macOS (Intel or Apple Silicon), Linux desktop (Ubuntu/Fedora), Linux headless/server, or Raspberry Pi 4/5 wants to run the full CCTV processor. After this fix, the app installs and runs correctly on all these platforms with a README that explains platform-specific steps.

**Why this priority**: The app currently works only on Windows by design; cross-platform support opens it to significantly more users including home-lab Pi setups.

**Independent Test**: Unit-test `get_desktop_path()` with mocked `platform.system()` returning "Darwin", "Linux" (with/without `XDG_DESKTOP_DIR`, with/without `~/Desktop`). Test `QSystemTrayIcon.isSystemTrayAvailable()` guard in close event logic.

**Acceptance Scenarios**:

1. **Given** a macOS or Linux machine, **When** the user follows the README installation steps, **Then** `python launcher.py` starts without errors and the Qt app opens.
2. **Given** a Linux machine without a `~/Desktop` directory, **When** a job export uses the desktop path, **Then** the export defaults to `$XDG_DESKTOP_DIR`, then `~/Downloads`, then `~/` (not a crash).
3. **Given** a GNOME/Wayland desktop where system tray is unavailable, **When** the user closes the window during an active job, **Then** the app closes cleanly rather than hiding to an invisible tray.
4. **Given** a Raspberry Pi with 2 GB or 4 GB RAM, **When** the app starts, **Then** AI Analysis (Florence-2) is automatically disabled and the capability endpoint reports it as unavailable.
5. **Given** a Linux headless server, **When** the backend is started without Qt, **Then** the FastAPI backend serves the web UI on port 5151 and is accessible from another device's browser.

---

### Edge Cases

- What happens when ultralytics is not installed? YOLO warm-up thread must not start; warm-up guard must be a no-op.
- What if the SSE reconnect still fails after 5 retries? Show "Connection lost" message; do not retry indefinitely.
- What if a Pi has exactly 5.0 GB RAM? `AI_FEATURES_ENABLED` threshold is `_total_gb >= 5.0` — exactly 5.0 GB enables AI.
- What if `XDG_DESKTOP_DIR` is set but points to a non-existent directory? Fall through to `~/Desktop`, then `~/Downloads`, then `~/`.
- What if Florence-2 inference exceeds 90 seconds? The existing task-timeout mechanism fires; this is unchanged behaviour.
- What if the YOLO warm-up thread raises an exception? Exception must be caught and logged; it must not propagate to the main thread or prevent job start.

---

## Requirements

### Functional Requirements

**Track 1 — AI Fix**

- **FR-001**: The system MUST sanitise all string values returned by Florence-2's `post_process_generation` to remove special tokens (`</s>`, `<s>`, `<pad>`, `<loc_NNN>`) before storing captions or detection labels.
- **FR-002**: The system MUST NOT pad CCTV frames to a square before passing them to Florence-2; aspect-ratio normalisation is the model processor's responsibility.
- **FR-003**: Florence-2 inference MUST use `max_new_tokens=100` (not 64) to prevent mid-token truncation. (Value chosen as 100, not 150, to stay within the existing 90-second per-task timeout at worst-case CPU inference speed — see research.md Decision 2.)
- **FR-004**: The system MUST suppress `UserWarning` and `DeprecationWarning` from torch, numpy, and PIL during Florence-2 inference calls (not just during model loading). `RuntimeError` and `ValueError` MUST NOT be suppressed.
- **FR-005**: `FrameAnalyzer.is_available()` MUST return `False` immediately when `AI_FEATURES_ENABLED` is False (device has <5 GB RAM), without attempting model loading.

**Track 1 — Log Panel**

- ~~**FR-006**: `LogBuffer` MUST expose a `snapshot()` method returning all entries currently in the ring buffer, in insertion order.~~ *(Eliminated — `LogBuffer.subscribe()` already replays the last 100 ring-buffer entries to new subscribers; confirmed by research.md Decision 1. No server-side change required.)*
- ~~**FR-007**: On every new SSE subscriber connection, the server MUST flush the current `snapshot()` before entering the live-stream loop.~~ *(Eliminated — same rationale as FR-006.)*
- **FR-008**: The frontend SSE client MUST automatically reconnect on error (3-second backoff, maximum 5 retries), then show a "Connection lost" message if all retries fail.

**Track 2 — Performance**

- **FR-009**: When `POST /api/job/create` succeeds and ultralytics is installed, the system MUST start a background daemon thread to pre-load the YOLO model. If ultralytics is not installed, this step MUST be skipped silently.
- **FR-010**: The YOLO detection loop MUST skip frames according to `YOLO_FRAME_SKIP` (3 on PC, 6 on Pi), processing only frames where `frame_index % YOLO_FRAME_SKIP == 0`.
- **FR-011**: Both `detection_engine.py` and `yolo_detector.py` MUST fire the `on_progress` callback at least every 2 seconds, regardless of how many frames have been processed.
- **FR-012**: On Raspberry Pi (`IS_PI` is True), `BATCH_SIZE` MUST be 100; on all other platforms it MUST be 500.

**Track 3 — Platform**

- **FR-013**: A single canonical `get_desktop_path()` function MUST be defined in `app/utils/platform.py` and imported by both `shell/main_window.py` and `app/api/job.py`. Duplicate local definitions MUST be removed.
- **FR-014**: `get_desktop_path()` MUST resolve the desktop path in platform order: Windows (SHGetFolderPathW), macOS (`~/Desktop`), Linux (`$XDG_DESKTOP_DIR` → `~/Desktop` → `~/Downloads` → `~/`).
- **FR-015**: `AI_FEATURES_ENABLED` MUST be defined in `app/config.py` as `True` when total system RAM ≥ 5.0 GB, `False` otherwise.
- **FR-016**: At startup, the Qt main window MUST check `QSystemTrayIcon.isSystemTrayAvailable()` and store the result. Close-to-tray behaviour MUST only be attempted when the result is `True`.
- **FR-017**: `app/api/job.py` MUST import `os` at the module level (not inside a function body).
- **FR-018**: `launcher.py` MUST carry an accurate comment explaining that the SIGINT timer applies to all platforms, not just Windows.
- **FR-019**: `README.md` MUST include platform-specific installation instructions for macOS (Intel + Apple Silicon), Linux desktop (libgl1 prerequisite, Wayland note), Raspberry Pi (install order, AI-disabled note, headless-mode note), and Linux headless.

### Key Entities

- **`FrameAnalyzer`**: Encapsulates Florence-2 model loading and inference. Owns the `_clean_caption()` sanitiser and `is_available()` gate.
- **`LogBuffer`**: Thread-safe ring buffer of log messages. `subscribe()` already replays the last 100 entries to new SSE subscribers — no changes required server-side.
- **`YoloDetector`**: Runs YOLOv8 inference. Gains frame-skip and eager warm-up.
- **`DetectionEngine`**: Orchestrates MOG2 detection. Gains time-based progress callback.
- **`config`**: Single source of truth for `IS_PI`, `AI_FEATURES_ENABLED`, `YOLO_FRAME_SKIP`, `BATCH_SIZE`.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: An Intelligence Report generated from any video contains zero occurrences of the strings `</s>`, `</s>`, `<s>`, `<pad>`, or `<loc_` in any caption or label field.
- **SC-002**: The terminal shows zero `UserWarning` or `DeprecationWarning` lines originating from torch, numpy, or PIL during a complete AI report generation run.
- **SC-003**: The progress bar advances at least once within any 2-second window during an active detection job, regardless of video frame rate or detection mode.
- **SC-004**: A user who switches browser tabs during detection and returns within 30 seconds sees all log messages that were emitted during their absence — no gap in the log sequence.
- **SC-005**: On a device where total RAM < 5 GB, the `/api/system/capabilities` endpoint returns `florence2_available: false` and no Florence-2 model loading occurs during the session.
- **SC-006**: On a Linux system without `~/Desktop`, `get_desktop_path()` returns a valid writable directory (not an error or empty string).
- **SC-007**: The full test suite runs to completion (`pytest tests/ -v`) with ≥ 205 tests passing and zero new failures compared to the Phase 10 baseline. (195 existing + ~10 new tests.)

---

## Assumptions

- The app is already installed and running on Windows; this phase adds compatibility, not a ground-up port.
- Raspberry Pi targets are Pi 4 or Pi 5 running 64-bit Raspberry Pi OS Bookworm; Pi 2 and Pi 3 are not supported.
- `ultralytics` is an optional dependency; the app must degrade gracefully when it is not installed.
- Florence-2 model weights are already cached in `~/.cache/huggingface/` if AI features are enabled; this phase does not add auto-download.
- No new Python packages are added to `requirements.txt`; all fixes use existing dependencies.
- The Linux headless mode documents the existing backend-only capability; it does not add new server functionality.
- The `IS_PI` detection logic already in `app/config.py` (checking `aarch64`/`armv` + Linux) is correct and does not need to change.
- Test suite targets: all new tests must run without a real video file, GPU, or display server.
