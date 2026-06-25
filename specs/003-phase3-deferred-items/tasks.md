# Tasks: Phase 3 — Deferred Items Release

**Input**: Design documents from `specs/003-phase3-deferred-items/`
**Branch**: `003-phase3-deferred-items`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/api.md ✅ quickstart.md ✅ checklists/risk-review.md ✅ (all 15 items resolved)

**Constitution Principle III**: Tests are MANDATORY for new backend logic — written
before implementation, confirmed failing before code is written. There is no
frontend test runner in this stack (unchanged Phase 2 precedent); frontend tasks are
verified by directly driving the real app via a temporary script, deleted after use.

**Organization**: 5 phases — Setup → US1 (Custom Export Presets) → US2 (Multi-Level
Undo) → US3 (Light Theme Toggle) → Polish. All three user stories are fully
independent (disjoint files, no shared infrastructure) — there is no Foundational
phase, since nothing here is needed by more than one story.

---

## Phase 1: Setup

**Purpose**: Nothing is shared across the 3 user stories — each is self-contained
in its own files. The only true "setup" is the one config constant US1's backend
needs, which is listed in US1's phase below rather than invented as a separate
no-op phase here.

**No tasks in this phase.**

---

## Phase 2: User Story 1 — Custom Export Presets (Priority: P1) 🎯 MVP

**Goal**: Users can configure export settings, save them as a named preset that
appears as a one-click button alongside the 3 built-ins, have it survive app
restarts, and delete it later. Name collisions (case-insensitive, trimmed) against
both built-in and custom names are rejected.

**Independent Test** (quickstart.md Scenario 1): Configure export settings, save as
preset, close and reopen the app, confirm it's still there and applies correctly.
Reject a built-in-name collision and a duplicate. Delete it.

- [X] T001 [US1] Add `PRESETS_FILE: Path = _APP_DIR / "presets.json"` to
  `app/config.py`, alongside the existing `JOBS_DIR`/`PREVIEW_DIR`/`MODEL_DIR`
  constants
- [X] T002 [P] [US1] Write failing tests in `tests/test_api_presets.py` — using a
  pytest fixture that monkeypatches `app.config.PRESETS_FILE` to a `tmp_path`
  location (so the real `~/.cctv_processor/presets.json` is never touched):
  `test_list_presets_empty_when_file_missing` (GET returns `[]`),
  `test_list_presets_empty_when_file_corrupted` (write invalid JSON content to the
  tmp_path file directly, then GET returns `[]` rather than a 500 — covers the
  spec's "missing, deleted, **or corrupted**" edge case, not just the missing case),
  `test_create_preset_success` (POST then GET shows it),
  `test_create_preset_empty_name_rejected` (whitespace-only name → 400),
  `test_create_preset_builtin_name_rejected` (case-insensitive — try "security report"
  lowercase against "Security Report" → 400),
  `test_create_preset_duplicate_name_rejected` (case-insensitive, trimmed — try
  "Weekly Report " against existing "weekly report" → 400),
  `test_delete_preset_success` (DELETE then GET no longer shows it),
  `test_delete_preset_not_found` (DELETE unknown name → 404); run
  `pytest tests/test_api_presets.py -v` to confirm all fail (module doesn't exist yet)
- [X] T003 [US1] Implement `app/api/presets.py` per `plan.md`'s
  `Implementation Notes for Task Generation` section verbatim (`_load()`/`_save()`
  helpers, `GET /api/presets`, `POST /api/presets`, `DELETE /api/presets/{name}`,
  case-insensitive + trimmed name comparison in `create_preset`); run
  `pytest tests/test_api_presets.py -v` to confirm T002's tests now pass
- [X] T004 [US1] Register the new router in `app/main.py` —
  `from app.api.presets import router as presets_router` and
  `app.include_router(presets_router, prefix="/api")`, in the same style as the
  other five routers already there; run `pytest tests/ -v` to confirm the full
  suite passes with no regressions
- [X] T005 [P] [US1] Add `loadCustomPresets()` to `static/js/pages/export.js`,
  called from the existing `loadSummary().then(...)` chain — `fetch('/api/presets')`,
  render one `<button class="btn preset-btn">` per entry after the 3 built-in
  preset buttons, each wired through the existing `setType()`/`setQuality()`
  helpers plus the existing `burnIn`/`labelFilter` closures (set them from the
  preset's `output_type`/`quality`/`burn_in`/`label_filter` fields)
- [X] T006 [US1] Add a "Save as Preset" control next to the preset row in
  `static/js/pages/export.js` — on click, capture the current
  `selectedType`/`selectedQuality`/`burnIn`/`labelFilter`, prompt for a name,
  `POST /api/presets`; on a 400 response, show the backend's error message; on
  success, call `loadCustomPresets()` again to re-render the row with the new button
  included
- [X] T007 [US1] Add a small delete control to each custom preset button rendered
  by `loadCustomPresets()` in `static/js/pages/export.js` — `DELETE
  /api/presets/{name}`, then re-render the custom preset row; built-in preset
  buttons must not have this control
- [X] T008 [US1] Manual verification per `quickstart.md` Scenario 1 — write a
  temporary script (e.g. `_verify_presets.py`) launching the real
  `shell.main_window.MainWindow` against the real backend, driving it via
  `runJavaScript` to: save a preset, confirm the button appears; restart the app
  process and confirm the preset and its settings survive; attempt a built-in-name
  collision and a duplicate and confirm both are rejected with the right message;
  delete the preset and confirm built-ins are unaffected. Delete the script when done.

**Checkpoint**: Scenario 1 from quickstart.md passes. `pytest tests/ -v` is green.

---

## Phase 3: User Story 2 — Multi-Level Undo History (Priority: P2)

**Goal**: The Timeline page maintains a capped history of bulk include/exclude
operations (not just the last one), undoable one at a time, most recent first.
Clearing the current selection (Escape / empty-area click) does not clear undo
history.

**Independent Test** (quickstart.md Scenario 2): Perform 3 separate bulk-exclude
operations, clear selection via Escape, confirm Undo still works, then Undo three
times and confirm each step reverts exactly one operation in reverse order.

- [X] T009 [US2] In `static/js/session-state.js`, replace the single `lastBulkOp:
  null` field with `undoStack: []` and export `UNDO_STACK_CAP = 20`; update
  `resetUiState()` to reset `_state.undoStack = []` instead of `_state.lastBulkOp =
  null`
- [X] T010 [US2] In `static/js/pages/timeline.js`'s `bulkToggle(include)`, replace
  the `uiState.lastBulkOp = {...}` overwrite with
  `uiState.undoStack.push({ indices, prevIncluded: indices.map(i =>
  events[i].included) }); if (uiState.undoStack.length > UNDO_STACK_CAP)
  uiState.undoStack.shift();` (import `UNDO_STACK_CAP` from `session-state.js`
  alongside the existing `uiState`/`resetUiState` import)
- [X] T011 [US2] In `static/js/pages/timeline.js`'s `undoBulk()`, replace the
  "read `uiState.lastBulkOp` then set it to `null`" logic with
  `if (!uiState.undoStack.length) return; const { indices, prevIncluded } =
  uiState.undoStack.pop();` — keep the existing `trueIdx`/`falseIdx` replay logic
  (the two `PUT /api/job/events/bulk` calls) unchanged below this
- [X] T012 [US2] In `static/js/pages/timeline.js`'s `clearSelection()`, remove the
  line that sets `uiState.lastBulkOp = null` — this function must only clear
  `uiState.selectedIndices` and the related DOM classes/toolbar visibility; undo
  history must be entirely unaffected by clearing a selection
- [X] T013 [US2] In `static/js/pages/timeline.js`'s `updateBulkToolbar()`, change
  `btn-undo.disabled = !uiState.lastBulkOp` to
  `btn-undo.disabled = uiState.undoStack.length === 0`
- [X] T014 [US2] Manual verification per `quickstart.md` Scenario 2 — temporary
  script driving the real app: perform 3 bulk-excludes on different event groups,
  press Escape, confirm Undo is still enabled, then press Undo 3 times and confirm
  after each press that exactly the most recent still-undoable operation's events
  revert (check `events[i].included` via the real `/api/job/events` response at
  each step), ending with Undo disabled. **Also explicitly cover the 3 edge cases
  added to spec.md during checklist resolution, not just the happy path**: (a)
  apply a label/score filter that hides one of the bulk-excluded events, then Undo,
  and confirm via `/api/job/events` that it reverts anyway even though it isn't
  currently visible; (b) build a multi-selection (Ctrl+click some cards), then
  press Undo, and confirm `uiState.selectedIndices` is unchanged by the Undo; (c)
  build undo history, load a new job (`POST /api/job/create` on a different/same
  source), and confirm the Undo button is disabled afterward. Delete the script
  when done.

**Checkpoint**: Scenario 2 from quickstart.md passes. `pytest tests/ -v` remains
green (this story touches no Python files).

---

## Phase 4: User Story 3 — Light Theme Toggle (Priority: P3)

**Goal**: A toggle in the nav bar, visible on every page, switches the whole UI
between dark and light themes instantly with no reload, and the choice survives an
app restart.

**Independent Test** (quickstart.md Scenario 3): Toggle theme on one page, confirm
it applies on every other page, confirm a preview modal also re-themes, restart the
app and confirm the choice persisted.

- [X] T015 [P] [US3] Create `static/js/theme.js` exporting `installTheme()` per
  `plan.md`'s code — reads `localStorage["cctv-theme"]` (default `"dark"`), applies
  it via a `data-theme` attribute on `document.documentElement`, injects a
  `.theme-toggle` button into `#app-nav` that flips the attribute and
  `localStorage` value on click and updates its own icon
- [X] T016 [P] [US3] In `static/css/base.css`, add the
  `:root[data-theme="light"], html[data-theme="light"] { ... }` override block
  with the 10 light-theme custom-property values from `plan.md`, plus a
  `.theme-toggle` style in the same visual register as the existing `.debug-toggle`
  — do NOT add any override for label/badge colors (FR-P3-010: semantic colors stay
  constant across themes)
- [X] T017 [US3] In `static/js/app.js`, import `installTheme` from
  `/static/js/theme.js` and call it next to the existing `installDebugLog()` call
- [X] T018 [US3] Manual verification per `quickstart.md` Scenario 3 — temporary
  script driving the real app: click the theme toggle, confirm
  `document.documentElement.dataset.theme === "light"` and the visible colors
  changed with no network request fired (check via the debug log's fetch capture
  from Task A1 if still useful, or just confirm no page `load` event refired);
  navigate to another page and confirm theme persists; open a preview modal and
  confirm it's themed; fully restart the app process and confirm it opens in light
  theme already. **Also cover the storage-unavailable edge case**: inject
  `Object.defineProperty(window, 'localStorage', { value: { getItem: () => { throw
  new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } } })`
  before calling `installTheme()`, then click the toggle and confirm the theme
  still switches for the current session (no uncaught exception, no crash) even
  though persistence is impossible — `installTheme()`/`applyTheme()` must wrap the
  `localStorage` calls in try/catch for this to pass. Delete the script when done.

**Checkpoint**: Scenario 3 from quickstart.md passes. `pytest tests/ -v` remains
green (this story touches no Python files).

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Final full-suite confirmation, combined manual pass, sign-off.

- [X] T019 Run `pytest tests/ -v` from project root — confirm all existing tests
  plus the new `tests/test_api_presets.py` tests pass; fix any regressions
- [X] T020 Manual smoke test: run through all 3 scenarios in
  `specs/003-phase3-deferred-items/quickstart.md` together in one continuous live
  app session with `python launcher.py` (not just in isolation per-story), to catch
  any cross-feature interaction the independent tests might miss (e.g. saving a
  preset, then performing undo operations, then toggling theme, all in the same
  session)
- [X] T021 Commit completed Phase 3 on branch `003-phase3-deferred-items` with
  message `feat(phase3): custom export presets, multi-level undo, light theme`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Empty — no dependencies, nothing to start
- **Phase 2 (US1)**: No dependencies on other phases; T001 must precede T002–T004
  (tests need the config constant to exist, even though it'll fail for a different
  reason — the router itself — until T003); T005–T007 (frontend) can start in
  parallel with T002–T004 (backend) since they're different files, but T008
  (integration verification) needs both halves done
- **Phase 3 (US2)**: No dependencies on Phase 2 or Phase 4; T009 must precede
  T010–T013 (they all consume `UNDO_STACK_CAP`/the new `undoStack` field T009
  creates)
- **Phase 4 (US3)**: No dependencies on Phase 2 or Phase 3; T015 must precede T017
  (which imports from it); T016 (CSS) is independent of T015/T017 and can run in
  parallel
- **Phase 5 (Polish)**: Depends on all of Phase 2–4 being complete

### User Story Dependencies

- **US1 (P1)**, **US2 (P2)**, **US3 (P3)**: Fully independent of each other — can
  be implemented and shipped in any order, or in parallel by different people,
  since they touch entirely disjoint files (`app/api/presets.py` +
  `app/config.py` + `app/main.py` + `export.js` for US1;
  `session-state.js` + `timeline.js` for US2; `theme.js` + `app.js` + `base.css`
  for US3)

### Parallel Opportunities

```bash
# Within US1 — backend and frontend can proceed in parallel:
Chain A (backend, TDD): T001 → T002 (write tests) → T003 (implement) → T004 (register)
Chain B (frontend): T005, T006, T007 (same file, sequential within the chain)
# T008 needs both chains done.

# Across stories — fully parallel, no shared files:
US1 (T001-T008) | US2 (T009-T014) | US3 (T015-T018)

# Within US3:
Task T015 (theme.js) and Task T016 (base.css) — different files, no dependency
```

---

## Implementation Strategy

### MVP First (US1 Only — Custom Export Presets)

1. Complete Phase 2 (T001–T008)
2. **STOP and VALIDATE**: Run quickstart.md Scenario 1 — save, restart, reuse,
   reject collisions, delete
3. This alone delivers the highest-value deferred item from Phase 2

### Incremental Delivery (Recommended Order)

1. Phase 2 (US1) → Custom presets work → Validate Scenario 1
2. Phase 3 (US2) → Multi-level undo works → Validate Scenario 2
3. Phase 4 (US3) → Light theme works → Validate Scenario 3
4. Phase 5 → All tests green, all 3 scenarios pass together → Merge to master

Since all three stories are independent, they may also be implemented in parallel
(e.g., by separate subagents) rather than strictly in this order — the order above
is priority-driven, not dependency-driven.

---

## Notes

- `[P]` tasks touch different files and have no unresolved dependencies — safe to
  implement simultaneously
- Constitution Principle III: T002 is the test-first task for the only new backend
  surface in this feature; run it to confirm FAILURE before writing T003
- No JS test runner exists in this project (no `package.json`) — T008/T014/T018 use
  temporary, throwaway scripts that drive a real `QWebEngineView`/`MainWindow`
  instance, per the established pattern from the debug-log-panel and edge-case-fixes
  work earlier this branch's history; delete each script after use, do not add to
  `tests/`
- `tests/test_api_presets.py` MUST monkeypatch `app.config.PRESETS_FILE` to a
  `tmp_path` — this is the first persistent file the test suite touches, and a
  naive test would pollute the real developer machine's
  `~/.cctv_processor/presets.json`
