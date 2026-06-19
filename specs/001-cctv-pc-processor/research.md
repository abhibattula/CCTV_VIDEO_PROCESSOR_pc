# Research: CCTV Video Processor PC

**Branch**: `001-cctv-pc-processor` | **Date**: 2026-06-19
**Status**: Complete — all unknowns resolved

---

## Motion Detection Approach

**Decision**: OpenCV MOG2 (Mixture of Gaussians 2) as the default detection mode;
YOLOv8n via `ultralytics` as the optional object detection mode.

**Rationale**: MOG2 is mature, CPU-only, ships inside `opencv-python-headless`, and
runs at real-time speeds on any modern desktop. The existing Pi version already has a
working, debugged MOG2 pipeline. YOLOv8n adds person/vehicle/animal labelling at the
cost of a one-time model download and higher CPU usage — appropriate for the
investigation use case (User Story 2).

**Alternatives considered**:
- Frame differencing: simpler but highly sensitive to camera noise and lighting changes.
- MOG1: superseded by MOG2; no advantage.
- YOLOv8s/m/l: larger models with higher accuracy but slower; nano (n) is sufficient
  for the coarse detection task of identifying motion intervals.

---

## FFmpeg Bundling

**Decision**: `imageio-ffmpeg` pip package bundles a static FFmpeg binary per platform.
All subprocess calls use `get_ffmpeg()` / `get_ffprobe()` from `app/utils/ffmpeg_path.py`.

**Rationale**: Eliminates the "FFmpeg not found" failure mode on user machines. The
bundle is ~70 MB total but installs automatically with `pip install imageio-ffmpeg`.
Covers Windows (ffmpeg.exe), macOS (arm64 + x86_64), and Linux (x86_64).

**Alternatives considered**:
- Require system FFmpeg: breaks on clean Windows installs; unacceptable for
  non-technical users.
- Bundle via PyInstaller data files: more complex packaging; `imageio-ffmpeg` already
  does this correctly.

---

## Desktop UI Framework

**Decision**: PyQt6 native window hosting a `QWebEngineView` pointed at
localhost:5151. HTML/CSS/JS UI served by FastAPI's `StaticFiles` mount.

**Rationale**: Gives full browser rendering (Canvas, EventSource, fetch API) inside a
native window with system tray, drag-and-drop, native file dialogs, and no external
browser dependency. Electron was rejected due to its 150MB+ overhead and Node.js
dependency; Tkinter was rejected due to its poor styling capabilities; CEF Python was
rejected as unmaintained.

**Alternatives considered**:
- Electron: 150MB+ overhead, requires Node.js, complex cross-platform packaging.
- PyWebView: simpler but weaker — no system tray, limited JS bridge.
- Tkinter: ships with Python but incapable of rich CSS/canvas UI without a re-render
  framework; animation/timeline canvas would require custom Tkinter canvas code.
- Pure web app (browser-based): no native file picker, no drag-and-drop to OS, no
  system tray; requires the user to open a browser and navigate to localhost.

---

## Session State Storage

**Decision**: Single in-memory Python dict (`app/session.py`) protected by
`threading.RLock()`. No SQLite, no Redis, no file-based persistence.

**Rationale**: The Pi version's SQLite usage was the primary cause of the "no motion
detected" bug on PC — `get_conn()` failed silently when the DB path was wrong or the
schema wasn't initialised. A RAM dict cannot fail to open, has zero setup, and resets
cleanly between sessions. One job at a time means no concurrency concern beyond the
single background worker thread.

**Alternatives considered**:
- SQLite: was the Pi approach; caused PC-02 bug; rejected.
- Redis: massively over-engineered for a single-user desktop app.
- JSON file: persistent but adds file I/O and corruption risk for no benefit given the
  session-only requirement.

---

## Live Progress Streaming

**Decision**: SSE (Server-Sent Events) via `asyncio.Queue` fan-out (`app/core/log_buffer.py`).
The EventSource API in the browser receives log lines, progress percentage, event count,
and status in real time.

**Rationale**: SSE is simpler than WebSockets for one-directional server→client push.
The existing Pi version's `log_buffer.py` is already correct and reusable unchanged.
The asyncio.Queue approach avoids blocking the uvicorn event loop during detection
(which runs in a daemon thread).

**Alternatives considered**:
- WebSockets: bidirectional, more complex, unnecessary for progress reporting.
- Polling `GET /api/job`: adequate fallback but adds 1–2s latency per update; SSE
  gives sub-second updates with no polling overhead.

---

## Export Strategy

**Decision**: FFmpeg segment extraction to `.ts` intermediate files + concat merge.
Stream copy for H.264/HEVC; re-encode to H.264 for other codecs. Chapter markers
embedded in merged output via `-metadata title=` flags.

**Rationale**: `.ts` (MPEG Transport Stream) tolerates timestamp discontinuities
between segments, making concat reliable for arbitrary clips from a single source.
Stream copy preserves original quality and achieves <30s export for any H.264/HEVC
source. Re-encode is required for MJPEG, VP9, AV1, etc. since they have no fast concat
path via stream copy.

**Alternatives considered**:
- Direct FFmpeg trim + concat in one pass: fragile with timestamp gaps; `.ts`
  intermediate files are the established workaround.
- Lossless re-encode for all: guarantees consistency but makes every export slow.

---

## Wall-Clock Timestamp Display (FR-015 — clarification Q1)

**Decision**: Optional `recording_start` field (HH:MM:SS, user-entered on Home screen).
When set, `time_utils.seconds_to_clock(offset_s, recording_start)` computes absolute
wall-clock time. Event cards show both. Individual clip filenames embed wall-clock time.

**Rationale**: CCTV investigators need to correlate clip timestamps with real-world
events (security logs, witness statements). File metadata timestamps are unreliable on
DVR exports. Manual entry is simple and covers the primary use case.

**Alternatives considered**:
- Auto-detect from file metadata: DVR files often have wrong creation timestamps;
  unreliable. User entry is explicit and trustworthy.

---

## Crash Recovery during Export (FR-016 — clarification Q2)

**Decision**: Write sentinel to `JOBS_DIR/{job_id}/export.writing` (contains the
output file path as text) before FFmpeg starts; delete it on successful completion.
On app launch, scan `JOBS_DIR` for `*.writing` files, read the output path from
each, delete the partial output file, then delete the sentinel.

**Rationale**: Writing the sentinel to JOBS_DIR (a fixed known location inside the
app's data directory) rather than next to the output file means the cleanup scan
works even when the user chose a custom output directory (Desktop, external drive,
etc.) — the scan location is always deterministic regardless of previous session
state. FFmpeg writes incrementally; a partially written MP4 is unplayable and could
mislead the user. Auto-cleanup is silent and correct; no user action needed.

---

## New Job Confirmation (FR-017 — clarification Q3)

**Decision**: When a new video is loaded (drop or browse) and session status is
`completed` with at least one event and `output_path is None`, show a confirmation
dialog via a JS `confirm()` call intercepted by the shell bridge, or rendered as a
modal overlay in the web UI.

**Rationale**: Prevents silent data loss after a multi-minute detection run. The dialog
offers Export (redirects to Export page) or Continue (resets session and loads new file).

---

## Preview Clip Cleanup (FR-018 — clarification Q4)

**Decision**: On `QApplication.aboutToQuit` signal (PyQt6), call `shutil.rmtree` on
`PREVIEW_DIR`. Also run a background cleanup timer (60s interval) that deletes preview
clips older than 5 minutes during an active session to prevent unbounded temp growth.

**Rationale**: Sensitive CCTV footage in temp folders persists across reboots on some
OS configurations. Cleanup on quit is the primary guarantee; periodic cleanup handles
long sessions.
