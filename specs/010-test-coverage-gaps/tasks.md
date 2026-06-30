# Tasks: Phase 10 — Test Coverage Gaps

**Input**: Design documents from `specs/010-test-coverage-gaps/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ quickstart.md ✅

**Organization**: Tasks grouped by user story. Each story is independently testable.
**TDD**: All tasks write tests (the deliverable IS tests — Principle III self-referential).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Maps to spec.md user story (US1–US6)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Extend `tests/conftest.py` with shared fixtures needed by US1, US2, and US6 test files.

- [ ] T001 Extend `tests/conftest.py` — add only `ready_session` fixture (the `client` fixture already exists in conftest.py — do NOT add `app_client`). The `ready_session` fixture: call `import app.session as session_module` then `session_module.reset()` then `session_module.update(status="ready", job_id="test-job-001", source_path="/fake/video.mp4", source_info={"fps": 25, "duration_s": 10, "width": 1920, "height": 1080})` and `yield`. The fixture must be function-scoped to isolate state between tests. Run `pytest tests/ -v --co -q` to confirm fixture is discoverable.

**Checkpoint**: `tests/conftest.py` importable with no errors; `pytest --fixtures` shows `ready_session`.

---

## Phase 2: User Story 1 — Job Lifecycle Test Coverage (Priority: P1) 🎯 MVP

**Goal**: `start_job`, `cancel_job`, `get_events` fully covered by tests that run without a video file.

**Independent Test**: `pytest tests/test_api_job_lifecycle.py -v` passes all tests.

**Data-model entities used**: TestSession (conftest `ready_session`), MockDetector, FakeDetector — see `specs/010-test-coverage-gaps/data-model.md`.
**Research decisions**: Decision 1 (polling loop), Decision 4 (monkeypatch target = `app.core.detection_engine.run`).

- [ ] T002 [US1] Create `tests/test_api_job_lifecycle.py` — class `TestStartJobStateMachine` with 4 tests:
  (a) `test_reject_when_detecting`: set session status to "detecting" directly, POST /api/job/start → assert HTTP 400;
  (b) `test_reject_when_idle_no_job`: session in default idle state (no reset to ready), POST /api/job/start → assert HTTP 400;
  (c) `test_returns_detecting_status`: use `ready_session` + monkeypatch `app.core.detection_engine.run` to `lambda **kw: None`, POST /api/job/start → assert `response.json()["status"] == "detecting"` (key check, not exact dict match — `start_job` returns the full session snapshot);
  (d) `test_yolo_missing_returns_400`: use `ready_session` + monkeypatch `builtins.__import__` to raise ImportError for "ultralytics", POST /api/job/start with `{"mode": "yolo"}` → assert HTTP 400. Run `pytest tests/test_api_job_lifecycle.py::TestStartJobStateMachine -v` — all 4 must pass.

- [ ] T003 [US1] Append class `TestStartJobThreadLifecycle` to `tests/test_api_job_lifecycle.py` with 3 tests using FakeDetector (sleeps 50ms, calls on_event twice — exact signature from `data-model.md §FakeDetector`):
  (a) `test_thread_completes_with_two_events`: monkeypatch `app.core.detection_engine.run` with `fake_detector`, POST /api/job/start, poll `session.snapshot()["status"]` with 50ms sleep up to 5s deadline, assert final status == "completed" and `event_count == 2`;
  (b) `test_thread_exception_sets_error_status`: monkeypatch `app.core.detection_engine.run` to `def raise_fn(**kw): raise RuntimeError("boom")`, POST /api/job/start, poll until status != "detecting" (5s deadline), assert status == "error" and `error_msg == "boom"`;
  (c) `test_cancel_stops_thread`: monkeypatch with slow_detector (sleeps 2s, checks cancel_event before emitting), POST /api/job/start, immediately POST /api/job/cancel, poll until status != "detecting" (5s deadline), assert status == "cancelled". Run `pytest tests/test_api_job_lifecycle.py::TestStartJobThreadLifecycle -v` — all 3 must pass.

- [ ] T004 [US1] Append 3 standalone test functions to `tests/test_api_job_lifecycle.py`:
  (a) `test_cancel_job_sets_cancelled_status`: use `ready_session`, monkeypatch detection_engine, POST /api/job/start, POST /api/job/cancel → assert `response.json()["status"] == "cancelled"` (key check, not exact dict match);
  (b) `test_get_events_returns_empty_list`: use `ready_session`, GET /api/job/events → assert response is `[]`;
  (c) `test_get_events_after_detection`: use `ready_session` + FakeDetector, POST /api/job/start, poll to completed, GET /api/job/events → assert `len(events) == 2`. Run `pytest tests/test_api_job_lifecycle.py -v` — all 10 tests must pass. Commit: `test(010): add job lifecycle tests (US1) [P10]`.

**Checkpoint**: 10 new tests, all passing without video file. `pytest tests/test_api_job_lifecycle.py -v` shows 10 PASSED.

---

## Phase 3: User Story 2 — Shell Bridge API Coverage (Priority: P1)

**Goal**: All 6 shell bridge acceptance criteria covered by tests.

**Independent Test**: `pytest tests/test_api_shell_bridge.py -v` passes all tests.

**Research decision used**: Decision 6 (session.output_path is used by open-folder, not output_dir).

- [ ] T005 [US2] Create `tests/test_api_shell_bridge.py` with 3 tests:
  (a) `test_set_filepath_stores_path`: POST /api/shell/filepath with `{"path": "/tmp/test.mp4"}` → assert HTTP 200, then `session.snapshot()["pending_path"] == "/tmp/test.mp4"`;
  (b) `test_get_pending_path_returns_and_clears`: set `session.update(pending_path="/tmp/test.mp4")`, GET /api/shell/pending-path → assert `{"path": "/tmp/test.mp4"}`, then call again → assert `{"path": null}`;
  (c) `test_get_pending_path_returns_null_when_empty`: GET /api/shell/pending-path with no pending path → assert `{"path": null}`. Run `pytest tests/test_api_shell_bridge.py -v`.

- [ ] T006 [US2] Append 3 more tests to `tests/test_api_shell_bridge.py`:
  (a) `test_set_output_dir_updates_session`: POST /api/shell/set-output-dir with `{"output_dir": "/home/user/outputs"}` → assert response `{"ok": true, ...}` and `session.snapshot()["output_dir"] == "/home/user/outputs"`;
  (b) `test_open_folder_calls_platform_open`: monkeypatch `app.api.shell_bridge._open_folder` with `MagicMock()` (shell_bridge.py uses `from shell.platform_utils import open_folder as _open_folder` — patch the local binding, not the original), set `session.update(output_path="/home/user/outputs/video_export.mp4")`, POST /api/shell/open-folder → assert mock called with `"/home/user/outputs"` (parent dir) and response `{"ok": true}`;
  (c) `test_open_folder_returns_false_when_no_output_path`: POST /api/shell/open-folder with no output_path set → assert response `{"ok": false}` (NOT HTTP 400). Run `pytest tests/test_api_shell_bridge.py -v` — all 6 must pass. Commit: `test(010): add shell bridge tests (US2) [P10]`.

**Checkpoint**: 6 new tests, all passing. `pytest tests/test_api_shell_bridge.py -v` shows 6 PASSED.

---

## Phase 4: User Story 3 — Utility Class Contract Coverage (Priority: P2)

**Goal**: LogBuffer pub/sub and ClipIndexer graceful degradation both covered.

**Independent Test**: `pytest tests/test_log_buffer.py tests/test_clip_indexer.py -v` passes all tests.

- [ ] T007 [P] [US3] Create `tests/test_log_buffer.py` — 5 tests. Import `from app.core.log_buffer import LogBuffer` and create a fresh `LogBuffer()` per test (NOT the module-level singleton):
  (a) `test_subscribe_replays_history`: append 3 lines, subscribe → queue has 3 items immediately;
  (b) `test_append_calls_call_soon_threadsafe`: subscribe to get queue, set `buf._loop = MagicMock()`, append one line → assert `buf._loop.call_soon_threadsafe.called` with `(queue.put_nowait, "line")` args;
  (c) `test_ring_buffer_cap`: monkeypatch `app.core.log_buffer.LOG_RING_SIZE = 3` (log_buffer.py does `from app.config import LOG_RING_SIZE` — patch the local binding in the log_buffer module, not app.config), create fresh `LogBuffer()`, append 4 lines, subscribe → queue has exactly 3 items (oldest dropped);
  (d) `test_reset_clears_only_target_job`: append to job_a and job_b, reset job_a, subscribe to job_b → still receives job_b's lines; subscribe to job_a → empty queue;
  (e) `test_close_sends_done_sentinel`: subscribe, set `buf._loop = MagicMock()`, call `buf.close(job_id)` → assert `call_soon_threadsafe` called with `(queue.put_nowait, "__DONE__")`. Run `pytest tests/test_log_buffer.py -v`.

- [ ] T008 [P] [US3] Create `tests/test_clip_indexer.py` — 5 tests. Import `from app.core.clip_indexer import ClipIndexer`:
  (a) `test_is_available_returns_false_when_no_open_clip`: monkeypatch `ClipIndexer.is_available` to return `False`, call `is_available()` → assert `False`;
  (b) `test_embed_returns_none_when_unavailable`: monkeypatch `ClipIndexer.is_available` to return `False`, call `embed(Path("/fake/image.jpg"))` → assert `None` and no exception;
  (c) `test_embed_returns_none_on_do_embed_exception`: monkeypatch `ClipIndexer.is_available` to return `True`, monkeypatch `ClipIndexer._do_embed` to raise `RuntimeError("gpu error")`, call `embed(Path("/fake/image.jpg"))` → assert `None` and no exception;
  (d) `test_embed_returns_sidecar_path_on_success`: monkeypatch `is_available` True, monkeypatch `_do_embed` to return `"/tmp/image.clip.npy"`, call `embed(Path("/fake/image.jpg"))` → assert return value is `"/tmp/image.clip.npy"`;
  (e) `test_embed_never_raises_to_caller`: monkeypatch `is_available` True, monkeypatch `_do_embed` to raise `Exception("anything")`, call `embed(Path("/x"))` → confirm no exception propagates. Run `pytest tests/test_clip_indexer.py -v`. After both T007+T008 pass: Commit `test(010): add LogBuffer and ClipIndexer tests (US3) [P10]`.

**Checkpoint**: 10 new tests, all passing. `pytest tests/test_log_buffer.py tests/test_clip_indexer.py -v` shows 10 PASSED.

---

## Phase 5: User Story 4 — Narrative Synthesizer Coverage (Priority: P2)

**Goal**: seconds_to_clock, timeline_entries, and NarrativeSynthesizer class all tested.

**Independent Test**: `pytest tests/test_narrative_synthesizer.py -v` shows ≥ 13 tests passing.

**Research decision used**: Decision 7 — expected values: `seconds_to_clock(0)=="00:00"`, `seconds_to_clock(90)=="01:30"`, `seconds_to_clock(3661)=="01:01:01"`.

- [ ] T009 [US4] Append 10 new test functions to `tests/test_narrative_synthesizer.py` (APPEND only — do not overwrite existing 4 tests). Import `from app.core.narrative_synthesizer import seconds_to_clock, timeline_entries, NarrativeSynthesizer`. Note: `temporal_analysis` and `trend_direction` are instance methods — instantiate `ns = NarrativeSynthesizer()` before calling them:
  (a) `test_seconds_to_clock_zero` → assert `"00:00"`;
  (b) `test_seconds_to_clock_90s` → assert `"01:30"`;
  (c) `test_seconds_to_clock_over_hour` → `seconds_to_clock(3661)` → assert `"01:01:01"`;
  (d) `test_seconds_to_clock_boundary_one_hour` → `seconds_to_clock(3600)` → assert `"01:00:00"`;
  (e) `test_timeline_entries_returns_correct_structure`: call `timeline_entries([{"start_s":0.0,"end_s":1.0,"zone_label":None,"peak_motion_score":0.8,"event_index":0}], {})` → assert result has 1 entry with keys `event_num`, `start_clock`, `end_clock`, `duration_s`, `label`, `confidence_pct`, `description`;
  (f) `test_timeline_entries_empty_list` → `timeline_entries([], {})` → assert `[]`;
  (g) `test_timeline_entries_uses_description` → call with event_index=0 and descriptions={0: "a person entered"} → assert entry["description"] == "a person entered"`;
  (h) `test_timeline_entries_missing_description_defaults_to_na` → call with empty descriptions dict → assert entry["description"] == "N/A"`;
  (i) `test_narrative_synthesizer_temporal_analysis`: `ns = NarrativeSynthesizer()`, events at start_s=[1,2,10,11,20,21] with duration_s=30, call `ns.temporal_analysis(events, 30)` → assert result has keys "early", "middle", "late", "peak_third";
  (j) `test_narrative_synthesizer_trend_direction_rising`: `ns = NarrativeSynthesizer()`, events = `[{"start_s": 60}, {"start_s": 70}, {"start_s": 80}]` with duration_s=100 (all events in second half), call `ns.trend_direction(events, 100)` → assert result == `"rising"`. Run `pytest tests/test_narrative_synthesizer.py -v` — ≥ 14 PASSED. Commit: `test(010): expand narrative synthesizer tests (US4) [P10]`.

**Checkpoint**: ≥ 14 tests passing in test_narrative_synthesizer.py.

---

## Phase 6: User Story 5 — Qt Shell Logic (Priority: P2)

**Goal**: _get_desktop_path(), closeEvent, check_shutdown tested without a display.

**Independent Test**: `pytest tests/test_shell_logic.py -v` passes all tests without ImportError.

**Data-model entity used**: QtStubRegistry — see `specs/010-test-coverage-gaps/data-model.md §QtStubRegistry` for exact stub structure.

- [ ] T010 [US5] Create `tests/test_shell_logic.py` — define `_make_qt_stubs()` function using `unittest.mock.MagicMock` for all PyQt6 module stubs (follow `data-model.md §QtStubRegistry` but also add `"PyQt6"`, `"PyQt6.QtWebEngineCore"` with `QWebEnginePage` and `QWebEngineSettings` as MagicMock attributes, `"PyQt6.QtGui"` must also include `QDragEnterEvent` and `QDropEvent`, and `"PyQt6.QtWidgets"` must also include `QFileDialog`). Define `mw_module` pytest fixture that patches `sys.modules`, deletes `shell.main_window` from sys.modules, imports fresh `shell.main_window`, yields it, and restores originals in finally block (pattern in `data-model.md §QtStubRegistry`). Add test:
  `test_get_desktop_path_returns_nonempty_string`: using `mw_module`, call `mw._get_desktop_path()` (module-level function, NOT `mw.MainWindow._get_desktop_path()`) → assert result is a non-empty string. Run `pytest tests/test_shell_logic.py::test_get_desktop_path_returns_nonempty_string -v`.

- [ ] T011 [US5] Append 4 more tests to `tests/test_shell_logic.py`:
  (a) `test_close_event_hides_when_detecting`: in `mw_module` fixture context, patch `requests.get` to return a mock with `.json()` → `{"status": "detecting"}`, instantiate `MainWindow(mock_app)`, create a `QCloseEvent` mock, call `closeEvent(event)` → assert `event.ignore()` was called (or `QApplication.quit` was NOT called);
  (b) `test_close_event_quits_when_idle`: patch `requests.get` to return `{"status": "idle"}`, call `closeEvent(event)` → assert `QApplication.quit()` was called;
  (c) `test_close_event_quits_when_backend_raises`: patch `requests.get` to raise `ConnectionError("refused")`, call `closeEvent(event)` → assert `QApplication.quit()` was called (fail-safe: no backend = treat as idle);
  (d) `test_check_shutdown_schedules_qtimer`: `check_shutdown` is an inner function inside `_handle_browse_flags`, not a public method. Test via `_handle_browse_flags()`: using `mw_module`, instantiate `mw_instance = mw.MainWindow(backend_port=9999)`, then configure `mw_instance._view.page().runJavaScript.side_effect` with a helper that calls the callback with `True` when the script contains `"_cctvShutdown"` and `"= false"` is NOT in the script (i.e., the flag-check call), and calls callback with `False` or `'{"flag": false, "path": ""}'` for all other script patterns. Call `mw_instance._handle_browse_flags()`. Then assert `sys.modules["PyQt6.QtCore"].QTimer.singleShot.call_args[0][0] == 2000`. Run `pytest tests/test_shell_logic.py -v` — all 5 must pass. Commit: `test(010): add Qt shell logic tests (US5) [P10]`.

**Checkpoint**: 5 new tests, all passing without display or PyQt6 installation.

---

## Phase 7: User Story 6 — SSE, System API, Thumbnails, CI Blind Spots (Priority: P3)

**Goal**: System API key contracts, SSE idle safety, thumbnail error path, and CI mock pairs.

**Independent Test**: `pytest tests/test_api_system.py tests/test_stream.py tests/test_thumbnail_gen.py -v` passes all tests.

- [ ] T012 [P] [US6] Create `tests/test_api_system.py` — 2 tests using `client` from conftest (the existing fixture — do NOT add `app_client`):
  (a) `test_system_stats_has_correct_keys`: GET /api/system/stats → assert response JSON has exactly keys `cpu_pct`, `ram_pct`, `cpu_temp` (no `cpu_percent`, no `ram_percent`);
  (b) `test_system_capabilities_yolo_false_when_not_installed`: monkeypatch `builtins.__import__` to raise ImportError for "ultralytics", GET /api/system/capabilities → assert response `{"yolo_available": false}`. Run `pytest tests/test_api_system.py -v`.

- [ ] T013 [P] [US6] Append 2 tests to `tests/test_stream.py` (APPEND only — preserve existing 4 tests):
  (a) `test_sse_idle_safety_exits_after_max_polls`: `import app.api.stream as stream_mod`, monkeypatch `stream_mod.POLL_INTERVAL_S = 0.001` and `stream_mod._MAX_IDLE_POLLS = 3` (this makes the generator time out after 3×1ms instead of 10×500ms — no asyncio.wait_for mocking needed), then `asyncio.run(collect(_event_generator("test-job")))` where `collect` drains the async generator into a list. Assert the generator exits cleanly (no exception) and at least one emitted chunk contains `"keepalive"`;
  (b) `test_sse_handles_generator_exit`: wrap generator iteration in try/except GeneratorExit and verify no exception propagates. Run `pytest tests/test_stream.py -v`.

- [ ] T014 [P] [US6] Append 1 test to `tests/test_thumbnail_gen.py` (APPEND only):
  `test_thumbnail_gen_handles_ffmpeg_failure`: monkeypatch `subprocess.run` to raise `subprocess.CalledProcessError(1, "ffmpeg")`, call `thumbnail_gen.run(job_id="x", source_path="/fake.mp4", events=[...], logger=lambda m: None)` → assert function returns without raising. Run `pytest tests/test_thumbnail_gen.py -v`. After all three pass: Commit `test(010): add system API, SSE safety, thumbnail tests (US6) [P10]`.

- [ ] T015 [US6] Add 9 CI mock-counterpart tests to address US6 AC6 (spec: "mock-paired variants of CI-skipped tests"). These tests use monkeypatching instead of real video/hardware and must have NO `@pytest.mark.skipif` guard:

  **3 tests in `tests/test_api_job.py`** (APPEND after existing tests):
  (a) `test_create_job_valid_file_mocked`: monkeypatch `app.utils.ffprobe.probe` to return `{"fps": 25.0, "duration_s": 10.0, "width": 1920, "height": 1080}` and `pathlib.Path.is_file` to return `True`, POST /api/job/create with `{"source_path": "/fake/video.mp4"}` → assert HTTP 200 and `resp.json()["status"] == "ready"`;
  (b) `test_preview_frame_extracts_and_caches_mocked`: monkeypatch `app.utils.ffprobe.probe` + `Path.is_file` (same as above), then monkeypatch `subprocess.run` to write a small JPEG to the output path and return `MagicMock(returncode=0)`, call GET /api/job/preview-frame twice → assert first call HTTP 200 + content-type image/jpeg, assert `subprocess.run` called exactly once (second call served from cache);
  (c) `test_create_job_cancels_inflight_detection_mocked`: monkeypatch `app.utils.ffprobe.probe` + `Path.is_file`, POST /api/job/create → assert `app.api.job._cancel_event.is_set()` is True after call.

  **3 tests in `tests/test_detection_engine.py`** (APPEND after existing tests):
  (d) `test_run_emits_progress_and_events_with_mocked_capture`: monkeypatch `cv2.VideoCapture` to return a stub that yields 5 synthetic 320×240 uint8 numpy frames then EOF, call `detection_engine.run(source_path="/fake.mp4", source_info={"fps":25,"duration_s":0.2,"width":320,"height":240}, settings={"threshold":20,"min_duration":0,"frame_skip":0}, cancel_event=threading.Event(), on_progress=progress_cb, on_event=event_cb, job_dir=tmp_path)` → assert `on_progress` called at least once with value in [0.0, 1.0];
  (e) `test_run_respects_cancel_with_mocked_capture`: same cv2 mock but set cancel_event before calling run → assert run returns without calling `on_event`;
  (f) `test_run_handles_capture_open_failure_mocked`: monkeypatch `cv2.VideoCapture.__init__` so `.isOpened()` returns `False` → assert run returns without raising.

  **3 tests in `tests/test_ffprobe.py`** (APPEND after existing tests):
  (g) `test_probe_returns_fps_from_mocked_output`: monkeypatch `subprocess.run` to return a CompletedProcess with stdout=valid ffprobe JSON (fps=30, duration=5.0, width=1280, height=720), call `from app.utils.ffprobe import probe; result = probe("/fake.mp4")` → assert `result["fps"] == pytest.approx(30.0)` and `result["duration_s"] == pytest.approx(5.0)`;
  (h) `test_probe_raises_on_subprocess_error`: monkeypatch `subprocess.run` to raise `subprocess.CalledProcessError(1, "ffprobe")` → assert `probe("/fake.mp4")` raises an exception (any);
  (i) `test_probe_handles_fractional_fps_mocked`: monkeypatch subprocess to return ffprobe JSON with `r_frame_rate: "30000/1001"` → assert result fps is approximately 29.97.

  Run `pytest tests/test_api_job.py tests/test_detection_engine.py tests/test_ffprobe.py -v` — all 9 new tests must pass. Commit: `test(010): add CI blind-spot mock counterparts (US6 AC6) [P10]`.

**Checkpoint**: ≥ 14 new tests in Phase 7, all passing without video/GPU/display.

---

## Phase 8: Polish & Validation

**Purpose**: Full suite validation, documentation updates, final commit.

- [ ] T016 Run `pytest tests/ -v` and confirm: total test count ≥ 195, 0 failures, 0 errors, any skips are pre-existing video-dependent tests only. If count < 195, identify which story's tests are missing and add them. Expected new test count: 43 (T002–T014) + 1 T009(j) + 2 T011(c,d) + 9 T015 = 55 new tests; 140 + 55 = 195 total.

- [ ] T017 [P] Update `README.md` — increment test count badge/mention from 140 to current count; add Phase 10 to the "Phases completed" section.

- [ ] T018 [P] Update `USER_MANUAL.md` — if any test-running instructions reference the old test count, update them.

- [ ] T019 Update `ROADMAP.md` — mark Phase 10 test coverage as completed; note next priority.

- [ ] T020 Final commit: `test(010): complete Phase 10 test coverage gaps — NNN tests [P10]` (replace NNN with actual count). Run `git log --oneline -5` to confirm all phase commits are present.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **US1 (Phase 2)**: Depends on T001 (conftest fixtures)
- **US2 (Phase 3)**: Depends on T001 (conftest fixtures)
- **US3a+b (Phase 4)**: Independent — no conftest dependency; can run after Phase 1 or in parallel
- **US4 (Phase 5)**: Independent — pure function tests; can run in parallel with any phase
- **US5 (Phase 6)**: Independent — Qt stub tests; can run in parallel with any phase
- **US6 (Phase 7)**: Depends on T001 for system API tests; T013/T014/T015 independent
- **Polish (Phase 8)**: Depends on all user story phases complete

### Within US1 (Phase 2)

- T002 (state machine) → T003 (thread lifecycle) → T004 (cancel + events)
- Must be sequential: each appends to the same file

### Parallel Opportunities

- T007 and T008 can run in parallel (different files)
- T012, T013, T014 can run in parallel (different files)
- T015 can run after T012/T013/T014 complete (appends to different files)
- T017, T018 can run in parallel (different files)

---

## Parallel Execution Examples

### US3 (both in parallel)

```
Task T007: Create tests/test_log_buffer.py (5 tests)
Task T008: Create tests/test_clip_indexer.py (5 tests)
→ then: pytest tests/test_log_buffer.py tests/test_clip_indexer.py -v
```

### US6 (first three in parallel, then T015)

```
Task T012: Create tests/test_api_system.py (2 tests)
Task T013: Expand tests/test_stream.py (+2 tests)
Task T014: Expand tests/test_thumbnail_gen.py (+1 test)
→ then: T015: append 9 CI mock-counterpart tests to test_api_job.py, test_detection_engine.py, test_ffprobe.py
→ then: pytest tests/test_api_system.py tests/test_stream.py tests/test_thumbnail_gen.py tests/test_api_job.py tests/test_detection_engine.py tests/test_ffprobe.py -v
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. T001 — extend conftest.py
2. T002, T003, T004 — all job lifecycle tests
3. STOP: run `pytest tests/test_api_job_lifecycle.py -v` → 10 PASSED ✓
4. Optionally deploy and demo

### Incremental Delivery

1. Setup (T001) → US1 (T002-T004) → US2 (T005-T006) → US3 (T007-T008) → US4 (T009) → US5 (T010-T011) → US6 (T012-T015) → Polish (T016-T020)
2. Each phase independently runnable with `pytest <file> -v`

---

## Notes

- [P] tasks = different files, no dependencies on each other
- [Story] maps each task to its acceptance criteria in spec.md
- Monkeypatch targets: always `app.core.detection_engine.run` (not `_run` in job.py)
- Session fixtures: always use `session.reset()` + `session.update()` — never mutate `_state` directly
- Qt stubs: delete `shell.main_window` from `sys.modules` before import in fixture setup
- LogBuffer: create fresh `LogBuffer()` per test — do not reuse module-level singleton
- CI constraint: all 20 tasks must produce tests that pass with `pytest tests/ -v` in a clean environment (no video, no GPU, no display)
- T015 (CI mock counterparts): tests must append to existing files, not replace; use `# ── Phase 10 mock counterparts ──` comment header to demarcate additions
