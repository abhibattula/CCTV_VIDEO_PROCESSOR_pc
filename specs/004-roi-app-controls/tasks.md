# Tasks: Phase 4 — ROI Selection, Stop Application, New Project

**Input**: Design documents from `specs/004-roi-app-controls/`
**Branch**: `004-roi-app-controls`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅
contracts/api.md ✅ quickstart.md ✅ checklists/risk-review.md ✅ (all 17 items
resolved)

**Constitution Principle III**: Tests are MANDATORY for new backend logic in
`app/api/*.py`/`app/core/*.py` — written before implementation, confirmed
failing before code is written. There is no frontend test runner in this stack
(unchanged Phase 2/3 precedent); frontend tasks are verified by directly
driving the real app via a temporary script, deleted after use.

**Organization**: 5 phases — Setup → US1 (ROI Selection) → US2 (Stop
Application) → US3 (New Project) → Polish. The three user stories are
behaviorally independent, but **US1 and US3 both touch `app/api/job.py`**
(different functions) and **US2 and US3 both touch `static/js/app.js`**
(different `installX()` call sites) — see the Dependencies section for the
resulting sequencing notes. There is no Foundational phase, since nothing here
is needed by more than one story beyond those two shared files.

---

## Phase 1: Setup

**Purpose**: Each story is self-contained; there is no shared infrastructure
to scaffold ahead of time this phase.

**No tasks in this phase.**

---

## Phase 2: User Story 1 — ROI Selection (Priority: P1) 🎯 MVP

**Goal**: After loading a video, the user sees its first frame and can draw
one or more free-form regions on it; detection restricts its activity report
to the union of those regions, or analyzes the full frame if none are drawn.
Regions never persist past the currently-loaded video.

**Independent Test** (quickstart.md Scenario 1): Load a video with motion in
two distinct areas, draw a region around only one, run detection, confirm only
that area's motion is reported; confirm full-frame behavior is unchanged when
no regions are drawn; confirm regions reset when a different file loads.

- [X] T001 [US1] Write failing tests in `tests/test_api_job.py` for the new
  preview-frame endpoint — `test_preview_frame_no_active_job_returns_400` (no
  `source_path`/`job_id` in session → 400), `test_preview_frame_extracts_and_caches`
  (using the existing small sample video fixture this test file already uses
  elsewhere — first call invokes ffmpeg and writes `preview_frame.jpg` into the
  job dir, second call serves the cached file without re-invoking ffmpeg —
  assert on file mtime or a subprocess-call-count mock to prove caching),
  `test_preview_frame_extraction_failure_returns_500` (point `source_path` at a
  corrupt/empty file, confirm 500 with an `"error"` key, not an uncaught
  exception); run `pytest tests/test_api_job.py -v` to confirm all three fail
  (endpoint doesn't exist yet)
- [X] T002 [US1] Implement `GET /api/job/preview-frame` in `app/api/job.py` per
  `plan.md`/`contracts/api.md` — add `import subprocess` and `FileResponse`
  (not currently imported in this file) to the existing import block; run
  `pytest tests/test_api_job.py -v` to confirm T001's tests now pass
- [X] T003 [P] [US1] Create `static/js/roi.js` exporting
  `mountRoiEditor(container, { onChange })` per `plan.md`'s design — `<img>` +
  absolutely-positioned `<canvas>` overlay kept pixel-synced on load/resize;
  click-to-place-vertex, close-near-first-vertex (≥3 points, per the spec's
  FR-P4-002), "Cancel Shape"/"Clear All" controls, a region chip list with
  editable label + delete (×) per region; returns `{ setImageSrc, reset,
  destroy }`; `onChange` fires `[{ label, points: [[x,y],...] }, ...]` on every
  region mutation
- [X] T004 [P] [US1] Create `static/css/roi.css` with `.roi-editor__stage`
  (`position: relative`), `.roi-editor__canvas` (`position: absolute; inset:
  0; cursor: crosshair`), `.roi-chip` and related selectors per `plan.md`,
  extending only existing custom properties (`var(--border)`, `var(--accent)`,
  `var(--surface2)`, `var(--radius)`); link it from `static/index.html` after
  the existing `home.css` link
- [X] T005 [US1] In `static/js/pages/home.js`: add a `<div class="card hidden"
  id="roi-card">` containing `<div id="roi-container"></div>` to the template
  between `#source-info` and `.settings-card`; add `loadRoiPreview()`, called
  right after the existing `resetUiState();` line inside `doLoadFile()` — lazily
  `mountRoiEditor(...)` once, call `roiHandle.reset()` on every call (enforcing
  per-job-only regions per FR-P4-005), then `roiHandle.setImageSrc("/api/job/preview-frame?t=" + Date.now())`;
  replace the hardcoded `zones: []` in the `/api/job/start` request body with
  the live `liveZones` array maintained by the `onChange` callback; if the
  preview image fails to load, show "Preview unavailable — detection will run
  on the full frame" in `#roi-card` instead of the editor (per the spec's edge
  case) and leave `liveZones` as `[]`
- [X] T006 [US1] Manual verification per `quickstart.md` Scenario 1 (all 8
  steps, not a subset) — write a temporary script (e.g. `_verify_roi.py`)
  launching the real `shell.main_window.MainWindow` against the real backend
  with a synthetic test video that has motion staged in **three** distinct,
  known frame areas (so one can be left as a deliberately-excluded control);
  drive it via `runJavaScript` to: confirm the preview frame appears, draw a
  region around only the first motion area, start detection, confirm via
  `/api/job/events` that only that area's events appear; load a different
  file and confirm the region is gone and a fresh preview shows; run detection
  with zero regions drawn and confirm all motion areas now produce events;
  **draw two separate regions, one around each of the first two motion
  areas, and confirm both produce events while the third, deliberately
  undrawn area does not** (this is the only live test of FR-P4-004's
  union-not-intersection rule — do not skip it); **delete one region via its
  chip's × control and confirm only that region's outline disappears from the
  canvas, then click "Clear All" and confirm the canvas is empty** (FR-P4-003).
  If a rotated-metadata test clip is available, also confirm the drawn region
  still lines up with the correct area after rotation (see research.md's
  Implementation Risks — ffmpeg/OpenCV may handle rotation tags differently);
  if no such clip is available, note this as untested in the verification
  write-up rather than silently skipping it. Delete the script when done.

**Checkpoint**: Scenario 1 from quickstart.md passes. `pytest tests/ -v` is green.

---

## Phase 3: User Story 2 — Stop Application (Priority: P2)

**Goal**: A "Stop" control, visible on every page, lets the user gracefully
shut down the backend (cancelling any in-progress work first) after an
explicit confirmation, while the application window stays open and shows a
"safe to close" message once the backend is confirmed dead.

**Independent Test** (quickstart.md Scenario 2): Click Stop mid-detection,
confirm the warning dialog, confirm declining leaves the app running normally,
confirm confirming cancels the detection and makes the backend unreachable
within 15 seconds while the window remains open showing the result message.

- [X] T007 [US2] In `launcher.py`, replace `_start_backend`'s `uvicorn.run(app,
  host=BACKEND_HOST, port=port, log_level="warning")` call with the
  lower-level pattern from `plan.md`/`research.md` §4 — build a
  `uvicorn.Config(app, host=BACKEND_HOST, port=port, log_level="warning")`,
  wrap it in `uvicorn.Server(config)`, store the instance in a new
  module-level `_uvicorn_server: uvicorn.Server | None = None`, then call
  `server.run()`; add a new `stop_backend()` function that sets
  `_uvicorn_server.should_exit = True` if the server reference is set
- [X] T008 [US2] In `shell/main_window.py`: add `on_stop_backend=None` to
  `MainWindow.__init__`'s parameters, stored as `self._on_stop_backend`; add
  `window._cctvShutdown = false;` to the JS injected by `_inject_js_bridge`;
  extend `_handle_browse_flags` with a third `page.runJavaScript("window._cctvShutdown",
  check_shutdown)` check whose callback clears the flag
  (`window._cctvShutdown = false;`) and calls `self._on_stop_backend()` if set
- [X] T009 [US2] In `launcher.py`'s `main()`, pass
  `on_stop_backend=stop_backend` into the existing `MainWindow(backend_port=backend_port)`
  constructor call
- [X] T010 [P] [US2] Create `static/js/stop-app.js` exporting
  `installStopButton()` per `plan.md` — appends a `.btn-danger` "Stop" button
  to `#app-nav`; click opens a confirmation modal (reusing the
  `.modal-overlay`/`.modal` CSS classes already used by `home.js`'s
  `showDiscardModal`) warning that in-progress work will be abandoned; on
  confirm: `POST /api/job/cancel` first, then set `window._cctvShutdown =
  true`, then poll `GET /api/health` every 500ms (cap ~30 attempts / 15s) —
  a network-level fetch failure (not merely a non-2xx response) means the
  backend is confirmed dead, at which point show `"✅ Application stopped. You
  can close this window now."` **The `job/cancel` call MUST be wrapped so a
  failure never blocks the rest of the flow** —
  `fetch(...).catch(() => {}).finally(() => { window._cctvShutdown = true;
  pollStopped(...); })` — this matters specifically for the case where the
  user clicks Stop a second time after the backend is already dead (spec edge
  case): without the `.catch()`, the rejected fetch would prevent
  `window._cctvShutdown` from ever being (re-)set and leave the UI stuck
  instead of immediately re-showing the "stopped" message.
- [X] T011 [US2] Wire `installStopButton()` into `static/js/app.js` — add
  `import { installStopButton } from "/static/js/stop-app.js";
  installStopButton();` next to the existing `installDebugLog();
  installTheme();` calls
- [X] T012 [US2] Manual verification per `quickstart.md` Scenario 2 — temporary
  script driving the real app: start detection, click Stop, confirm the
  warning dialog appears; click Cancel and confirm `/api/health` still
  succeeds and detection keeps progressing; click Stop again and confirm this
  time, confirm the UI shows "Stopping…" then the "safe to close" message
  within 15 seconds, confirm `/api/health` polled directly is genuinely
  unreachable (not just that the UI claims so), and confirm the Qt window
  itself is still open, responsive, and only closes on an explicit native
  close. Repeat once from an idle (no job running) state. **Then, with the
  backend already confirmed stopped, click "Stop" once more (spec edge
  case) and confirm the UI immediately re-shows the "safe to close" message
  rather than hanging or erroring** — this specifically exercises T010's
  `.catch()` guard. **Also confirm the 15s-timeout path is honest, not
  optimistic**: the T007-T009 review found that when this launcher instance
  reused an already-running backend from a prior process
  (`_our_backend_is_running` path in `launcher.py`), `stop_backend()`
  silently no-ops — `/api/health` keeps succeeding the whole time, so the
  poll loop in `stop-app.js` will exhaust its 15s budget without ever seeing
  a network failure. T010 MUST show a distinct "could not confirm the
  application stopped" message in that case, NOT the same "✅ Application
  stopped" success message — never claim success on a timeout, only on an
  actual confirmed connection failure. Delete the script when done.

**Checkpoint**: Scenario 2 from quickstart.md passes. `pytest tests/ -v`
remains green (this story touches no file under `app/`).

---

## Phase 4: User Story 3 — New Project (Priority: P3)

**Goal**: A "New Project" control, visible on every page, lets the user
abandon the current job (warning first if work would be lost) and return to a
clean upload screen, without restarting the application process.

**Independent Test** (quickstart.md Scenario 3): From Timeline, with
uncollected completed events, click New Project, confirm the warning, confirm
declining leaves the job untouched, confirm confirming returns to a clean Home
with no leftover state; repeat with an actively-running job (different
warning text) and with an idle job (no warning at all).

- [ ] T013 [US3] Write a failing regression test in `tests/test_api_job.py` —
  `test_create_job_cancels_inflight_detection_before_reset`: start a job,
  simulate an in-flight detection by directly checking the module-level
  `_cancel_event` is initially clear, call `POST /api/job/create` again with a
  second source file, then assert `_cancel_event.is_set()` is `True`
  afterward; run `pytest tests/test_api_job.py -v` to confirm it fails (the
  guard doesn't exist yet)
- [ ] T014 [US3] In `app/api/job.py`'s `create_job()`, add `_cancel_event.set()`
  as the first line of the function body, immediately before the existing
  `session.reset()` call; run `pytest tests/test_api_job.py -v` to confirm
  T013 now passes, then `pytest tests/ -v` for the full suite
- [ ] T015 [P] [US3] Create `static/js/new-project.js` exporting
  `installNewProjectButton()` per `plan.md` — appends a `.btn` "New Project"
  button to `#app-nav`; click handler calls `GET /api/job`, then: if status is
  `"detecting"`/`"exporting"` → warning modal about cancelling the running
  operation; else if status is `"completed"` with `events.length > 0` and no
  `output_path` → warning modal about discarding uncollected events; else →
  no modal. On confirm (or the no-modal path): `POST /api/job/cancel`
  (`.catch(() => {})` — best-effort, per the spec's edge case that a failed
  cancel call must not block starting over), `resetUiState()`, `window.go("/")`
- [ ] T016 [US3] Wire `installNewProjectButton()` into `static/js/app.js` —
  add `import { installNewProjectButton } from "/static/js/new-project.js";
  installNewProjectButton();` next to the `installStopButton()` call added in
  T011 (sequenced after T011 since both edit `app.js`)
- [ ] T017 [US3] Manual verification per `quickstart.md` Scenario 3 — temporary
  script driving the real app: complete a job without exporting, go to
  Timeline, click New Project, confirm the uncollected-events warning,
  decline and confirm the job is untouched, confirm again and confirm landing
  on a clean Home form with `/api/job/events` empty after loading a new file
  and no leftover label filter/selection/undo state; start detection on a
  second video, click New Project from Export mid-detection, confirm the
  running-operation warning variant (different text) appears; from a freshly
  loaded but not-yet-started job, click New Project and confirm it proceeds
  with no modal at all. **Time the no-modal path from click to the upload
  screen being visible and confirm it is comfortably under the 5-second bound
  in SC-P4-004** (a simple `performance.now()` delta logged to the debug
  panel is sufficient — this is the only task that actually verifies that
  success criterion, not just New Project's functional behavior). Delete the
  script when done.

**Checkpoint**: Scenario 3 from quickstart.md passes. `pytest tests/ -v`
remains green.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Final full-suite confirmation, combined manual pass, documentation
updates, sign-off.

- [ ] T018 Run `pytest tests/ -v` from project root — confirm all existing
  tests plus the new preview-frame tests (T001) and the cancel-guard
  regression test (T013) pass with no regressions
- [ ] T019 Manual combined smoke test per `quickstart.md`'s "Combined pass"
  section — run all three stories together in one continuous live
  `python launcher.py` session (load a video, draw a region, detect, export,
  New Project into a second video with a different region, detect again, then
  Stop), to catch any cross-feature interaction the per-story scenarios above
  might miss. **Also visually confirm `#app-nav` does not overflow or wrap
  awkwardly at the app's default 1280px window width** now that it holds 4
  route links plus 4 action buttons (debug, theme, Stop, New Project) —
  research.md's Implementation Risks flags this; resize the window narrower
  if it looks tight and note whether `flex-wrap` or an icon-only treatment is
  needed as a follow-up
- [ ] T020 Update `README.md` and `USER_MANUAL.md` to document the three new
  Phase 4 features — ROI region drawing on the Home page, the Stop
  Application control and its confirm/safe-to-close flow, and the New Project
  control and when it warns vs. proceeds immediately
- [ ] T021 Commit completed Phase 4 on branch `004-roi-app-controls` with
  message `feat(phase4): ROI selection, Stop Application, New Project`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Empty — no dependencies, nothing to start
- **Phase 2 (US1)**: No dependencies on other phases; T001 must precede T002
  (TDD — tests written and confirmed failing first); T003/T004 (frontend) can
  proceed in parallel with T001/T002 (backend) since they're different files;
  T005 needs T002 (backend endpoint) and T003 (roi.js) both done; T006
  (verification) needs everything in this phase done
- **Phase 3 (US2)**: No dependencies on Phase 2; T007 must precede T009 (which
  passes the function T007 defines); T008 must precede T009 (same
  constructor-call edit); T010 is independent of T007-T009 until T011 wires
  it in; T012 needs everything in this phase done
- **Phase 4 (US3)**: No *behavioral* dependency on Phase 2 or 3, but **T016
  must come after T011** — both edit `static/js/app.js`, and sequencing avoids
  a merge conflict between two stories' subagents touching the same file; T013
  must precede T014 (TDD); T017 needs everything in this phase done
- **Phase 5 (Polish)**: Depends on all of Phase 2-4 being complete

### Cross-Story File Overlaps (important — do not treat as fully independent)

- **`app/api/job.py`**: modified by both US1 (T002, new `preview_frame()`
  function) and US3 (T014, one line in `create_job()`). Different functions,
  but the same file — implement sequentially (US1 before US3, matching
  priority order), not via two simultaneous subagents.
- **`static/js/app.js`**: modified by both US2 (T011) and US3 (T016).
  Implement T011 before T016 for the same reason.

### Parallel Opportunities

```bash
# Within US1 — backend and frontend can proceed in parallel:
Chain A (backend, TDD): T001 (write tests) → T002 (implement)
Chain B (frontend): T003, T004 (different files, no dependency on each other)
# T005 needs both chains done; T006 needs T005 done.

# Within US2:
Chain A (Qt/launcher): T007 → T008 → T009 (each depends on the previous)
Chain B (frontend): T010 (independent until T011 wires it in)

# Within US3:
Chain A (backend, TDD): T013 (write test) → T014 (implement)
Chain B (frontend): T015 (independent until T016 wires it in)

# Across stories — mostly parallel, EXCEPT the two file overlaps above:
US1 (T001-T006) | US2 (T007-T012) — fully parallel, no shared files
US3's T014 must follow US1's T002 (same file, job.py)
US3's T016 must follow US2's T011 (same file, app.js)
```

---

## Implementation Strategy

### MVP First (US1 Only — ROI Selection)

1. Complete Phase 2 (T001-T006)
2. **STOP and VALIDATE**: Run quickstart.md Scenario 1 — region drawn, detection
   restricted, regions reset on new file, full-frame behavior unchanged with
   none drawn
3. This alone delivers the highest-value story — directly reduces false
   positives, the most common real-world complaint about full-frame detection

### Incremental Delivery (Recommended Order)

1. Phase 2 (US1) → ROI selection works → Validate Scenario 1
2. Phase 3 (US2) → Stop Application works → Validate Scenario 2
3. Phase 4 (US3) → New Project works → Validate Scenario 3 (note: T014 needs
   US1's T002 already landed in `job.py`; T016 needs US2's T011 already landed
   in `app.js` — this recommended order already satisfies both)
4. Phase 5 → All tests green, all 3 scenarios pass together → Merge to master

Since the file overlaps noted above are narrow (one line each), the stories
could still be parallelized by separate people/subagents if the two
overlapping edits are coordinated by hand afterward — but the sequential order
above avoids that coordination cost entirely and is the recommended path.

---

## Notes

- `[P]` tasks touch different files and have no unresolved dependencies within
  their own story — safe to implement simultaneously. Note the two **cross-
  story** exceptions called out above are not marked `[P]` against each other.
- Constitution Principle III: T001 and T013 are the test-first tasks for the
  only new/changed backend logic in this feature; run each to confirm FAILURE
  before writing T002/T014 respectively.
- No JS test runner exists in this project (no `package.json`) — T006/T012/T017
  use temporary, throwaway scripts that drive a real `QWebEngineView`/
  `MainWindow` instance, per the established pattern from Phases 2-3; delete
  each script after use, do not add to `tests/`.
- `launcher.py`/`shell/main_window.py` (US2) are Qt/process-orchestration code
  outside `app/` — same already-untested category as the rest of `shell/`,
  not subject to Principle III's TDD mandate; verified only via T012's live
  script.
