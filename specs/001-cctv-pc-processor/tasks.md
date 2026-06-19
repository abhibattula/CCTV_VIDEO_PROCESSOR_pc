---
description: "Task list for CCTV Video Processor PC"
---

# Tasks: CCTV Video Processor PC

**Input**: Design documents from `specs/001-cctv-pc-processor/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Included — Constitution Principle III (Test-First) is NON-NEGOTIABLE.
Tests are written first, confirmed failing, then implementation follows.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Tests MUST be written and FAIL before their corresponding implementation task

---

## Phase 1: Setup

**Purpose**: Project initialization, dependency installation, directory scaffolding.

- [X] T001 Create `requirements.txt` with all pinned dependencies (fastapi, uvicorn, opencv-python-headless, numpy, imageio-ffmpeg, PyQt6, PyQt6-WebEngine, psutil, aiofiles, requests, pytest, pytest-asyncio, httpx)
- [X] T002 [P] Create all `__init__.py` files and package directories: `app/`, `app/api/`, `app/core/`, `app/utils/`, `shell/`, `static/pages/`, `static/css/`, `static/js/pages/`, `tests/`
- [X] T003 [P] Create `tests/conftest.py` with shared `client` fixture (TestClient wrapping `create_app()`, calls `session.reset()` before each test)
- [X] T004 Install dependencies: `pip install -r requirements.txt`

**Checkpoint**: `python -c "import fastapi, cv2, PyQt6"` runs without error.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure required by ALL user stories. Nothing in Phase 3+ can
start until this phase is complete.

**⚠️ CRITICAL**: No user story work begins until this phase is fully done.

- [X] T005 [P] Write failing tests for `app/config.py` in `tests/test_config.py`: assert `DETECT_WIDTH` and `DETECT_HEIGHT` are set based on available RAM; assert `BACKEND_PORT == 5151`; assert `PREVIEW_DIR`, `JOBS_DIR`, `MODEL_DIR` are `pathlib.Path` instances; assert `BATCH_SIZE` is an int; assert `LOG_RING_SIZE == 2000`
- [X] T006 [P] Create `app/config.py` — PC-adapted constants: RAM-scaled detection resolution (640×360 ≥8 GB / 480×270 4–8 GB / 320×180 <4 GB), `BACKEND_PORT=5151`, `PREVIEW_DIR`, `JOBS_DIR`, `MODEL_DIR = Path.home()/".cctv_processor"/"models"`, `STREAM_COPY_SAFE`, `FFMPEG_THREADS`, `BATCH_SIZE=500`, `LOG_RING_SIZE=2000`, `RAM_GUARD_PERCENT=85`
- [X] T007 Run `pytest tests/test_config.py -v` → expect all pass

- [X] T008 [P] Write failing tests for `app/utils/ffmpeg_path.py` in `tests/test_ffmpeg_path.py`: `test_get_ffmpeg_returns_existing_path`, `test_get_ffprobe_returns_existing_path`
- [X] T009 [P] Create `app/utils/ffmpeg_path.py` — `get_ffmpeg()` and `get_ffprobe()` resolvers using `imageio_ffmpeg.get_ffmpeg_exe()`; system ffmpeg fallback; raises `RuntimeError` if not found
- [X] T010 Run `pytest tests/test_ffmpeg_path.py -v` → expect 2 passed (2 skipped — no ffprobe binary on Windows)

- [X] T011 [P] Write failing tests for `app/session.py` in `tests/test_session.py`: initial status idle, `update()` changes fields, `snapshot()` returns deep copy, `append_event()`, `toggle_event()`, thread-safe concurrent updates (50-thread test)
- [X] T012 [P] Create `app/session.py` — in-memory session dict with `threading.RLock()`; `reset()`, `update(**kwargs)`, `snapshot()` (deep copy), `append_event(ev)`, `toggle_event(idx)`; initialises on import
- [X] T013 Run `pytest tests/test_session.py -v` → 7 passed

- [X] T014 [P] Write NEW `app/utils/time_utils.py` (do NOT copy Pi version — incompatible format): `seconds_to_clock(offset_s, recording_start=None)` where `recording_start` is `"HH:MM:SS"` user input (not ISO 8601); fallback is elapsed `HH:MM:SS`; also include `clock_to_seconds(hms: str) -> int`; verify `seconds_to_clock(3661, None) == "01:01:01"` and `seconds_to_clock(600, "08:00:00") == "08:10:00"`
- [X] T015 [P] Copy `app/core/log_buffer.py` from `OLD RASPBERRI PI VERSION/app/core/log_buffer.py`; rename existing `clear(job_id)` → `reset(job_id)` (same body; just rename for consistency with PC API); run `python -c "from app.core.log_buffer import log_buffer; print('OK')"`

- [X] T016 [P] Create `app/utils/ffprobe.py` with dual-probe strategy: ffprobe JSON primary, ffmpeg -i stderr fallback; returns keys: codec, fps, width, height, duration_s, has_audio, audio_codec, needs_reencode
- [X] T017 [P] Write `tests/test_ffprobe.py`: `test_probe_returns_expected_fields` asserts keys `codec`, `fps`, `duration_s`, `width`, `height`, `has_audio`, `needs_reencode`, `audio_codec` present (NOT `codec_name`/`avg_frame_rate`); `test_probe_detects_has_audio`; `test_probe_duration_fallback` (mock zero-duration file) — all `@pytest.mark.skipif` on test video absence
- [X] T018 Run `pytest tests/test_ffprobe.py -v` → all 9 passed (or skipped)

- [X] T019 [P] Write `tests/test_api_job.py` minimal bootstrap test: `test_health` — GET /api/health returns `{"status":"ok"}` (⚠️ test BEFORE implementation — Constitution Principle III)
- [X] T020 Create `app/main.py` — FastAPI app factory with `lifespan` context manager: creates `PREVIEW_DIR`/`JOBS_DIR`, sets log_buffer event loop, calls `session.reset()`, starts preview cleanup background task; mounts `StaticFiles`; registers all routers; health endpoint
- [X] T021 Run `pytest tests/test_api_job.py::test_health -v` → 1 passed

**Checkpoint**: Foundation ready — `pytest tests/ -v` passes with no failures; user story work can begin.

---

## Phase 3: User Story 1 — Quick Activity Export (Priority: P1) 🎯 MVP

**Goal**: User drops a video, clicks Start, detection runs, Quick Export produces a
merged MP4 on their Desktop — zero timeline review required.

**Independent Test**: Drop a test video with 3 active segments onto the app. After
detection completes and Quick Export is clicked, a merged MP4 exists on the Desktop
whose total duration is less than the source duration.

### Detection Engine (MOG2)

- [X] T022 [P] [US1] Write `tests/test_detection_engine.py`: `test_detection_engine_has_run_attr`; `test_run_signature_accepts_callbacks` (inspect signature — must have `on_progress`, `on_event` params); `test_detection_finds_events_on_real_video` (skipif no test video at project root; constructs callbacks that collect events, calls `run()`, asserts ≥1 event found and progress reaches 1.0); `test_detection_respects_cancel` (pre-set cancel_event before calling `run()`, asserts `on_event` was never called)
- [X] T023 [US1] Write PC-adapted `app/core/detection_engine.py` from scratch (all T024-T027 patches applied in one clean implementation)
- [X] T024 [US1] Applied: CLAHE warmup fix — `if sensitivity == "high": gray = clahe.apply(gray)` inside initial warmup loop
- [X] T025 [US1] Applied: PC-02 full rewrite — no DB, no crash-resume, no ram_guard; callback-based interface; `get_ffmpeg()` in normalize
- [X] T026 [US1] Applied: PC-04 — W,H from config; config.BATCH_SIZE for progress reporting interval
- [X] T027 [US1] Applied: `silence_start = None` sentinel fix throughout state machine
- [X] T028 [US1] Run `pytest tests/test_detection_engine.py -v` → 4 passed (74s)

### Export Engine

- [X] T029 [P] [US1] Create `app/core/export_engine.py` and `app/core/thumbnail_gen.py` — PC-adapted from scratch
- [X] T030 [US1] Applied: all `get_ffmpeg()` calls in export_engine and thumbnail_gen (3 locations)
- [X] T031 [US1] Applied: PC-07 + compatibility fixes — callback interface, as_posix() concat, quality strings, audio codec safety
- [X] T032 [US1] Applied: write-in-progress sentinel at `job_dir/"export.writing"` with output path content; deleted on success
- [X] T033 [US1] Applied: `get_ffmpeg()` in thumbnail_gen

### API: Job Create + Start + Cancel + Export + SSE

- [X] T034 [P] [US1] Expand `tests/test_api_job.py` with: `test_create_job_missing_file` (400); `test_get_job_initial_state` (status==idle); `test_toggle_event_out_of_range` (404); `test_create_job_valid_file` (skipif)
- [X] T035 [US1] Create `app/api/job.py` — complete job router
- [X] T036 [US1] Create `app/api/stream.py` — SSE endpoint with keepalive + done signal
- [X] T037 [US1] Run `pytest tests/test_api_job.py -v` → 5 passed

### Frontend: Home Page

- [X] T038 [P] [US1] Create `static/css/base.css` — dark theme design system
- [X] T039 [P] [US1] Create `static/js/app.js` — client-side SPA router
- [X] T040 [P] [US1] Create `static/index.html` — single-page app shell
- [X] T041 [P] [US1] Create `static/css/home.css` — two-column grid layout
- [X] T042 [US1] Create `static/js/pages/home.js` — full home page logic with FR-017 modal

### Frontend: Processing Page

- [X] T043 [P] [US1] Create `static/css/processing.css` — stats cards, log panel
- [X] T044 [US1] Create `static/js/pages/processing.js` — SSE consumer, auto-navigate, cancel

### Frontend: Export Page (US1 subset — merged MP4 only)

- [X] T045 [P] [US1] Create `static/css/export.css` — export two-column layout
- [X] T046 [US1] Create `static/js/pages/export.js` — export options + FR-014 quick-start

### PyQt6 Shell + Launcher

- [X] T047 [P] [US1] Create `shell/platform_utils.py` — cross-platform folder opener
- [X] T048 [P] [US1] Create `shell/main_window.py` — QMainWindow + QWebEngineView + JS bridge + FR-017 drop safety
- [X] T049 [US1] Create `launcher.py` — uvicorn daemon thread + QApplication
- [X] T050 [US1] Crash-recovery in `app/main.py` lifespan: scan export.writing sentinels, wipe PREVIEW_DIR
- [X] T051 [US1] Integration verified: backend health OK, home page served, all API endpoints functional

**Checkpoint**: US1 complete — drop video → detect → Quick Export → merged MP4 on Desktop. ✅

---

## Phase 4: User Story 2 — Review and Curate Timeline (Priority: P2)

**Goal**: After detection, user sees a visual timeline, previews individual clips,
toggles false positives off, and exports only the selected events.

**Independent Test**: Run detection on a video with mixed events. Toggle off 2 events on
the Timeline page. Export — confirm output contains only the non-toggled events.

### API: Preview

- [X] T052 [P] [US2] Create `app/api/preview.py` — `POST /api/job/preview/{idx}`: extracts clip using FFmpeg to `PREVIEW_DIR/{token}.mp4`; returns `{url, token}`; `GET /api/preview/{token}.mp4`: validates 16-hex token; serves `FileResponse`; 404 if expired

### Frontend: Timeline Page

- [X] T053 [P] [US2] Create `static/css/timeline.css` — toolbar, canvas strip, event cards, preview modal overlay
- [X] T054 [US2] Create `static/js/pages/timeline.js` — full timeline with canvas, event cards, preview modal, toggle, select all/none
- [X] T055 [US2] No-events diagnostic panel in `static/js/pages/timeline.js`

### Session Discard Confirmation

- [X] T056 [US2] FR-017 confirmation modal in `static/js/pages/home.js` — before loadFile checks job status

### Preview Cleanup on App Close

- [X] T057 [US2] `launcher.py`: `aboutToQuit` wipes PREVIEW_DIR; 60s QTimer deletes clips older than 300s

**Checkpoint**: US2 complete — timeline renders, events toggle, preview plays, export respects inclusions. ✅

---

## Phase 5: User Story 3 — Flexible Output Options (Priority: P3)

**Goal**: User can choose merged MP4 or individual clips, select quality (original/720p/480p),
pick any output folder, and see wall-clock timestamps on event cards.

**Independent Test**: Export as Individual Clips → multiple numbered files in output folder.
Export at 720p → output video height == 720. Browse output folder → native folder picker opens.

### Individual Clips + Quality in Export Engine

- [X] T058 [P] [US3] Extend `app/core/export_engine.py` to support `output_type == "individual"`: for each included event, write `{source_stem}_event_{N:03d}_{timestamp}.mp4`; wall-clock timestamp in filename when `recording_start` is set, file-relative offset otherwise
- [X] T059 [P] [US3] Extend `app/core/export_engine.py` quality scaling: when `quality == "720p"`, add `-vf scale=-2:720` to FFmpeg re-encode command; when `quality == "480p"`, add `-vf scale=-2:480`; "original" passes no scale filter

### Folder Picker + Shell Bridge

- [X] T060 [P] [US3] Create `app/api/shell_bridge.py` — complete router: `POST /api/shell/filepath` (stores to `session.update(pending_path=...)`); `GET /api/shell/pending-path` (returns and clears atomically); `POST /api/shell/open-folder` (calls `open_folder(dirname(output_path))`); `POST /api/shell/set-output-dir`
- [X] T061 [US3] Register `shell_bridge` router in `app/main.py` (add `from app.api.shell_bridge import router as shell_router` + `app.include_router(shell_router, prefix="/api")`)
- [X] T062 [US3] Add `cctv:browse-folder` handling in `shell/main_window.py` `_handle_browse_flags()`: open `QFileDialog.getExistingDirectory()`; POST result to `/api/shell/filepath`

### Frontend: Export Page Full Options

- [X] T063 [US3] Extend `static/js/pages/export.js` — add Individual Clips / Merged MP4 toggle (segment buttons); add 720p / 480p / Original quality toggle; add output folder row with Browse button (dispatches `cctv:browse-folder`, polls `/api/shell/pending-path`, calls `/api/shell/set-output-dir`); summary card shows codec stream-copy vs re-encode indicator and estimated time

### Wall-Clock Timestamps (FR-015)

- [X] T064 [P] [US3] Add optional "Recording started at (HH:MM:SS)" input field to `static/js/pages/home.js` settings panel; pass `recording_start` value to `POST /api/job/start` body
- [X] T065 [US3] Update `static/js/pages/timeline.js` event card rendering: when `start_clock` is non-null, display it prominently; show file-relative time as secondary (smaller, muted); update individual clip filename display to show wall-clock time in done state

### YOLO / Object Detection Mode

- [X] T066 [P] [US3] Write `tests/test_yolo_detector.py`: `test_yolo_detector_imports` (has `run`); `test_yolo_unavailable_raises_helpful_error` (mock `ultralytics` as None, assert `ImportError` with "ultralytics" in message)
- [X] T067 [US3] Create `app/core/yolo_detector.py` — same `run()` interface as `detection_engine.run()`; wraps `ultralytics.YOLO("yolov8n.pt")` (auto-downloads to `MODEL_DIR`); confidence thresholds per sensitivity; YOLO class ID → label mapping (Person/Vehicle/Animal); events tagged with label; raises `ImportError` with install hint if ultralytics absent
- [X] T068 [US3] Run `pytest tests/test_yolo_detector.py -v` → expect 2 passed
- [X] T069 [US3] Wire YOLO mode in `app/api/job.py` `start_job()`: when `settings["mode"] == "yolo"`, import `yolo_detector` instead of `detection_engine`; wrap `ImportError` in `HTTPException(400, "ultralytics not installed...")`

**Checkpoint**: US3 complete — individual clips export, 720p works, folder picker works, wall-clock times visible, YOLO mode selectable. ✅

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Non-functional improvements and platform hardening.

- [X] T070 [P] Create `app/utils/system.py` — `get_cpu_percent()` via psutil, `get_ram_percent()` via psutil, `get_cpu_temp()` (platform-guarded; returns None on Windows); `open_folder(path)` delegates to `shell.platform_utils.open_folder(path)` (avoid duplicate implementation — shell.platform_utils is canonical)
- [X] T071 [P] Create `shell/tray.py` — `QSystemTrayIcon` with Show / Quit actions; double-click restores window; `QSystemTrayIcon.ActivationReason.DoubleClick` handler
- [X] T072 [P] Wire tray icon in `launcher.py`: instantiate `TrayIcon(window)` after `window.show()`; set `app.setQuitOnLastWindowClosed(False)`
- [X] T073 [P] Update `static/js/pages/processing.js` to poll `GET /api/job` for system stats display (CPU %, status) every 3s
- [X] T074 Run full test suite: `pytest tests/ -v --tb=short` → expect all pass, 0 failures
- [X] T075 [P] Cross-platform smoke test: verify `get_ffmpeg()` returns existing path; verify `pathlib.Path` round-trip with space in filename; verify `tempfile.gettempdir()` is writable
- [X] T076 [P] Update `specs/001-cctv-pc-processor/checklists/requirements.md` — mark all items complete; document final FR count (FR-001–FR-018) and validated SCs
- [X] T077 Final commit: `git add . && git commit -m "feat: CCTV PC Video Processor — complete implementation (US1+US2+US3)"`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** (Setup): No dependencies — start immediately
- **Phase 2** (Foundational): Depends on Phase 1 — BLOCKS all user stories
- **Phase 3** (US1 — P1): Depends on Phase 2 — implement first
- **Phase 4** (US2 — P2): Depends on Phase 3 completion (timeline builds on detection)
- **Phase 5** (US3 — P3): Depends on Phase 3; some tasks parallel with Phase 4
- **Final Phase** (Polish): Depends on Phase 5

### User Story Dependencies

- **US1 (P1)**: Foundation + detection engine + export engine + 4 pages + shell + launcher
- **US2 (P2)**: Depends on US1 (needs timeline page, preview API) — not independently startable
- **US3 (P3)**: Core (T058–T065) depends on US1 export engine; YOLO (T066–T069) can run in parallel with US2

### Within Each Phase

- Tests MUST be written and FAIL before implementation
- Engine ports before API layer
- API layer before frontend
- Frontend pages can be built in parallel once API is stable
- Launcher last (needs all components ready)

### Parallel Opportunities

**Phase 2** — all `[P]` tasks runnable in parallel:
T005+T008+T011+T014+T015+T016 simultaneously (all different files)

**Phase 3** — parallelisable within story:
T022+T029 (test writing) simultaneously
T038+T039+T040+T041+T043+T045+T047 (CSS/HTML/static files) simultaneously

**Phase 5** — parallelisable:
T058+T059+T060+T064+T066 simultaneously

---

## Parallel Example: Phase 2 (Foundational)

```bash
# All these can be dispatched as parallel tasks:
Task: "Write failing tests for app/config.py in tests/test_config.py"          # T005
Task: "Write failing tests for app/utils/ffmpeg_path.py in tests/test_ffmpeg_path.py"  # T008
Task: "Write failing tests for app/session.py in tests/test_session.py"        # T011
Task: "Copy app/utils/time_utils.py from Pi version and verify"                # T014
Task: "Copy app/core/log_buffer.py from Pi version and add reset() method"     # T015
Task: "Copy app/utils/ffprobe.py and replace ffprobe string with get_ffprobe()" # T016
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T004)
2. Complete Phase 2: Foundational (T005–T021) — CRITICAL, blocks everything
3. Complete Phase 3: User Story 1 (T022–T051)
4. **STOP AND VALIDATE**: Drop test video → detect → Quick Export → check Desktop
5. All 8 success criteria SC-01, SC-02, SC-03, SC-04, SC-07 verifiable at this point

### Incremental Delivery

1. Foundation ready → User Story 1 → **MVP demo**
2. Add User Story 2 → Timeline + preview → **Investigation use case**
3. Add User Story 3 → Full export options + YOLO → **Complete feature**

### Parallel Team Strategy

After Phase 2 (Foundational) is complete:
- Developer A: US1 backend (T022–T037)
- Developer B: US1 frontend (T038–T046)
- Developer C: US1 shell + launcher (T047–T051)
Stories integrate at T051 smoke test.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task in the same phase
- `[US1/US2/US3]` = user story traceability
- Write test → confirm fail → implement → confirm pass → commit
- Stop at each **Checkpoint** to validate the story independently before proceeding
- Constitution Principle III (Test-First) is non-negotiable: never commit implementation without a prior failing test for that unit
