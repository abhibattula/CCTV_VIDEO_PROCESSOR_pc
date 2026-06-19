# Tasks: Phase 2 — UI Redesign, Tag Filtering & Smart Export

**Input**: Design documents from `specs/002-ui-tag-filter/`
**Branch**: `002-ui-tag-filter`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/api.md ✅ quickstart.md ✅

**Constitution Principle III**: Tests are MANDATORY — written before implementation, confirmed failing before code is written.

**Organization**: 8 phases — Setup → Foundational → US1 → US2 → US3 → US4 → US5 → Polish

---

## Phase 1: Setup (Shared Frontend Infrastructure)

**Purpose**: Create the two shared building blocks every user story depends on. No backend changes. No user-visible features yet.

- [ ] T001 Create `static/js/session-state.js` — export `uiState` object (`labelFilter: new Set()`, `scoreThreshold: 0.0`, `selectedIndices: new Set()`, `lastBulkOp: null`) and `resetUiState()` function that re-initialises all fields to defaults
- [ ] T002 Add CSS custom properties to `static/css/base.css` — `--label-person: #4f8ef7`, `--label-car: #f7a24f`, `--label-dog: #4fd97a`, `--label-cat: #a24ff7`, `--label-bus: #f74f4f`, `--label-bicycle: #4fcff7`, `--label-default: #888888`; also add token classes `.badge--green { color: #4fd97a }`, `.badge--amber { color: #f7c84f }`, `.badge--red { color: #f74f4f }` for confidence badges

**Checkpoint**: `session-state.js` can be imported in browser devtools; label CSS vars visible in computed styles.

---

## Phase 2: Foundational (Backend Bulk Toggle API)

**Purpose**: The `PUT /api/job/events/bulk` endpoint is needed by both US2 (bulk exclude) and US4 (Quick Highlights auto-select). Must be complete before either story can be fully implemented.

**⚠️ CRITICAL**: Write tests FIRST — run `pytest tests/test_session.py -v` to confirm they fail before implementing the function.

- [ ] T003 Write 3 failing tests in `tests/test_session.py` — `test_bulk_toggle_include` (all indices set to included=True), `test_bulk_toggle_exclude` (all indices set to included=False), `test_bulk_toggle_invalid_index` (raises IndexError for out-of-range index)
- [ ] T004 Implement `bulk_toggle_events(indices: list, include: bool) -> None` in `app/session.py` — acquire `_lock`, iterate indices, set `_state["events"][idx]["included"] = include`; run `pytest tests/test_session.py -v` to confirm T003 tests now pass
- [ ] T005 Write 3 failing tests in `tests/test_api_job.py` — `test_bulk_toggle_success` (POST creates events, PUT /api/job/events/bulk sets all to excluded, response has `updated=N`), `test_bulk_toggle_empty_indices` (returns 400), `test_bulk_toggle_invalid_index` (returns 404)
- [ ] T006 Add `BulkToggleRequest(BaseModel)` with fields `indices: list[int]` and `include: bool`; add `PUT /api/job/events/bulk` endpoint in `app/api/job.py` — validate non-empty indices, call `session.bulk_toggle_events()`, return `{"updated": len(indices), "events": snap["events"]}`; run `pytest tests/test_api_job.py -v` to confirm T005 tests pass

**Checkpoint**: `curl -X PUT http://127.0.0.1:5151/api/job/events/bulk -d '{"indices":[0,1],"include":false}'` returns `{"updated":2, "events":[...]}`.

---

## Phase 3: User Story 1 — Tag Filtering (Priority: P1) 🎯 MVP

**Goal**: Timeline shows a label filter bar; clicking chips restricts the event list and canvas strip (non-matching blocks greyed to 20% opacity); a score threshold slider hides weak detections; count display updates to "N shown / M total".

**Independent Test** (quickstart.md Scenario 1): Load YOLO-detected job with Person + Car events. Click "Person" chip — only Person events visible, canvas shows Car blocks dimmed. Drag slider to 0.6 — low-score Person events hide. Toolbar count reflects filtered total.

- [ ] T007 [US1] Add `.filter-bar`, `.label-chip`, `.label-chip.active`, `.score-slider-wrap`, and `.summary-count` CSS rules in `static/css/timeline.css`
- [ ] T008 [US1] Rewrite toolbar HTML in `static/js/pages/timeline.js` — replace current `<span id="tl-summary">` with a two-row toolbar: top row = filter chips container `<div id="filter-bar"></div>` + "Clear Filters" button; second row = score threshold slider `<input type="range" id="score-threshold" min="0" max="1" step="0.05" value="0">` + count display `<span id="ev-count"></span>`
- [ ] T009 [US1] Implement `buildFilterBar(events)` function in `static/js/pages/timeline.js` — collects distinct `zone_label` values from events array; creates one chip per label (plus "Unlabelled" chip if any event has null/empty zone_label); on chip click, toggles label in `uiState.labelFilter` and calls `renderFiltered()`; imports `uiState` from `session-state.js`
- [ ] T010 [US1] Implement `getVisibleEvents()` in `static/js/pages/timeline.js` — returns events where (`uiState.labelFilter.size === 0` OR `zone_label ∈ uiState.labelFilter` OR (`uiState.labelFilter.has("Unlabelled")` AND `!zone_label`)) AND `peak_motion_score >= uiState.scoreThreshold`
- [ ] T011 [US1] Update score threshold slider `input` event handler in `static/js/pages/timeline.js` — on change, set `uiState.scoreThreshold = parseFloat(slider.value)`, call `renderFiltered()`
- [ ] T012 [US1] Update count display in `renderFiltered()` in `static/js/pages/timeline.js` — `document.getElementById("ev-count").textContent = "${visible.length} shown / ${events.length} total"` (uses `getVisibleEvents()` for visible count)
- [ ] T013 [US1] Update `drawCanvas()` in `static/js/pages/timeline.js` — for each event, if its label is NOT in active filter (or score is below threshold), render at `ctx.globalAlpha = 0.2`; matching events at `ctx.globalAlpha = 1.0`; restore alpha to 1.0 after each event block
- [ ] T014 [US1] Add one-click filter shortcut: in the event card's label pill element (`.event-label`), add `click` handler that calls `uiState.labelFilter.add(ev.zone_label)` then `renderFiltered()` in `static/js/pages/timeline.js`
- [ ] T015 [US1] Add label summary chips row to timeline toolbar in `static/js/pages/timeline.js` — after `render()` completes (detection already done), build a compact `<div id="label-summary">` row showing "Person×12 Car×47" by counting zone_labels across all events (not filtered); only shown when YOLO events exist (FR-P2-019)

**Checkpoint**: Scenario 1 from quickstart.md passes.

---

## Phase 4: User Story 2 — Multi-Select & Bulk Operations (Priority: P2)

**Goal**: Each event card has a checkbox; Ctrl+click activates multi-select; bulk action toolbar appears with include/exclude/invert/select-visible/clear; Ctrl+Z undoes the last bulk operation.

**Independent Test** (quickstart.md Scenario 2): Ctrl+click 3 cards — selection ring appears, toolbar shows "3 selected". Click "Exclude Selected" — all 3 go grey. Ctrl+Z — all 3 revert to included.

- [ ] T016 [US2] Add CSS in `static/css/timeline.css` — `.event-card .card-checkbox { display: none }`, `.event-card.selecting .card-checkbox { display: block }`, `.event-card.selected { outline: 2px solid #4f8ef7; outline-offset: -2px }`, `.bulk-toolbar { display: flex; gap: 8px; padding: 8px; background: var(--surface2) }` (hidden by default via `.hidden`)
- [ ] T017 [US2] Add checkbox `<input type="checkbox" class="card-checkbox">` to each event card in `static/js/pages/timeline.js`; add Ctrl+click handler on card body — if `e.ctrlKey`, toggle index in `uiState.selectedIndices`, add/remove `.selected` class, call `updateBulkToolbar()`, add `.selecting` to `#events-list` if selection is non-empty
- [ ] T018 [US2] Implement `updateBulkToolbar()` in `static/js/pages/timeline.js` — shows bulk toolbar when `uiState.selectedIndices.size > 0`; toolbar buttons: "Include Selected", "Exclude Selected", "Invert Selection" (toggle each selected event), "Select Visible" (select all `getVisibleEvents()` indices), "Clear Selection"
- [ ] T019 [US2] Implement `bulkToggle(include)` in `static/js/pages/timeline.js` — saves `lastBulkOp = { indices: [...uiState.selectedIndices], prevIncluded: indices.map(i => events[i].included) }` to `uiState`; calls `PUT /api/job/events/bulk` with `{ indices, include }`; on response, updates local events array and calls `renderFiltered()`; activates undo button
- [ ] T020 [US2] Implement undo in `static/js/pages/timeline.js` — on `Ctrl+Z` keydown (and "Undo" button click): if `uiState.lastBulkOp` is not null, reconstruct two arrays: `includeTrue = indices where prevIncluded[i]===true`, `includeFalse = indices where prevIncluded[i]===false`; call bulk API twice (once per group); set `uiState.lastBulkOp = null`; deactivate undo button
- [ ] T021 [US2] Implement selection clear in `static/js/pages/timeline.js` — on `Escape` keydown (when events-list has focus) and on click on the events-list container where `e.target === eventsListEl`: clear `uiState.selectedIndices`, remove `.selected` and `.selecting` classes, hide bulk toolbar (FR-P2-009)

**Checkpoint**: Scenario 2 from quickstart.md passes. `uiState.selectedIndices` is empty after Escape.

---

## Phase 5: User Story 3 — UI Redesign, Confidence Badges & Keyboard Shortcuts (Priority: P3)

**Goal**: Each event card shows a colour-coded confidence badge and a coloured label pill. Arrow keys navigate cards; Space toggles; Ctrl+A/D select/deselect; Ctrl+E goes to export. CSS containment enables performant rendering for 300+ events. Home page settings become two-column.

**Independent Test** (quickstart.md Scenario 3): Click event list once. Press Arrow Down twice — focus ring on card #3. Press Space — card #3 excluded. Press Enter — preview modal opens. Ctrl+E — navigates to export.

- [ ] T022 [US3] Add confidence badge to each event card in `static/js/pages/timeline.js` — after score display, add `<span class="confidence-badge ${badgeClass}">${score.toFixed(2)}</span>` where `badgeClass` = `badge--green` if score ≥ 0.7, `badge--amber` if ≥ 0.4, else `badge--red`
- [ ] T023 [US3] Add label pill to each event card in `static/js/pages/timeline.js` — if `ev.zone_label`, add `<span class="event-label" style="background: var(--label-${ev.zone_label.toLowerCase()}, var(--label-default))">${ev.zone_label}</span>` (uses CSS custom properties from T002)
- [ ] T024 [US3] Add keyboard navigation in `static/js/pages/timeline.js` — maintain `let focusedIdx = null`; on `keydown` on `#events-list` container: `ArrowDown`/`ArrowUp` → update focusedIdx (clamp to visibleEvents length), add `.focused` to focused card, remove from others, call `.scrollIntoView({ block: "nearest" })`; `Space` → call `PUT /api/job/events/{focusedIdx}/toggle` then re-render; `Enter` → call `showPreview(focusedIdx)`
- [ ] T025 [US3] Add global keyboard shortcuts in `static/js/pages/timeline.js` — add `keydown` listener on `window` (suppressed when `e.target.tagName` is INPUT/TEXTAREA/SELECT): `Ctrl+A` → select all visible indices into `uiState.selectedIndices`, call `updateBulkToolbar()`; `Ctrl+D` → clear `uiState.selectedIndices`, hide bulk toolbar; `Ctrl+E` → `window.go('/export')`; `Escape` → clear selection (reuse T021 logic)
- [ ] T026 [US3] [P] Add CSS `content-visibility: auto; contain-intrinsic-size: 0 90px;` to `.event-card` rule in `static/css/timeline.css` (FR-P2-020 virtual scroll via CSS containment); add `.event-card.focused { outline: 2px solid var(--accent); outline-offset: -2px }` and `.confidence-badge`, `.event-label` pill styles
- [ ] T027 [US3] [P] Redesign home page settings panel to two-column grid in `static/pages/home.html` — wrap existing settings sections in `<div class="settings-grid">` containing two `<div class="settings-col">` divs (Detection + Sensitivity in left col; Advanced + Timestamp in right col); add `.settings-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px }` with `@media (max-width: 900px) { .settings-grid { grid-template-columns: 1fr } }` in `static/css/home.css`

**Checkpoint**: Scenario 3 from quickstart.md passes. On a 300-event timeline, scrolling feels smooth (no janky repaints).

---

## Phase 6: User Story 4 — Smart Export Presets & Burn-In (Priority: P4)

**Goal**: Three preset buttons on the export page auto-configure all settings. Optional burn-in overlay renders timestamp + label via FFmpeg drawtext on each exported clip. Tests written before backend implementation.

**Independent Test** (quickstart.md Scenario 4): Click "Evidence Pack" — output type becomes Individual Clips, quality Original. Click "Security Report" — output type Merged, burn-in ON. Export a real clip with burn-in; open in media player; confirm `"HH:MM:SS • Person"` visible in bottom-left.

- [ ] T028 [US4] Write 4 failing tests in `tests/test_export_engine.py` — `test_burn_in_drawtext_in_individual_cmd` (when burn_in=True, ffmpeg cmd contains `drawtext`), `test_burn_in_label_in_text` (drawtext text contains zone_label), `test_no_burn_in_when_disabled` (cmd does NOT contain `drawtext` when burn_in=False), `test_label_filter_excludes_non_matching_events` (events with zone_label not in label_filter are skipped)
- [ ] T029 [US4] Add `_build_burnin_filter(start_s: float, zone_label: str | None, recording_start: str | None) -> str` helper in `app/core/export_engine.py` — computes timestamp string (uses `seconds_to_clock(start_s, recording_start)` if recording_start set, else `f"{int(start_s)//3600:02d}:{(int(start_s)%3600)//60:02d}:{int(start_s)%60:02d}"`); builds drawtext filter string: `drawtext=text='<timestamp>[ • <label>]':fontsize=18:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=4:x=10:y=(h-th-10)`; run T028 tests to confirm they pass
- [ ] T030 [US4] Extend export `run()` in `app/core/export_engine.py` to accept `burn_in: bool = False` and `label_filter: list = []` parameters — at the top of `run()`, if `label_filter`, filter `included` list to `[ev for ev in included if ev.get("zone_label","") in label_filter]`; raise ValueError if result is empty; for each clip command (both individual and segment modes), when `burn_in=True`, append `-vf` with the drawtext filter string (chained with any existing scale filter using `,`); run `pytest tests/test_export_engine.py -v` to confirm all T028 tests pass
- [ ] T031 [US4] Extend `ExportRequest` in `app/api/job.py` — add `burn_in: bool = False` and `label_filter: list[str] = []`; thread both values through to `export_run()` call in `export_job()`
- [ ] T032 [US4] [P] Add three preset buttons to export page HTML in `static/js/pages/export.js` — above the Output Type card, insert `<div class="preset-row"><button class="preset-btn" data-preset="security">Security Report</button><button class="preset-btn" data-preset="evidence">Evidence Pack</button><button class="preset-btn" data-preset="highlights">Quick Highlights</button></div>`
- [ ] T033 [US4] Implement preset click handlers in `static/js/pages/export.js` — `security`: set `selectedType="merged"`, `selectedQuality="original"`, `burnIn=true`, `labelFilter=["Person"]`; `evidence`: set `selectedType="individual"`, `selectedQuality="original"`, `burnIn=false`, `labelFilter=[]`; `highlights`: set `selectedType="merged"`, `selectedQuality="720p"`, `burnIn=false`, `labelFilter=[]`, then call `applyQuickHighlights()`; each preset updates the UI toggle buttons to show active state
- [ ] T034 [US4] Implement `applyQuickHighlights()` in `static/js/pages/export.js` — fetch `/api/job/events`, sort by `peak_motion_score` descending, take first 10 (or all if fewer), get their indices; call `PUT /api/job/events/bulk` with `{indices: top10, include: true}` then `PUT /api/job/events/bulk` with `{indices: rest, include: false}`
- [ ] T035 [US4] Add burn-in toggle and label scope selector to export page in `static/js/pages/export.js` — add `<label class="burn-in-toggle"><input type="checkbox" id="burn-in-check"> Burn-in timestamp & label</label>`; add `<select id="label-scope"><option value="">All labels</option></select>` (populated from distinct zone_labels on load); wire both to `selectedBurnIn` and `selectedLabelFilter` variables passed in export API call; add preset CSS in `static/css/export.css`

**Checkpoint**: Scenario 4 from quickstart.md passes. Exported clip viewed in media player shows `"08:35:12 • Person"` bottom-left text overlay.

---

## Phase 7: User Story 5 — Live Detection Dashboard (Priority: P5)

**Goal**: During YOLO detection, the processing page shows a CSS bar chart of label counts that updates in real time from the SSE stream, plus an events-per-minute counter. After detection, the timeline toolbar shows a compact label summary.

**Independent Test** (quickstart.md Scenario 5): Start YOLO detection; switch to Processing page; confirm bars appear and grow as events are detected; confirm events/min counter increments; after detection completes, navigate to timeline and see "Person×12 Car×47" in toolbar.

- [ ] T036 [US5] Add chart HTML to processing page in `static/js/pages/processing.js` — below the progress bar, insert `<div class="chart-wrap"><h4>Detection Activity</h4><div id="label-chart"></div><p class="eventsmin-counter">Events/min: <span id="evmin">—</span></p></div>`
- [ ] T037 [US5] Add CSS in `static/css/processing.css` — `.chart-wrap { margin-top: 16px }`, `.chart-bar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px }`, `.chart-label { width: 80px; font-size: 12px; text-align: right }`, `.chart-bar { height: 14px; background: var(--accent); border-radius: 2px; transition: width 0.3s ease; min-width: 2px }`, `.eventsmin-counter { font-size: 13px; color: var(--muted); margin-top: 8px }`
- [ ] T038 [US5] Wire chart to SSE stream in `static/js/pages/processing.js` — in the existing SSE event listener, add handler for `type === "event"` messages: extract `event.zone_label` (or `"Motion"` for null), increment `labelCounts[label]`, compute `maxCount = Math.max(...Object.values(labelCounts))`, re-render `#label-chart` with one `.chart-bar-row` per label where `.chart-bar` width = `${(count/maxCount)*200}px`; initialise `startTime = Date.now()` when first event arrives
- [ ] T039 [US5] Add events/min counter in `static/js/pages/processing.js` — set `setInterval(() => { const elapsed = (Date.now() - startTime) / 60000; document.getElementById("evmin").textContent = elapsed > 0 ? (totalEvents / elapsed).toFixed(1) : "—"; }, 10000)` — cancel the interval on page unmount (in `container._cleanup`)

**Checkpoint**: Scenario 5 from quickstart.md passes.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Wire the filter state reset, run all tests, smoke-test all quickstart scenarios.

- [ ] T040 Call `resetUiState()` from `static/js/pages/home.js` after successful `POST /api/job/create` response — `import { resetUiState } from '/static/js/session-state.js'; /* after job create succeeds */ resetUiState();`
- [ ] T041 Run `pytest tests/ -v` from project root — confirm all existing 49 tests still pass AND new tests T003+T005+T028 all pass; fix any regressions
- [ ] T042 Manual smoke test: run through all 7 scenarios in `specs/002-ui-tag-filter/quickstart.md` with `python launcher.py`; fix any issues found
- [ ] T043 Commit completed Phase 2 on branch `002-ui-tag-filter` with message `feat(phase2): tag filtering, multi-select, presets, burn-in, live dashboard`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately; T001 and T002 are [P] parallelizable
- **Phase 2 (Foundational)**: Depends on Phase 1 completion; T003→T004 sequential (TDD), T005→T006 sequential (TDD)
- **Phase 3 (US1)**: Depends on Phase 1 (needs `session-state.js`); does NOT need Phase 2 backend
- **Phase 4 (US2)**: Depends on Phase 1 + Phase 2 (needs bulk toggle API)
- **Phase 5 (US3)**: Depends on Phase 3 (builds on timeline.js); T026 and T027 are [P] independent
- **Phase 6 (US4)**: Depends on Phase 2 (needs bulk API for Quick Highlights); T028→T029→T030 sequential (TDD)
- **Phase 7 (US5)**: Independent of US1–US4 (only modifies processing.js); can start after Phase 1
- **Phase 8 (Polish)**: Depends on all phases complete

### User Story Dependencies

- **US1 (P1)**: After Phase 1; no dependency on US2-US5
- **US2 (P2)**: After Phase 1 + Phase 2 (bulk API); no dependency on US1 (can work in parallel with US1)
- **US3 (P3)**: After Phase 3 (US1) — extends the timeline.js file, best to build on US1's rewrite
- **US4 (P4)**: After Phase 2 (bulk API for Quick Highlights); independent of US1/US2/US3
- **US5 (P5)**: After Phase 1 only; fully independent

### Parallel Opportunities

```bash
# Phase 1 — run together:
Task T001 (session-state.js)
Task T002 (base.css colour tokens)

# Phase 2 — two TDD chains, run sequentially within each chain:
Chain A: T003 (write test) → T004 (implement bulk_toggle in session.py)
Chain B: T005 (write test) → T006 (implement bulk API endpoint)

# Phase 5 — US3 has two independent tasks:
Task T026 (CSS containment + badge styles in timeline.css)
Task T027 (home page two-column in home.html + home.css)

# Phase 7 — US5 is fully independent of Phase 3-6 once Phase 1 done:
Can work on US5 (T036-T039) in parallel with US1 (T007-T015)
```

---

## Implementation Strategy

### MVP First (US1 Only — Label Filtering)

1. Complete Phase 1 (T001, T002)
2. Complete Phase 3 (T007–T015)
3. **STOP and VALIDATE**: Run quickstart.md Scenario 1 — filter bar works, canvas greys out, score slider filters, count updates
4. This alone reduces review time from "scroll 312 cards" to "scroll 17 cards"

### Incremental Delivery (Recommended Order)

1. Phase 1 + Phase 2 → Foundation ready (T001–T006)
2. Phase 3 (US1) → Label filtering works → Validate Scenario 1
3. Phase 4 (US2) → Bulk ops work → Validate Scenario 2
4. Phase 5 (US3) → Keyboard nav + badges → Validate Scenario 3
5. Phase 6 (US4) → Presets + burn-in → Validate Scenario 4
6. Phase 7 (US5) → Live chart → Validate Scenario 5
7. Phase 8 → All tests green, all 7 scenarios pass → Merge to master

---

## Notes

- `[P]` tasks touch different files and have no unresolved dependencies — safe to implement simultaneously
- Constitution Principle III: T003, T005, T028 are the test-first tasks; run them to confirm failure BEFORE writing implementation in T004, T006, T030
- `session-state.js` is an ES module singleton — test its import in browser console: `import('/static/js/session-state.js').then(m => console.log(m.uiState))`
- The `drawtext` burn-in test (T028) uses `_make_fake_ffmpeg()` from existing `tests/conftest.py` or `test_export_engine.py` to stub FFmpeg — confirm the cmd list contains `"drawtext"` without actually running FFmpeg
- Keyboard shortcuts (T024, T025) must be suppressed when `e.target.tagName` is `"INPUT"`, `"TEXTAREA"`, or `"SELECT"` to avoid interfering with the score slider and other inputs
- After T040 (resetUiState), test Scenario 7 from quickstart.md to confirm new job load clears filters
