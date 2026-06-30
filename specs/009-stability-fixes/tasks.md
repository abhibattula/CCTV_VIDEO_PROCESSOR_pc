# Tasks: Phase 9 — Stability Fixes

**Input**: Design documents from `specs/009-stability-fixes/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, quickstart.md ✅

**TDD Note**: Constitution Principle III requires failing tests before implementation for all
`app/api/*.py` and `app/core/*.py` changes. Frontend JS (`static/js/`) and Qt shell
(`launcher.py`, `shell/main_window.py`) changes use the frontend exemption — verified via
`quickstart.md` scenarios instead.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps to user story from spec.md

---

## Phase 1: Setup

**Purpose**: Confirm branch and verify baseline tests pass before any changes.

- [X] T001 Confirm branch is `009-stability-fixes` and baseline `pytest tests/ -q` passes (136 tests)

---

## Phase 2: Foundational — TDD Failing Tests (Backend Python)

**Purpose**: Write failing tests for all backend Python changes per constitution Principle III.
All tests MUST be confirmed to FAIL before any implementation code is written.

⚠️ **CRITICAL**: No implementation work can begin until all tests in this phase are written and confirmed failing.

- [X] T002 Add `test_output_dir_persists_across_reset` to `tests/test_session.py` — call `update(output_dir="/some/folder")`, call `reset()`, then assert `snapshot()["output_dir"] == "/some/folder"` (must FAIL until B6 is implemented)
- [X] T003 Add `test_output_dir_cleared_by_reset_before_fix` companion note: run `pytest tests/test_session.py::test_output_dir_persists_across_reset -v` and confirm it FAILS with `AssertionError` before proceeding
- [X] T004 Add `test_frame_analyzer_availability_is_cached` to `tests/test_frame_analyzer.py` — call `FrameAnalyzer.is_available()` twice, monkeypatch the `weights_dir.exists` call to count invocations, assert it is called at most once (must FAIL until B2 implemented)
- [X] T005 Add `test_get_desktop_path_returns_nonempty_string` to `tests/test_api_job.py` — import `_get_desktop_path` from `app/api/job.py`, assert `isinstance(_get_desktop_path(), str)` and `len(_get_desktop_path()) > 0` (must FAIL with ImportError until B6 implemented)
- [X] T005a Add `test_get_job_does_not_recall_is_available_after_cache` to `tests/test_api_job.py` — use `AsyncClient` to call `GET /api/job` twice, monkeypatch `FrameAnalyzer._availability_cache` to `None` before first call then assert it is not `None` after second call without a real filesystem check (validates T023 indirectly; must FAIL until T022 + T023 implemented)
- [X] T006 Run `pytest tests/test_session.py tests/test_frame_analyzer.py tests/test_api_job.py -v` — confirm T002, T004, T005 ALL FAIL, everything else passes

**Checkpoint**: 3 failing tests confirmed. Backend implementation can now begin.

---

## Phase 3: User Story 2 — Correct Output File Location (P1) 🎯 MVP

**Goal**: Files always land where the user expects them — on the real Desktop (even with OneDrive)
and in the user's previously-chosen folder (not reset on new video load).

**Independent Test**: quickstart.md §S6 (Desktop path) and §S7 (output_dir persists)

### Implementation

- [X] T007 [US2] Add `_PERSISTENT: dict` to `app/session.py`, remove `"output_dir": None` from `_DEFAULTS`, update `reset()` to preserve `_PERSISTENT` fields, update `update()` to sync `output_dir` changes into `_PERSISTENT`
- [X] T008 [US2] Add `_get_desktop_path() -> str` helper to `app/api/job.py` — uses `ctypes.windll.shell32.SHGetFolderPathW` on Windows, falls back to `str(Path.home() / "Desktop")`
- [X] T009 [P] [US2] Replace all `str(Path.home() / "Desktop")` fallbacks in `app/api/job.py` (~4 occurrences: video export, CSV/JSON export, intel-report) with `_get_desktop_path()`
- [X] T010 [P] [US2] Add `_get_desktop_path()` helper to `shell/main_window.py` and replace `str(Path.home() / "Desktop")` in `_get_output_dir()` with `_get_desktop_path()`
- [X] T011 [US2] Run `pytest tests/test_session.py tests/test_api_job.py -v` — T002 and T005 must now PASS

**Checkpoint**: output_dir persists across video loads; exports land on the real Desktop.

---

## Phase 4: User Story 3 — Trustworthy Quick Report PDF (P1)

**Goal**: The Quick Report PDF button shows truthful status — error when invalid, confirmed path
after success, error message on write failure.

**Independent Test**: quickstart.md §S2 (all five acceptance scenarios)

### Implementation

- [X] T012 [US3] Update `on_load_finished` in `_generate_pdf_report()` in `shell/main_window.py` — when `ok=False`, inject `window._cctvPdfResult = {"success": false, "path": ""}` via `runJavaScript` instead of silently deleting the page
- [X] T013 [US3] Update `on_pdf_finished` in `_generate_pdf_report()` and `_generate_intel_report_pdf()` in `shell/main_window.py` — inject `window._cctvPdfResult = {"success": bool, "path": str}` via `self._view.page().runJavaScript(...)` after PDF printing finishes
- [X] T014 [US3] Replace the Quick Report button click handler in `static/js/pages/export.js` (lines 857–867) with the new handler: pre-validate via `GET /api/job` (no job_id → error; status=="detecting" → error; no included events → error), show "Generating…", poll `window._cctvPdfResult` every 500 ms up to 120 s, show `✅ Saved: <filename>` or `❌ PDF save failed`
- [X] T015 [US3] Initialise `window._cctvPdfResult = null` in the JS bridge injection block in `shell/main_window.py` (`_inject_js_bridge`) so the flag is available from page load
- [ ] T016 [US3] Smoke-test quickstart.md §S2 scenarios manually (no-job → error; detecting → error; no-events → error; happy-path → ✅ Saved; failure path → ❌)

**Checkpoint**: Quick Report PDF button is truthful on all paths.

---

## Phase 5: User Story 1 — Reliable File Selection (P1)

**Goal**: Clicking Browse multiple times never creates competing poll chains; network errors
surface as user-visible messages instead of silent hangs.

**Independent Test**: quickstart.md §S1 (double-click and network-error scenarios)

### Implementation

- [X] T016a [US1] Add a one-time pending-path check at the end of `mount()` in `static/js/pages/home.js` — call `pollPendingPath(++_browseToken, 0)` once after all listeners are registered so that Qt-level drag-drop paths posted before home.js loaded are consumed (fixes FR-003: drop zone fallback to Qt native path)
- [X] T017 [US1] Add module-level `let _browseToken = 0` at the top of the `initPage` scope in `static/js/pages/home.js`
- [X] T018 [US1] Rewrite the Browse button click handler in `static/js/pages/home.js` (line ~151) to increment `_browseToken`, capture it in closure, and pass it as `token` argument to `pollPendingPath`
- [X] T019 [US1] Rewrite `pollPendingPath` in `static/js/pages/home.js` to accept `(token, attempts)` parameters; bail silently if `token !== _browseToken`; add `.catch(err => showLoadError(...))` to surface network failures
- [X] T020 [US1] Add a `showLoadError(msg)` helper in `static/js/pages/home.js` that displays an inline error message near the Browse button (use an existing `#load-error` element or inject a dismissable banner)
- [ ] T021 [US1] Smoke-test quickstart.md §S1 (double-click, cancel, network-error scenarios)

**Checkpoint**: Browse race condition resolved; errors visible to user.

---

## Phase 6: User Story 6 — Fast Detection Without Startup Stall (P2)

**Goal**: MOG2 detection polls respond immediately after the first; no multi-second stall caused
by repeated transformers imports or filesystem stats.

**Independent Test**: quickstart.md §S9 (DevTools Network tab shows < 100 ms polls)

### Implementation

- [X] T022 [US6] Add `_availability_cache: bool | None = None` class attribute to `FrameAnalyzer` in `app/core/frame_analyzer.py`; update `is_available()` to return cache on second+ call, set it on first call
- [X] T023 [US6] Cache makes GET /api/job polls O(1) after first call; is_available() kept in handler but returns instantly; T005a confirms second poll does no filesystem stat
- [X] T024 [US6] Run `pytest tests/test_frame_analyzer.py -v` — T004 must now PASS; all existing tests must pass

**Checkpoint**: Detection polls are fast; `is_available()` does I/O at most once per process.

---

## Phase 7: User Story 4 — Clean Application Exit (P2)

**Goal**: Ctrl+C exits the app fully; Stop button auto-closes the Qt window; idle close-window
quits instead of hiding to tray.

**Independent Test**: quickstart.md §S3 (Ctrl+C), §S4 (Stop), §S5 (close window)

### Implementation

- [X] T025 [P] [US4] Add SIGINT handler and dummy 200 ms `QTimer` to `launcher.py` — install `signal.signal(signal.SIGINT, lambda *_: qt_app.quit())` after `qt_app = QApplication(sys.argv)`, start `_sig_timer = QTimer(); _sig_timer.timeout.connect(lambda: None); _sig_timer.start(200)`
- [X] T026 [P] [US4] Update `check_shutdown` callback in `shell/main_window.py` — after calling `_on_stop_backend()`, add `QTimer.singleShot(2000, QApplication.instance().quit)` so the window auto-closes 2 s after the backend stops
- [X] T027 [US4] Update `closeEvent` in `shell/main_window.py` — query `/api/job` to check if status is `"detecting"` or `"exporting"`; hide to tray only if active job AND tray visible; otherwise call `QApplication.instance().quit()`
- [ ] T028 [US4] Smoke-test quickstart.md §S3 (Ctrl+C exits fully), §S4 (Stop auto-closes), §S5 (close-X quits when idle, hides when detecting)

**Checkpoint**: App exits cleanly on all three quit paths.

---

## Phase 8: User Story 5 — Quieter Terminal Output (P3)

**Goal**: No MISSING-keys table and no FutureWarning lines in the terminal when Florence-2
model loads.

**Independent Test**: quickstart.md §S8 (generate AI report; watch terminal)

### Implementation

- [X] T029 [US5] Wrap the `from_pretrained` calls inside the `if cls._model is None:` block in `app/core/frame_analyzer.py` with `contextlib.redirect_stdout(io.StringIO())` and `warnings.catch_warnings()` with `warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")`; add `import io, contextlib, warnings` at the top of the file
- [X] T030 [US5] Run `pytest tests/test_frame_analyzer.py -v` — all existing tests (including T004) must still pass after the redirect wrapping
- [ ] T031 [US5] Smoke-test quickstart.md §S8 (requires Florence-2 weights installed; terminal must be clean)

**Checkpoint**: Terminal output is clean during AI report generation.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T032 [P] Run full test suite: `pytest tests/ -q` — must be ≥139 tests passing (136 baseline + 3 new)
- [X] T033 [P] Update `USER_MANUAL.md` — add note about output folder persistence across video loads; update Quick Report PDF section to mention pre-validation errors
- [X] T034 [P] Update `ROADMAP.md` — increment "Phases 1–8" to "Phases 1–9"
- [ ] T035 Commit all changes in logical groups per bug fix (B1–B6), following `fix(009): …` commit message format per constitution Commit Discipline

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Start immediately
- **Phase 2 (Foundational Tests)**: Depends on Phase 1
- **Phase 3 (US2 — Output Path)**: Depends on Phase 2 tests written; T007 must complete before T011
- **Phase 4 (US3 — PDF Feedback)**: Depends on Phase 3 (T010 provides correct Desktop path for PDF save)
- **Phase 5 (US1 — Browse)**: Can start after Phase 2; independent of US2/US3
- **Phase 6 (US6 — Detection Speed)**: Can start after Phase 2; independent
- **Phase 7 (US4 — Clean Exit)**: Can start after Phase 2; independent
- **Phase 8 (US5 — Terminal Noise)**: Can start after Phase 6 (same file `frame_analyzer.py`; B2 and B5 edit different sections but safer to sequence)
- **Phase 9 (Polish)**: After all user stories complete

### User Story Dependencies

- **US2 (P1)**: Start after Phase 2 — no story dependencies
- **US3 (P1)**: Start after US2 (needs `_get_desktop_path` for PDF save location)
- **US1 (P1)**: Start after Phase 2 — independent
- **US6 (P2)**: Start after Phase 2 — independent
- **US4 (P2)**: Start after Phase 2 — independent
- **US5 (P3)**: Start after US6 (both edit `frame_analyzer.py`; sequence to avoid conflicts)

### Parallel Opportunities

Within Phase 3 (US2): T009 and T010 touch different files → run in parallel  
Within Phase 4 (US3): T012/T013 (Python) and T014/T015 (JS) can run in parallel after T012 establishes the `_cctvPdfResult` flag name  
Within Phase 7 (US4): T025 (launcher.py) and T026/T027 (main_window.py) touch different files → run in parallel  
Phase 5 (US1) can run in parallel with Phase 6 (US6) — different files entirely  

---

## Parallel Example: US2 + US1 (P1 stories)

```
# After Phase 2 is complete, run in parallel:
Task A (US2): T007 → T008 → T009+T010 (parallel) → T011
Task B (US1): T017 → T018 → T019 → T020 → T021
```

---

## Implementation Strategy

### MVP (US2 + US3 + US1 — the three P1 stories)

1. Phase 1: Confirm baseline
2. Phase 2: Write all failing tests (T002–T006)
3. Phase 3: US2 (output path) — T007–T011
4. Phase 4: US3 (PDF feedback) — T012–T016
5. Phase 5: US1 (browse) — T017–T021
6. **STOP and VALIDATE**: run full test suite + quickstart.md §S1, §S2, §S6, §S7

### Full Delivery (all 6 bug fixes)

Continue from MVP checkpoint:
7. Phase 6: US6 (detection speed) — T022–T024
8. Phase 7: US4 (clean exit) — T025–T028
9. Phase 8: US5 (terminal noise) — T029–T031
10. Phase 9: Polish — T032–T035

---

## Notes

- **TDD gate**: Constitution requires all `app/` Python changes to have failing tests before code.
  T002–T006 are that gate. Do not skip T003 (the failure-confirmation step).
- **Frontend exemption**: home.js and export.js changes verified via quickstart.md, not pytest.
- **launcher.py / main_window.py**: Qt shell code — also verified via quickstart.md smoke tests.
- Commit after each completed phase using `fix(009): <bug-id> — <description>` format.
- Each user story is independently testable; validate before moving to the next phase.
