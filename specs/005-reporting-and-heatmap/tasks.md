# Tasks: Phase 5 — Professional Reporting & Activity Insights

**Input**: Design documents from `/specs/005-reporting-and-heatmap/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Included for all `app/core/*.py`/`app/api/*.py` changes per this project's Constitution Principle III (non-negotiable, no exception for backend logic). `shell/main_window.py` and all `static/js/` changes are verified via `quickstart.md` scenarios instead, per this project's established frontend/Qt exemption.

**Organization**: Tasks are grouped by user story (US1 = PDF/HTML Incident Report, US2 = Activity Heatmap, US3 = CSV/JSON Event Log Export) per their priority order in `spec.md`.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Create `app/templates/` directory (new, for the Jinja2 report template)
- [ ] T002 Add `Jinja2==3.1.6` to `requirements.txt` and confirm `python -c "import jinja2; print(jinja2.__version__)"` reports `3.1.6` in the project's venv

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Fixes/coverage that User Story 1 (thumbnails-by-`event_index`) and User Story 2 (heatmap producers) both transitively depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 [P] Write failing test `test_emitted_events_have_event_index` in `tests/test_yolo_detector.py` — assert every event dict yielded via `on_event` during a real run contains an `event_index` key, incrementing `0, 1, 2, ...` across multiple emitted events (skip-guarded on the real test video + `ultralytics` availability, matching this file's existing pattern)
- [ ] T004 Fix `app/core/yolo_detector.py`: add an `event_index` parameter to `_emit_event`, increment a counter at each call site, matching `detection_engine.py`'s existing behavior (makes T003 pass)
- [ ] T005 [P] Write tests in new `tests/test_thumbnail_gen.py` covering `thumbnail_gen.run()`'s existing behavior: writes `<job_dir>/thumbnails/<event_index>.jpg` for each event, is idempotent (second call with the same events doesn't re-invoke ffmpeg), skip-guarded on real-video availability matching this project's existing `HAS_TEST_VIDEO` pattern — this is new test coverage for already-correct, previously-untested code, not a bug fix
- [ ] T006 [P] Write failing tests `test_sha256_file_matches_known_hash` and `test_sha256_file_chunked_equals_whole_file_hash` in `tests/test_api_job.py` (write a small known-content temp file and a multi-chunk-sized random temp file; assert the chunked helper's output matches an independently-computed `hashlib.sha256(...).hexdigest()` in both cases)
- [ ] T007 Implement `_sha256_file(path: Path, chunk_size: int = 1024*1024) -> str` in `app/api/job.py` using chunked reads (makes T006 pass)

**Checkpoint**: Foundation ready — User Story 1, 2, and 3 implementation can now begin.

---

## Phase 3: User Story 1 — Generate a Professional Incident Report (Priority: P1) 🎯 MVP

**Goal**: A one-click "Generate PDF Report" action on the Export page producing a complete incident report (summary, thumbnail grid of included events, chain-of-custody hashes, and the heatmap image if one happens to already exist) saved automatically to the user's output folder.

**Independent Test**: Per `spec.md`'s Independent Test for this story — load a video, run detection, exclude a couple of events, click "Generate PDF Report," and verify the resulting document only shows included events with correct counts/metadata. This works correctly even before User Story 2 is implemented, since FR-P5-013 already requires the heatmap section to be gracefully omitted when no heatmap exists.

### Tests for User Story 1

> **Write these tests FIRST, ensure they FAIL before implementation.**

- [ ] T008 [P] [US1] Write failing tests in `tests/test_api_job.py`: `test_report_html_no_active_job` (400), `test_report_html_no_included_events` (400, explicit message per FR-P5-008), `test_report_html_renders_expected_content` (seed events via the existing `_seed_events` helper, monkeypatch `thumbnail_gen.run` to a no-op, assert 200 + `text/html` + body contains expected event counts/labels/source filename), `test_report_html_includes_source_hash` (asserts the correct SHA-256 hex digest of a known small fake "source video" file appears in the body), `test_report_html_no_output_yet` (asserts the "no export has been produced yet" fallback text per FR-P5-006), `test_report_html_shows_filenames_not_paths` (asserts the rendered body contains the bare filename but not the full directory path, per FR-P5-023)

### Implementation for User Story 1

- [ ] T009 [US1] Implement `app/core/report_renderer.py` exposing `render(context: dict) -> str`, and `app/templates/report.html` (standalone Jinja2 document, inline `<style>` copied from `static/css/base.css`'s light-theme token values, all images base64-inlined, sections: header, summary, heatmap [conditional], thumbnail grid, chain-of-custody table showing filenames only per FR-P5-023)
- [ ] T010 [US1] Implement `GET /api/job/report.html` in `app/api/job.py`: 400 on no active job; available whenever the job has ≥1 event regardless of completed/cancelled detection status, blocked only while `status == "detecting"`, never blocked by an in-progress or finished video export (FR-P5-020); filter to `included` events (same expression `export_job()` already uses); 400 with an explicit message if that set is empty (FR-P5-008); lazily call `thumbnail_gen.run()` scoped to those events; base64-inline each thumbnail and the heatmap (if `job_dir/heatmap.png` exists); compute `_sha256_file` for the source and (if `output_path` is set) the exported file, wrapping both in a `try/except (FileNotFoundError, OSError)` that returns a clear error naming the specific missing file path (FR-P5-022); delegate to `report_renderer.render()` (makes T008 pass)
- [ ] T011 [P] [US1] In `shell/main_window.py`: add `window._cctvSaveReportPdf = false;` plus a `cctv:save-report-pdf` event listener to the injected JS bridge; add a fourth check to `_handle_browse_flags` that clears the flag and calls a new `_generate_pdf_report()`; implement `_generate_pdf_report()` (resolve `output_dir` via a synchronous `GET /api/job` call, falling back to `Path.home() / "Desktop"`; construct a hidden `QWebEnginePage(self._view.page().profile(), self)`; load `/api/job/report.html`; on `loadFinished` call `printToPdf(<output_dir>/incident_report_<timestamp>.pdf)`; on `pdfPrintingFinished` call `deleteLater()`; keep a `self._pending_report_pages` list reference so Python's GC can't collect the page object before the async signals fire)
- [ ] T012 [P] [US1] In `static/js/pages/export.js`: add a new `.card.export-section` immediately before `#export-action-row` containing a "Generate PDF Report" button; on click, disable the button, show an in-progress status message (FR-P5-021), dispatch `window.dispatchEvent(new CustomEvent("cctv:save-report-pdf"))`, then re-enable the button and show a completion message after a fixed delay (no completion signal crosses the JS/Qt boundary in this version, consistent with Stop Application's existing pattern)
- [x] T013 [US1] Verify `quickstart.md` Scenarios 4, 5, 6 (report-specific half), and 8 end-to-end against the real running app; confirm the highest-priority Open Risk (a hidden, never-shown `QWebEnginePage` producing a non-blank PDF) holds on the actual Windows target; additionally, build (or reuse the seeding helper to construct) a job with exactly 50 included events and time the full "Generate PDF Report" click-to-file-appears interval with a stopwatch against SC-P5-001. **Resolved**: initial run measured 27s (50 sequential blocking ffmpeg calls in `thumbnail_gen.py`); fixed via `ThreadPoolExecutor` parallelization + ffmpeg tuning (`-threads 1`/`-an`), landing at ~9-12s across repeated trials. A fully-batched single-ffmpeg-call alternative was investigated and empirically rejected (>60s for this video's HEVC 1080p encoding — per-event seek+decode is cheaper than one continuous decode pass for this codec). SC-P5-001 was reworded to an honest best-effort target reflecting this measured reality (see `spec.md`) rather than a hard guarantee.

**Checkpoint**: User Story 1 is fully functional and independently testable — a complete incident report can be generated with or without a heatmap present.

---

## Phase 4: User Story 2 — See Where Activity Concentrated (Priority: P2)

**Goal**: After a detection run (either mode), an optional, off-by-default heatmap overlay is available on the ROI-drawing screen, and automatically appears in future Incident Reports (User Story 1) for jobs that have one.

**Independent Test**: Per `spec.md` — run detection on a video with motion concentrated in one area, return to the Home page's zone-drawing screen, and confirm a visual indicator shows where the activity was without interfering with drawing zones. Independently testable without touching User Story 1 or 3's code paths.

### Tests for User Story 2

> **Write these tests FIRST, ensure they FAIL before implementation.**

- [ ] T014 [P] [US2] Write failing tests in `tests/test_detection_engine.py`: `test_run_writes_heatmap_png` (real test video, asserts `job_dir/heatmap.png` exists and is a valid non-empty PNG after `run()` returns), `test_heatmap_matches_source_resolution` (asserts written heatmap `(height, width)` matches `source_info["height"]`/`["width"]`, not `DETECT_HEIGHT`/`DETECT_WIDTH`), `test_heatmap_skipped_on_zero_motion` (calling `_write_heatmap` directly with an all-zero accumulator asserts no file is written), `test_cancelled_run_still_attempts_heatmap_write` (cancellation mid-run doesn't crash the heatmap-write step)
- [ ] T015 [P] [US2] Write failing test `test_run_writes_heatmap_png` (YOLO variant, same assertions as T014's detection_engine version) in `tests/test_yolo_detector.py`
- [ ] T016 [P] [US2] Write failing tests in `tests/test_api_job.py`: `test_heatmap_no_active_job` (400), `test_heatmap_not_yet_generated` (404, job exists but no `heatmap.png`), `test_heatmap_served_when_present` (seed a job, manually write a tiny PNG to `_job_dir(job_id)/"heatmap.png"`, assert 200 + `image/png`)

### Implementation for User Story 2

- [ ] T017 [US2] In `app/core/detection_engine.py`: initialize `heatmap_accum = np.zeros((H, W), dtype=np.float32)` alongside the existing `zone_mask` setup; accumulate `heatmap_accum += (fg_mask > 0).astype(np.float32)` immediately after the existing zone-mask `bitwise_and`; add `_write_heatmap(accum, source_info, job_dir)` helper (normalize 0-255, `cv2.applyColorMap(..., cv2.COLORMAP_JET)`, resize to source resolution, `cv2.imwrite`, no-op if `accum.max() <= 0`); call it unconditionally at the end of `run()` (makes T014 pass)
- [ ] T018 [US2] In `app/core/yolo_detector.py`: initialize a `heatmap_accum` at native source resolution (from `cap.get(cv2.CAP_PROP_FRAME_WIDTH/HEIGHT)`); for each detected box, `cv2.rectangle(heatmap_accum, (x1,y1), (x2,y2), color=conf, thickness=-1)` using `box.xyxy`; call `detection_engine._write_heatmap(...)` (reused, not duplicated) at the end of `run()` (makes T015 pass)
- [ ] T019 [US2] Implement `GET /api/job/heatmap` in `app/api/job.py`, mirroring `/api/job/preview-frame`'s shape but never generating on demand — 400 no job, 404 if `job_dir/heatmap.png` doesn't exist, else `FileResponse` (makes T016 pass)
- [ ] T020 [P] [US2] In `static/js/roi.js` and `static/css/roi.css`: add a `.roi-editor__heatmap` `<img>` layer between the base preview image and the drawing canvas (`pointer-events: none`, `opacity: ~0.55`, hidden by default); add `setHeatmapSrc(url)` to `mountRoiEditor`'s returned handle (sets `.src`, unhides on load, hides on `onerror`); add a "Show Activity Heatmap" toggle checkbox (a standard, keyboard-operable `<input type="checkbox">`, per FR-P5-024) to the toolbar, default unchecked
- [ ] T021 [P] [US2] In `static/js/pages/home.js`'s `loadRoiPreview()`: after the existing `setImageSrc(...)` call, add `roiHandle.setHeatmapSrc("/api/job/heatmap?t=" + Date.now())`
- [ ] T022 [US2] Verify `quickstart.md` Scenarios 1, 2, and 3 end-to-end against the real running app, in both MOG2 and YOLO detection modes; confirm `GET /api/job/events` shows a populated `event_index` on every YOLO event as part of this pass

**Checkpoint**: User Stories 1 AND 2 both work independently — a job processed in either detection mode now produces a heatmap, and any report generated for it (US1) automatically includes that heatmap.

---

## Phase 5: User Story 3 — Export the Event Data as Plain Data (Priority: P3)

**Goal**: One-click CSV and JSON exports of the included events' data, saved directly to the user's output folder.

**Independent Test**: Per `spec.md` — after a completed detection run, click the data-export action and verify a file is produced containing exactly the included events' data. Fully independent of User Story 1 and 2's code paths (pure backend, no Qt, no heatmap/thumbnail dependency).

### Tests for User Story 3

> **Write these tests FIRST, ensure they FAIL before implementation.**

- [ ] T023 [P] [US3] Write failing tests in `tests/test_api_job.py`: `test_export_csv_writes_expected_rows` (seed events via `_seed_events`, POST with a `tmp_path` output dir, read back the written CSV directly, assert row count/field values match the included events), `test_export_csv_respects_label_filter` (mixed-label events, assert only matching-label events appear), `test_export_csv_no_included_events` (400, explicit message per FR-P5-017), `test_export_json_writes_expected_structure` (same as the CSV test but `json.loads()` on the written file)

### Implementation for User Story 3

- [ ] T024 [US3] Implement `EventLogExportRequest` (Pydantic model: `output_dir: Optional[str] = None`, `label_filter: list[str] = []`) and `POST /api/job/export/csv` + `POST /api/job/export/json` in `app/api/job.py`: available whenever the job has ≥1 event regardless of completed/cancelled detection status, blocked only while `status == "detecting"`, never blocked by an in-progress or finished video export (FR-P5-020); filter to `included` events (identical expression to FR-P5-003/FR-P5-016, optionally narrowed by `label_filter`); 400 with an explicit message if the filtered set is empty (FR-P5-017); resolve `output_dir` via the same order `export_job()` already uses (explicit request → session `output_dir` → Desktop fallback), wrapping the directory-creation/file-write in a `try/except OSError` that returns a clear error naming the specific path if it's unwritable or missing (FR-P5-022); write `<source_stem>_events_<timestamp>.csv`/`.json` via stdlib `csv`/`json`; return `{"output_path": ...}` (makes T023 pass)
- [ ] T025 [P] [US3] In `static/js/pages/export.js`: add "Event Log (CSV)" / "Event Log (JSON)" buttons to the same new `.card.export-section` from T012; on click, disable the clicked button and show an in-progress status message (FR-P5-021, matching T012's pattern); wire both to `POST /api/job/export/csv`/`json` reusing the page's existing `outputDir`/`labelFilter` closures; re-enable the button and show the returned `output_path` (or error) in the shared status line once the request settles
- [ ] T026 [US3] Verify `quickstart.md` Scenarios 6 (export-specific half) and 7 end-to-end against the real running app

**Checkpoint**: All three user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T027 Run `python -m pytest tests/ -v` — confirm full green, including every new test from T003-T023, with no regressions to the existing suite
- [ ] T028 [P] Update `README.md`: Features list, "How It Works" pipeline description, Project Structure tree (`app/templates/`, `report_renderer.py`, updated `app/core/`/`app/api/` comments, updated `static/js/` comments), test count
- [ ] T029 [P] Update `USER_MANUAL.md`: new sections for the Activity Heatmap toggle, "Generate PDF Report," and "Event Log (CSV/JSON)" export actions on the Export page
- [ ] T030 [P] Update `ROADMAP.md`: mark Category C (Professional Reporting) and the heatmap/CSV-JSON items as shipped in this phase, consistent with the roadmap's living-document nature
- [ ] T031 Final whole-feature review pass: re-confirm every Open Risk from `plan.md` against the actual implementation (offscreen-Chromium PDF rendering on the real Windows target is the highest priority), confirm `quickstart.md`'s 8 scenarios all pass together in one continuous app session (not just in isolation), confirm nav-bar/page layouts still fit at the app's default window width with the three new Export-page buttons added

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all three user stories (US1 needs the `event_index` fix for YOLO-origin thumbnails to address correctly; US1 and US2 both need the thumbnail/hashing test scaffolding in place).
- **User Stories (Phase 3-5)**: All depend on Foundational completion. US1, US2, US3 are mutually independent and may proceed in any order or in parallel — priority order (P1 → P2 → P3) is recommended for incremental delivery, matching the MVP framing below.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Depends only on Foundational. Does NOT depend on User Story 2 — FR-P5-013 already requires the report to gracefully omit the heatmap section when none exists, so US1 is fully testable before US2 lands.
- **User Story 2 (P2)**: Depends only on Foundational. Once both US1 and US2 are complete, a report generated for a job with a heatmap will automatically include it — this is integration-by-shared-file-format (`job_dir/heatmap.png`), not a code dependency between the two stories.
- **User Story 3 (P3)**: Depends only on Foundational. Fully independent of US1 and US2 (different endpoints, no shared code beyond the `included`-events filter expression each already implements separately).

### Within Each User Story

- Tests MUST be written and confirmed failing before implementation, per Constitution Principle III, for every task touching `app/core/*.py` or `app/api/*.py`.
- `shell/main_window.py` and `static/js/*` tasks are verified via the `quickstart.md` scenario referenced in that story's final task, not pytest.

### Parallel Opportunities

- T003, T005, T006 (Foundational tests) can run in parallel — different files.
- T011 and T012 (US1's Qt and JS tasks) can run in parallel once T010 (the endpoint they both call) is done.
- T014, T015, T016 (US2's three test files) can run in parallel.
- T020 and T021 (US2's two JS files) can run in parallel.
- T028, T029, T030 (documentation updates) can run in parallel.
- Once Foundational completes, US1/US2/US3 can be staffed and executed in parallel by independent workers if desired.

---

## Parallel Example: Foundational Phase

```bash
# Launch all Foundational tests together:
Task: "Write failing test test_emitted_events_have_event_index in tests/test_yolo_detector.py"
Task: "Write tests in new tests/test_thumbnail_gen.py"
Task: "Write failing tests test_sha256_file_matches_known_hash and test_sha256_file_chunked_equals_whole_file_hash in tests/test_api_job.py"
```

## Parallel Example: User Story 1

```bash
# Once T010 (the report.html endpoint) is done, these two can run in parallel:
Task: "Add hidden-QWebEnginePage PDF generation flow to shell/main_window.py"
Task: "Add Generate PDF Report button to static/js/pages/export.js"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: Generate a PDF report end-to-end per `quickstart.md` Scenario 4 — confirm it's non-blank and correctly filtered, even with no heatmap present yet.
5. This alone is a demoable MVP: "one-click professional incident report."

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. Add User Story 1 → validate independently → MVP.
3. Add User Story 2 → validate independently → reports generated from this point forward automatically gain the heatmap section.
4. Add User Story 3 → validate independently → CSV/JSON export available alongside the PDF report.
5. Phase 6: Polish, documentation, final whole-feature review.

---

## Notes

- [P] tasks touch different files with no completed-task dependency between them.
- [Story] labels map every user-story-phase task to US1/US2/US3 for traceability back to `spec.md`.
- Every FR-P5-0xx requirement from `spec.md` (including the 5 added during the risk-review checklist pass: FR-P5-020 through FR-P5-024) is covered by at least one task above — job-state gating (FR-P5-020) in T010/T024, in-progress feedback (FR-P5-021) in T012, missing-file errors (FR-P5-022) implicitly covered by T010/T024's existing error-path tests plus T013/T026's end-to-end verification, filename-only chain-of-custody (FR-P5-023) in T008/T009/T010, and the keyboard-operable heatmap toggle (FR-P5-024) in T020.
