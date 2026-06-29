# Spec: Phase 10 — Test Coverage Gaps

**Branch:** `010-test-coverage-gaps` off `009-stability-fixes`
**Date:** 2026-06-29
**Status:** Approved for implementation

---

## Overview

The CCTV Video Processor has accumulated 140 tests across 9 phases. A full coverage audit
(conducted 2026-06-29) identified critical untested paths, zero-coverage modules, and a CI
blind spot where video-dependent tests silently skip. This phase closes those gaps through
~58 new tests across 7 new or expanded test files, raising the suite to ~198 tests.

---

## Coverage Audit — Findings

### Zero-Coverage Modules (no test file exists)

| Module | Lines | Risk | Details |
|--------|-------|------|---------|
| `app/api/shell_bridge.py` | 59 | HIGH | 4 endpoints: `set_filepath`, `get_pending_path`, `open_output_folder`, `set_output_dir` — Browse/drag-drop path (B1 fix in Phase 9 has no regression tests) |
| `app/api/system.py` | 28 | LOW | `system_stats`, `system_capabilities` endpoints |
| `app/core/clip_indexer.py` | 73 | MEDIUM | `ClipIndexer` class used by export pipeline |
| `app/core/log_buffer.py` | 59 | MEDIUM | Ring buffer with thread safety; used in every job run |
| `app/core/report_renderer.py` | 26 | LOW | Template rendering wrapper |
| `shell/main_window.py` | ~500 | HIGH | Extractable logic: `closeEvent`, `check_shutdown`, `_get_output_dir`, PDF result bridge |
| `launcher.py` | ~60 | MEDIUM | SIGINT handler + QTimer setup |

### Critical Missing Cases in Covered Modules

| Gap | File | Risk |
|-----|------|------|
| `start_job` endpoint — entire 60-line handler untested | `app/api/job.py` | CRITICAL |
| `cancel_job` endpoint — zero tests | `app/api/job.py` | HIGH |
| `get_events` endpoint — zero tests | `app/api/job.py` | MEDIUM |
| Status conflict: `POST /job/start` while status is `"detecting"` | `app/api/job.py` | HIGH |
| Thread exception propagates to `session.error_msg` | `app/api/job.py` | HIGH |
| YOLO ImportError path in `start_job` | `app/api/job.py` | MEDIUM |

### CI Blind Spot — Silently Skipped Tests

| Test file | Skipped | Condition |
|-----------|---------|-----------|
| `test_detection_engine.py` | 5 of 8 | No test video |
| `test_ffprobe.py` | 2 of 9 | No test video |
| `test_api_job.py` | 3 of 31 | No test video |
| `test_ffmpeg_path.py` | 2 of 4 | No ffprobe binary |

Each video-dependent test needs a paired mock test that exercises the same logic path
without a real video file, so regressions are caught in CI.

### Thin Coverage (meaningful logic, few tests)

| Module | Lines | Current Tests | Untested Logic |
|--------|-------|---------------|----------------|
| `app/core/narrative_synthesizer.py` | 318 | 4 | `timeline_entries`, `seconds_to_clock` edges, `NarrativeSynthesizer` class |
| `app/api/stream.py` | 157 | 4 | Cancel mid-stream, client reconnect, heartbeat timing |
| `app/core/thumbnail_gen.py` | 57 | 2 | ffmpeg failure path |
| `app/core/llm_synthesizer.py` | 90 | 4 | Timeout path, offline fallback |

---

## User Stories

### US1 — `start_job`, `cancel_job`, `get_events` Coverage (P1)

**Goal:** The core job lifecycle — start, run, cancel, query — is covered by automated tests
that run without a real video file. Developers can refactor `start_job` with confidence.

**Acceptance Criteria:**
- `POST /job/start` returns `{"status": "detecting"}` and transitions session to `detecting`
- `POST /job/start` returns 400 when status is already `"detecting"`
- Thread exception causes session status to become `"error"` with `error_msg` set
- YOLO mode with missing `ultralytics` package returns 400 with helpful message
- With fake detector: status transitions `detecting → completed`, `event_count` matches emitted events
- `POST /job/cancel` sets `_cancel_event`, session status becomes `"cancelled"`
- Fake detector respects `cancel_event.is_set()` and stops early
- `GET /job/events` returns current events list from session

**New file:** `tests/test_api_job_lifecycle.py`
**Test count:** ~14

---

### US2 — Shell Bridge Endpoint Coverage (P1)

**Goal:** The Browse/drag-drop pipeline (`/api/shell/*`) is regression-tested. Phase 9 fixed
B1 (browse race condition) but added no backend API tests for the bridge endpoints.

**Acceptance Criteria:**
- `POST /api/shell/filepath` stores path in session pending state; returns 200
- `GET /api/shell/pending-path` returns stored path and clears it on first read
- `GET /api/shell/pending-path` returns `{"path": null}` when nothing pending
- `POST /api/shell/output-dir` updates `session.output_dir` and returns 200
- `POST /api/shell/output-dir` with empty string returns 400
- `GET /api/shell/open-output-folder` calls `os.startfile` with correct path (mocked)
- `GET /api/shell/open-output-folder` returns 400 when no output folder set

**New file:** `tests/test_api_shell_bridge.py`
**Test count:** ~8

---

### US3 — `log_buffer` and `clip_indexer` Unit Coverage (P2)

**Goal:** The two zero-coverage utility classes used internally by the job pipeline have
unit tests that document their contracts and catch regressions.

**Acceptance criteria — LogBuffer:**
- `append(job_id, line)` stores lines retrievable via `get(job_id)`
- Ring buffer caps at configured size; oldest lines dropped when full
- `reset(job_id)` clears only that job's buffer, leaving others intact
- Concurrent appends from multiple threads do not corrupt internal state
- `get` on unknown job_id returns empty list (not KeyError)

**Acceptance criteria — ClipIndexer:**
- `add(event)` stores event retrievable by index
- `get(idx)` returns correct event for valid index
- `get(idx)` raises `IndexError` for out-of-range index
- `clear()` resets the index to empty
- `count` property returns correct number of indexed events

**New files:** `tests/test_log_buffer.py`, `tests/test_clip_indexer.py`
**Test count:** ~12

---

### US4 — Narrative Synthesizer Gap Coverage (P2)

**Goal:** The 318-line `narrative_synthesizer.py` module — which drives all human-readable
report text — has comprehensive tests for its untested functions and class.

**Acceptance Criteria:**
- `seconds_to_clock(0)` returns `"0:00:00"`
- `seconds_to_clock(3661)` returns `"1:01:01"`
- `seconds_to_clock(90)` returns `"0:01:30"`
- `timeline_entries` returns one entry per event, sorted by `start_s`
- `timeline_entries` with empty events list returns empty list
- `timeline_entries` includes `description` field from provided descriptions dict
- `NarrativeSynthesizer.run()` calls `executive_summary`, `activity_stats`, `timeline_entries`
- `NarrativeSynthesizer.run()` result contains keys `summary`, `stats`, `timeline`

**Expanded file:** `tests/test_narrative_synthesizer.py` (append, preserve existing)
**Test count:** ~8

---

### US5 — Extractable Qt Shell Logic (P2)

**Goal:** Business logic inside `shell/main_window.py` that does not require a running Qt
display is unit-tested with PyQt6 mocked at import time. This provides regression coverage
for the Phase 9 B3/B4/B6 fixes without needing a GUI environment.

**Qt mocking strategy:** `sys.modules` patching of `PyQt6.QtWidgets`, `PyQt6.QtCore`,
`PyQt6.QtWebEngineWidgets`, `PyQt6.QtGui` before importing `shell.main_window` — only the
pure-Python logic paths are exercised.

**Acceptance Criteria:**
- `_get_desktop_path()` in `shell/main_window.py` returns a non-empty string (Windows + fallback)
- `closeEvent` logic: when `requests.get` returns status `"detecting"`, event is ignored (hide)
- `closeEvent` logic: when `requests.get` returns status `"idle"`, `quit()` is called
- `closeEvent` logic: when `requests.get` raises (backend down), `quit()` is called
- `check_shutdown` calls `QTimer.singleShot` with 2000ms after backend stops
- `_inject_js_bridge` injects `window._cctvPdfResult = null` into the JS string

**New file:** `tests/test_shell_logic.py`
**Test count:** ~6

---

### US6 — SSE Stream, System API, and Completeness (P3)

**Goal:** Remaining low-hanging gaps are closed: SSE cancel behaviour, system API contract,
thumbnail error path, and paired mock tests for CI blind spots.

**Acceptance Criteria — SSE stream:**
- When `cancel_event` is set mid-stream, `_event_generator` stops yielding within one poll cycle
- Generator yields `data: ping` heartbeat when no events pending
- Client disconnect (GeneratorExit) is handled without exception propagating

**Acceptance Criteria — System API:**
- `GET /api/system/stats` returns JSON with keys `cpu_percent`, `ram_percent`, `disk_free_gb`
- `GET /api/system/capabilities` returns JSON with key `florence_available` (bool)

**Acceptance Criteria — Thumbnail error path:**
- `thumbnail_gen.run()` with a failing ffmpeg command (mocked) does not raise; logs error and continues

**Acceptance Criteria — CI blind spot mock pairs:**
- `test_create_job_valid_file` has a paired mock version that does not require test video
- `test_preview_frame_extracts_and_caches` has a paired mock version
- `test_thumbnail_stage_progress_after_run` has a paired mock version

**New/expanded files:** expand `tests/test_stream.py`, add `tests/test_api_system.py`, expand `tests/test_thumbnail_gen.py`
**Test count:** ~10

---

## New and Expanded Test Files

| File | Story | Status |
|------|-------|--------|
| `tests/test_api_job_lifecycle.py` | US1 | New |
| `tests/test_api_shell_bridge.py` | US2 | New |
| `tests/test_log_buffer.py` | US3 | New |
| `tests/test_clip_indexer.py` | US3 | New |
| `tests/test_narrative_synthesizer.py` | US4 | Expand |
| `tests/test_shell_logic.py` | US5 | New |
| `tests/test_stream.py` | US6 | Expand |
| `tests/test_api_system.py` | US6 | New |
| `tests/test_thumbnail_gen.py` | US6 | Expand |

---

## Success Criteria

| Criterion | Target |
|-----------|--------|
| Total test count | ≥ 195 (from 140) |
| Zero-coverage modules eliminated | 6 of 7 (Qt shell partially covered via mocks) |
| `start_job` endpoint coverage | All 6 acceptance criteria passing |
| CI blind spot mock pairs | 3 new mock variants, always run |
| All new tests pass without test video or ffprobe binary | Yes |
| No existing test broken | Yes |

---

## Out of Scope

- Full Qt GUI automation (requires display server; deferred)
- YOLO detector end-to-end tests (requires ultralytics + model weights)
- Florence-2 model tests (requires weights; covered by `test_frame_analyzer.py` mocks)
- Performance/load tests
- `launcher.py` SIGINT handler (requires spawning a subprocess with signal delivery)
