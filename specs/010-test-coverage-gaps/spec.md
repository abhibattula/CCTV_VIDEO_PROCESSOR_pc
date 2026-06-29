# Feature Specification: Phase 10 — Test Coverage Gaps

**Feature Branch**: `010-test-coverage-gaps`  
**Created**: 2026-06-29  
**Status**: Approved for Planning  

---

## Clarifications

### Session 2026-06-29

- Q: How should US1 thread lifecycle tests detect that the fake-detector thread has finished? → A: Polling loop — `deadline = time.monotonic() + 5; while time.monotonic() < deadline: if session.snapshot()["status"] == "completed": break; time.sleep(0.05)` (tests production-realistic poll behaviour with a natural CI timeout)
- Q: How should LogBuffer asyncio broadcasting tests provide an event loop without running real asyncio? → A: Mock `LogBuffer._loop` with a stub object and assert `call_soon_threadsafe(q.put_nowait, line)` was called with correct arguments (unit-tests the bridge call without real async machinery)

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Job Lifecycle Test Coverage (Priority: P1)

A developer modifying the job start, cancel, or query endpoints needs automated
checks that catch regressions without requiring a real video file. Currently the
entire `start_job` handler (~60 lines), `cancel_job`, and `get_events` have zero
automated coverage — the most critical code paths in the application.

**Why this priority**: `start_job` orchestrates the detection thread, session
transitions, and error handling. Any regression here breaks the core user
workflow silently in CI.

**Independent Test**: Can be fully tested by verifying session state transitions,
HTTP response codes, and thread completion behaviour using a fake detector
function, delivering a verifiable job lifecycle without a real video file.

**Acceptance Scenarios**:

1. **Given** session status is `"idle"`, **When** `POST /api/job/start` is called, **Then** response is `{"status": "detecting"}` and session transitions to `"detecting"`
2. **Given** session status is already `"detecting"`, **When** `POST /api/job/start` is called again, **Then** response is HTTP 400 with an informative message
3. **Given** `start_job` is called with a fake detector that raises an exception, **When** the detection thread runs, **Then** session status becomes `"error"` and `error_msg` is populated
4. **Given** `ultralytics` package is absent and mode is `"yolo"`, **When** `POST /api/job/start` is called, **Then** response is HTTP 400 before any thread is spawned
5. **Given** a fake detector emits 2 events then completes, **When** the thread finishes, **Then** session status becomes `"completed"` and `event_count` equals 2 (thread completion detected by polling `session.snapshot()["status"]` in a 5-second deadline loop with 50 ms sleep intervals)
6. **Given** a job is running, **When** `POST /api/job/cancel` is called, **Then** the cancel signal is set and session eventually becomes `"cancelled"`
7. **Given** session has events stored, **When** `GET /api/job/events` is called, **Then** the response contains the correct event list

---

### User Story 2 — Shell Bridge API Coverage (Priority: P1)

A developer making changes to the Browse/drag-drop pipeline (`/api/shell/*`)
needs regression tests. Phase 9 fixed the browse race condition (B1) but added
no backend tests for the four shell bridge endpoints.

**Why this priority**: Shell bridge endpoints gate the primary file selection UX.
Without tests, the Phase 9 B1 fix has no regression guard.

**Independent Test**: Can be fully tested by calling the shell bridge endpoints
directly via the FastAPI test client and asserting session state changes, independently
of the detection pipeline.

**Acceptance Scenarios**:

1. **Given** a valid file path, **When** `POST /api/shell/filepath` is called, **Then** the path is stored in session pending state and HTTP 200 is returned
2. **Given** a path was stored, **When** `GET /api/shell/pending-path` is called, **Then** the stored path is returned and cleared atomically (second call returns `null`)
3. **Given** nothing is pending, **When** `GET /api/shell/pending-path` is called, **Then** response is `{"path": null}`
4. **Given** a valid directory path, **When** `POST /api/shell/output-dir` is called, **Then** `session.output_dir` is updated and HTTP 200 is returned
5. **Given** an empty string is sent, **When** `POST /api/shell/output-dir` is called, **Then** HTTP 400 is returned
6. **Given** an output folder is set in session, **When** `POST /api/shell/open-output-folder` is called, **Then** the OS folder-open command is invoked with the correct path (mocked)
7. **Given** no output folder is set, **When** `POST /api/shell/open-output-folder` is called, **Then** HTTP 400 is returned

---

### User Story 3 — Utility Class Contract Coverage (Priority: P2)

A developer working on the log streaming or CLIP embedding pipeline needs unit
tests that document the contracts of `LogBuffer` and `ClipIndexer` and catch
regressions in their internal behaviour.

**Why this priority**: `LogBuffer` is used in every job run; a regression in its
ring-buffer or pub/sub logic would break all streaming output. `ClipIndexer` is
a graceful-degradation wrapper; tests verify it never raises to callers.

**Independent Test**: Both classes can be fully tested with no external dependencies:
`LogBuffer` via direct method calls; `ClipIndexer` via monkeypatching its availability
check and embed function.

**Acceptance Scenarios — LogBuffer**:

1. **Given** lines are appended for a job, **When** `subscribe(job_id)` is called, **Then** the queue immediately contains the replayed history lines
2. **Given** a subscriber queue exists and `LogBuffer._loop` is replaced with a mock stub, **When** `append(job_id, line)` is called, **Then** `_loop.call_soon_threadsafe(q.put_nowait, line)` is called with the correct arguments (verified via mock assertion)
3. **Given** a job's history is at ring-buffer capacity, **When** one more line is appended, **Then** the oldest line is dropped and buffer size does not exceed the limit
4. **Given** a job's history exists, **When** `reset(job_id)` is called, **Then** that job's history is cleared and other jobs' histories are unaffected
5. **Given** `close(job_id)` is called, **When** a subscriber reads the queue, **Then** the sentinel `"__DONE__"` is eventually received

**Acceptance Scenarios — ClipIndexer**:

1. **Given** `open_clip` package is not installed, **When** `is_available()` is called, **Then** it returns `False`
2. **Given** `is_available()` is monkeypatched to return `False`, **When** `embed(image_path)` is called, **Then** it returns `None` without raising
3. **Given** `_do_embed` raises an exception, **When** `embed(image_path)` is called, **Then** it returns `None` without raising (graceful degradation)
4. **Given** `_do_embed` is monkeypatched to return a sidecar path, **When** `embed(image_path)` is called, **Then** it returns that path
5. **Given** `is_available()` returns `True` but the image file does not exist, **When** `embed(image_path)` is called, **Then** it returns `None` without raising

---

### User Story 4 — Narrative Synthesizer Coverage (Priority: P2)

A developer modifying the report text generation functions needs comprehensive
checks across the 318-line `narrative_synthesizer.py` module. Currently only
4 tests exist, leaving `seconds_to_clock`, `timeline_entries`, and the
`NarrativeSynthesizer` class untested.

**Why this priority**: The narrative module drives all human-readable report
content. Gaps here allow silent regressions in output formatting.

**Independent Test**: Pure-function module with no external dependencies — all
scenarios testable by calling functions directly with synthetic event data.

**Acceptance Scenarios**:

1. **Given** `s = 0`, **When** `seconds_to_clock(0)` is called, **Then** result is `"00:00"`
2. **Given** `s = 90`, **When** `seconds_to_clock(90)` is called, **Then** result is `"01:30"`
3. **Given** `s = 3661`, **When** `seconds_to_clock(3661)` is called, **Then** result is `"01:01:01"`
4. **Given** a list of 3 events with `start_s` values, **When** `timeline_entries(events, {})` is called, **Then** result contains 3 entries each with `event_num`, `start_clock`, `end_clock`, `duration_s`, `label`, `confidence_pct`, `description`
5. **Given** an empty events list, **When** `timeline_entries([], {})` is called, **Then** result is `[]`
6. **Given** descriptions dict contains an entry for `event_index=0`, **When** `timeline_entries` is called, **Then** that description appears verbatim in the entry
7. **Given** a missing description for an event, **When** `timeline_entries` is called, **Then** the `description` field defaults to `"N/A"`
8. **Given** events spread across all three time thirds, **When** `temporal_analysis(events, duration_s)` is called, **Then** result has `"early"`, `"middle"`, `"late"` counts and `"peak_third"` identifying the most active third
9. **Given** second-half events are more than 1.5× first-half, **When** `trend_direction(events, duration_s)` is called, **Then** result is `"rising"`

---

### User Story 5 — Qt Shell Logic Coverage (Priority: P2)

A developer modifying `shell/main_window.py` needs tests for the extractable
business logic that does not require a running display. Phase 9 fixed B3 (close
behaviour), B4 (PDF result bridge), and B6 (Desktop path) — none of these fixes
have regression tests.

**Why this priority**: Phase 9 fixes to shutdown and PDF feedback have no
automated guards; any future edit can silently break them.

**Independent Test**: PyQt6 modules are replaced with minimal stub types before
importing `shell.main_window`, allowing pure-Python logic paths to be exercised
without a display server.

**Acceptance Scenarios**:

1. **Given** Windows shell API is available, **When** `_get_desktop_path()` is called, **Then** it returns a non-empty string (Windows CSIDL path or `~/Desktop` fallback)
2. **Given** backend reports status `"detecting"`, **When** `closeEvent` is triggered, **Then** the close event is ignored (window stays open or hides to tray, `quit()` not called)
3. **Given** backend reports status `"idle"`, **When** `closeEvent` is triggered, **Then** `quit()` is called
4. **Given** backend request raises an exception, **When** `closeEvent` is triggered, **Then** `quit()` is called (fail-safe)
5. **Given** backend has stopped, **When** `check_shutdown` runs, **Then** `QTimer.singleShot` is called with a 2000 ms delay

---

### User Story 6 — SSE Stream, System API, and CI Blind Spots (Priority: P3)

A developer working on the SSE stream, system API endpoints, or thumbnail
generation needs tests for currently uncovered paths. Additionally, 12 tests
silently skip in CI due to missing video files; each needs a mock counterpart
that always runs.

**Why this priority**: CI blind spots mean broken code can ship undetected.
System API and SSE edge cases have never been validated.

**Independent Test**: System API testable via test client; SSE testable via
asyncio; mock counterparts testable with monkeypatched subprocess calls.

**Acceptance Scenarios — System API**:

1. **Given** a running app, **When** `GET /api/system/stats` is called, **Then** response JSON contains exactly keys `cpu_pct`, `ram_pct`, `cpu_temp`
2. **Given** a running app without `ultralytics`, **When** `GET /api/system/capabilities` is called, **Then** response JSON contains `{"yolo_available": false}`

**Acceptance Scenarios — SSE stream**:

3. **Given** `_MAX_IDLE_POLLS` consecutive idle polls occur, **When** the generator loop runs, **Then** it exits cleanly (does not hang)
4. **Given** a `GeneratorExit` is raised during iteration, **When** the generator handles it, **Then** no exception propagates to the caller

**Acceptance Scenarios — Thumbnail error path**:

5. **Given** the ffmpeg subprocess call fails, **When** `thumbnail_gen.run()` is called, **Then** the error is logged and the function returns without raising

**Acceptance Scenarios — CI mock counterparts**:

6. **Given** no real video file is present, **When** mock-paired variants of the 12 skipped tests run, **Then** they pass by exercising the same logic path through monkeypatching

---

### Edge Cases

- What happens when `start_job` is called while status is `"exporting"`? (same 400 rejection as `"detecting"`)
- What happens when `LogBuffer.close()` is called with no subscribers? (no-op, no exception)
- What happens when `ClipIndexer.embed()` is called with a path that is a directory? (returns None without raising)
- What happens when `seconds_to_clock` receives a float with sub-second precision? (truncated to int)
- What happens when `timeline_entries` receives events with no `event_index` key? (defaults to 0)

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The test suite MUST include checks for all six acceptance-criteria groups in US1 (job lifecycle state machine and thread lifecycle)
- **FR-002**: The test suite MUST include checks for all seven acceptance-criteria items in US2 (shell bridge endpoints)
- **FR-003**: The test suite MUST include checks for the five LogBuffer acceptance criteria and five ClipIndexer acceptance criteria in US3
- **FR-004**: The test suite MUST include checks for all nine narrative synthesizer acceptance criteria in US4, using correct expected values derived from the actual implementation
- **FR-005**: The test suite MUST include checks for all five Qt shell logic acceptance criteria in US5 using PyQt6 module mocking
- **FR-006**: The test suite MUST include checks for all six acceptance-criteria items in US6 (system API, SSE, thumbnail, CI mock pairs)
- **FR-007**: All new checks MUST pass in a standard developer environment without a connected video file, camera hardware, GPU, or display server
- **FR-008**: No existing passing check MUST be broken by the new additions
- **FR-009**: New checks for CI blind spots MUST run unconditionally (no `pytest.mark.skipif` on real-hardware conditions)
- **FR-010**: Fake-detector checks for US1 thread lifecycle MUST use a detector that sleeps 50 ms then calls `on_event` twice; thread completion MUST be detected by polling `session.snapshot()["status"]` with 50 ms intervals up to a 5-second deadline (no busy-wait, no `thread.join`)

### Key Entities

- **TestSession**: Reusable fixture that resets `app.session` to a known `"ready"` state before each test, providing `job_id`, `source_path`, `source_info`
- **FakeDetector**: A callable matching the `detection_engine.run` signature that sleeps 50 ms, optionally checks `cancel_event`, then emits 2 synthetic events via `on_event` — used for thread lifecycle tests without a real video
- **MockDetector**: A callable matching the `detection_engine.run` signature that returns immediately (lambda) — used for state machine tests where thread speed matters
- **QtStubRegistry**: A dict of minimal PyQt6 stub types (QApplication, QMainWindow, QTimer, QWebEngineView, etc.) inserted into `sys.modules` before importing `shell.main_window`, removed and restored after each test

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 55 new automated checks are added, raising the total suite count from 140 to at least 195
- **SC-002**: Zero new checks use `pytest.mark.skipif` with hardware-availability conditions; all new checks pass unconditionally in a standard developer machine environment
- **SC-003**: All 6 zero-coverage modules identified in the audit (shell bridge, system API, ClipIndexer, LogBuffer, narrative synthesizer gaps, Qt shell logic) have at least one passing check after this phase
- **SC-004**: The critical job lifecycle path (`start_job` through `completed` status) has both a state-machine check (instant mock) and a thread lifecycle check (fake detector with real thread completion)
- **SC-005**: All new checks pass without modification when run in CI (no video file, no ffprobe, no GPU, no display)
- **SC-006**: No previously passing check is broken by the new additions (suite passes as a whole)

---

## Assumptions

- The test suite runs with `pytest` and uses the FastAPI `TestClient` for endpoint tests
- `app.session` can be reset between tests by importing the module and calling `session.reset()` or by direct state manipulation
- The `detection_engine.run` function can be monkeypatched at the module level for job lifecycle tests
- PyQt6 is not installed in the CI environment; Qt shell tests must work via `sys.modules` patching regardless of whether PyQt6 is installed
- `open_clip` is not installed in the standard CI environment; ClipIndexer tests must not depend on it being present
- The `LogBuffer` ring buffer size is controlled by `app.config.LOG_RING_SIZE` and is at least 100 lines
- All test files live under the `tests/` directory and follow the existing `test_*.py` naming convention
- `report_renderer.py` and `launcher.py` are out of scope for this phase (see Out of Scope section)

---

## Out of Scope

- Full Qt GUI automation (requires display server; deferred to a future phase)
- YOLO end-to-end tests (requires `ultralytics` package and model weights)
- Florence-2 model tests (requires model weights; covered by existing `test_frame_analyzer.py` mocks)
- Performance and load tests
- `launcher.py` SIGINT handler (requires spawning a subprocess with OS signal delivery)
- `report_renderer.py` (Jinja2 template wrapper; low risk, deferred)
- `llm_synthesizer.py` timeout/offline path (deferred; requires careful asyncio mocking)
