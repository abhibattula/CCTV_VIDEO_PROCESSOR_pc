---
description: "Task list for Phase 8 — Report Fix + Quick Mode UI"
---

# Tasks: Phase 8 — Report Fix + Quick Mode UI

**Input**: Design documents from `specs/008-fix-report-quick-mode/`  
**Branch**: `008-fix-report-quick-mode`  
**Constitution**: Test-First required for all `app/` Python; `static/js/` exempt (use quickstart.md)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in all descriptions

---

## Phase 1: Setup

**Purpose**: Confirm baseline and branch are clean before any fix lands.

- [ ] T001 Run `python -m pytest tests/ -q` from project root and confirm 128 passed, 2 skipped, 0 failed on branch 008-fix-report-quick-mode

---

## Phase 2: Foundational

No shared infrastructure changes needed — this feature modifies existing files only. Proceed directly to user stories.

---

## Phase 3: User Story 1 — AI Report Produces Visible Descriptions (P1) 🎯 MVP

**Goal**: Florence-2 inference completes within 90 s per task, producing non-empty AI captions.

**Independent Test**: After Phase 3 tasks pass, `python -m pytest tests/test_frame_analyzer.py tests/test_intel_report.py -v` passes all new tests.

### Tests for US1 ⚠️ Write FIRST — confirm FAIL before implementing T004 and T005

- [ ] T002 [P] [US1] In `tests/test_frame_analyzer.py`, add: (a) `test_task_timeout_value()` asserting `frame_analyzer._TASK_TIMEOUT == 90`; (b) `test_max_new_tokens_value()` asserting the literal `64` appears as `max_new_tokens` in `_run_analysis()` source (use `inspect.getsource` or constant assertion); (c) `test_analyze_returns_empty_dict_on_timeout()` — mock `_run_in_daemon` to return `(None, TimeoutError("timeout"))` and assert `_run_analysis()` returns a dict with `"caption": ""` without raising (covers FR-002 fallback behavior)
- [ ] T003 [P] [US1] In `tests/test_intel_report.py`, add `test_scene_card_no_broken_img_when_b64_empty()`: render the intel_report.html Jinja2 template with one scene entry where `annotated_thumb_b64=""`, assert the rendered HTML does NOT contain `src="data:image/jpeg;base64,"` (the broken img pattern)

### Implementation for US1

- [ ] T004 [US1] In `app/core/frame_analyzer.py`: change `_TASK_TIMEOUT = 300` to `_TASK_TIMEOUT = 90` (line ~35 module-level constant); change `max_new_tokens=128` to `max_new_tokens=64` at all three `model.generate()` call sites (caption task ~line 146, OD task ~line 158, region caption task ~line 192). Run `python -m pytest tests/test_frame_analyzer.py -v` — confirm T002 tests pass.
- [ ] T005 [P] [US1] In `app/templates/intel_report.html`: find the `<img src="data:image/jpeg;base64,{{ entry.annotated_thumb_b64 }}"` line (near line 577 in the Scene Breakdown section); wrap it in `{% if entry.annotated_thumb_b64 %}<img ...>{% endif %}`. Run `python -m pytest tests/test_intel_report.py -v` — confirm T003 test passes.

**Checkpoint**: `python -m pytest tests/test_frame_analyzer.py tests/test_intel_report.py -v` — all new tests green. Intel report no longer produces broken img tags.

---

## Phase 4: User Story 2 — SSE Progress Stream Is Stable (P2)

**Goal**: Thumbnail progress shows accurate timing; browser disconnect does not crash the server.

**Independent Test**: After Phase 4 tasks pass, `python -m pytest tests/test_stream.py tests/test_api_job.py -v` passes all new tests.

### Tests for US2 ⚠️ Write FIRST — confirm FAIL before implementing T008 and T009

- [ ] T006 [P] [US2] In `tests/test_stream.py`, add `test_sse_generator_handles_client_disconnect()`: mock the SSE generator's `yield` to raise a `ConnectionResetError` on the second call; assert the generator returns cleanly (no unhandled exception raised, no `CancelledError` propagated)
- [ ] T007 [P] [US2] In `tests/test_api_job.py`, add `test_thumbnail_stage_progress_after_run()`: mock `thumbnail_gen.run()` to be a no-op; call the intel-report export logic; assert `session.snapshot()["report_stage_current"]` equals the total event count ONLY after `thumbnail_gen.run()` has been called (use a call-order assertion via `unittest.mock.call_args_list` or side_effect ordering)

### Implementation for US2

- [ ] T008 [US2] In `app/api/stream.py`: locate the SSE event generator function that `yield`s data to the client. Wrap the `yield` statement in `try/except`: catch `asyncio.CancelledError` and re-raise it; catch all other `Exception` types and `return` (ending the generator silently). Add a `logger.debug("SSE client disconnected")` before the `return`. Run `python -m pytest tests/test_stream.py -v` — confirm T006 test passes.
- [ ] T009 [P] [US2] In `app/api/job.py`: find the thumbnail stage block (near lines 470–490). Remove the per-event progress loop that runs before `thumbnail_gen.run()`. After `thumbnail_gen.run(...)` returns, add a single `session.update(report_stage="thumbnails", report_stage_current=len(included), report_stage_total=len(included))` call. Run `python -m pytest tests/test_api_job.py -v` — confirm T007 test passes.

**Checkpoint**: `python -m pytest tests/test_stream.py tests/test_api_job.py -v` — all new tests green. No more premature 100% thumbnail progress or socket.send() tracebacks.

---

## Phase 5: User Story 3 — Quick Report PDF Without AI Wait (P3)

**Goal**: "Quick Report (PDF)" button appears in export page, fires the existing motion-only PDF flow instantly.

**Independent Test**: Manual verification per `specs/008-fix-report-quick-mode/quickstart.md` Scenario 1 and 3.

**Note**: `static/js/` is exempt from automated tests per Constitution III. No T0xx test task. Verification is via quickstart.md.

### Implementation for US3

- [ ] T010 [US3] In `static/js/pages/export.js`: find the `#intel-report-section` render function. Above the existing "Generate Intelligence Report" button block, add a "Quick Report (PDF)" button that:
  1. Has label text `"Quick Report (PDF)"` and a subtitle paragraph `"Instant · rule-based synthesis"`
  2. On click, dispatches `document.dispatchEvent(new CustomEvent('cctv:save-report-pdf'))` — the exact same event the existing "Generate PDF Report" button uses
  3. Is disabled (with a tooltip) when there are zero included events (match the existing Intelligence Report button's guard condition)
  4. The two buttons are laid out side-by-side with a visual separator and their respective subtitle text
  Update the Intelligence Report button's existing subtitle (or add one if absent) to read `"~5–20 min · Florence-2"`
- [ ] T011 [US3] Run manual verification per `specs/008-fix-report-quick-mode/quickstart.md` Scenarios 1, 3, and 4: confirm Quick Report button appears, fires PDF immediately, and no terminal errors occur

**Checkpoint**: Export page shows two report buttons. "Quick Report" fires the motion-only PDF without waiting for AI.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T012 Run `python -m pytest tests/ -q` and confirm ≥ 130 passed (128 baseline + ≥ 4 new tests), 2 skipped, 0 failed
- [ ] T013 Commit all changes: `fix(008): reduce Florence-2 timeout to 90s, max_new_tokens to 64 [P8]` for T004+T005; `fix(008): fix SSE disconnect crash and thumbnail progress race [P8]` for T008+T009; `feat(008): add Quick Report PDF button on export page [P8]` for T010

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Baseline)**: Start immediately
- **Phase 3 (US1)**: After T001. T002+T003 [P] first → T004+T005 [P] after tests fail confirmed
- **Phase 4 (US2)**: After T001. T006+T007 [P] first → T008+T009 [P] after tests fail confirmed
- **Phase 5 (US3)**: Independent of US1/US2 (different file, no shared state)
- **Phase 6 (Polish)**: After all user stories complete

### Within Each Story (Test-First Order)

1. Write tests → run to confirm FAIL
2. Implement fix → run to confirm PASS
3. Move to next story

### Parallel Opportunities

- T002 + T003 can run in parallel (different test files)
- T004 + T005 can run in parallel (different files — frame_analyzer.py and intel_report.html)
- T006 + T007 can run in parallel (different test files)
- T008 + T009 can run in parallel (different files — stream.py and job.py)
- US3 (T010) is entirely independent and can be done alongside any US1/US2 task

---

## Parallel Example: US1

```
# Write tests in parallel:
T002: add timeout/token tests to tests/test_frame_analyzer.py
T003: add broken-img test to tests/test_intel_report.py

# After both tests confirmed failing, implement in parallel:
T004: fix app/core/frame_analyzer.py (timeout + tokens)
T005: fix app/templates/intel_report.html (img guard)
```

---

## Implementation Strategy

### MVP (US1 Only — fixes the empty report)

1. T001: Baseline check
2. T002 + T003: Write tests (parallel)
3. T004 + T005: Implement fixes (parallel)
4. Validate: `pytest tests/test_frame_analyzer.py tests/test_intel_report.py` passes
5. Demo: Generate Intelligence Report → AI captions now non-empty

### Full Delivery

1. MVP (above)
2. T006 + T007: Write SSE/thumbnail tests → T008 + T009: Implement
3. T010 + T011: Add Quick Report button + manual verify
4. T012 + T013: Full suite + commits

---

## Notes

- All `app/` Python tasks follow Test-First (Constitution III). Each implementation task depends on its test task failing first.
- `static/js/` (T010) uses quickstart.md manual scenarios per the frontend exemption.
- T004 modifies three `model.generate()` call sites in `frame_analyzer.py` — verify all three are updated.
- T009 removes a progress loop; ensure the `for n, ev in enumerate(included):` block that preceded `thumbnail_gen.run()` is deleted, not just the session.update call inside it.
- SC-001 math note: The spec states "< 9 min for 5 events" but the correct formula is 90 s × 3 tasks × 5 events = 22.5 min. Real CCTV frames fire EOS early and typically complete in 20–45 s per task, bringing the realistic total under 11 min. The 9-min target in SC-001 should be treated as aspirational for fast CCTV footage; the hard requirement is that each task does not exceed 90 s.
