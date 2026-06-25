# Tasks: Video Intelligence Export (Phase 6)

**Input**: Design documents from `specs/006-video-intel-export/`  
**Prerequisites**: plan.md ✓ | spec.md ✓ | data-model.md ✓ | contracts/api.md ✓ | research.md ✓ | quickstart.md ✓

**TDD Mandate (Constitution III)**: ALL `app/core/` and `app/api/` tasks require failing tests written first.  
The 12 tests in `tests/test_intel_report.py` MUST ALL FAIL before any implementation task begins.  
Frontend `static/js/` tasks use the quickstart.md exemption (manually verified, no pytest coverage).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared state)
- **[Story]**: User story this task belongs to (US1/US2/US3)

---

## Phase 1: Setup

**Purpose**: Document optional dependency; no structural changes needed (project layout exists).

- [ ] T001 Add optional moondream pip comment block to `requirements.txt` (after existing deps): `# Optional — visual frame descriptions in intelligence reports:` / `# pip install moondream   (~2GB model downloaded on first use to ~/.cache/huggingface/)`

---

## Phase 2: Foundational — TDD Test File (Fail-First Gate)

**Purpose**: Write ALL 12 failing tests before any implementation begins. This phase GATES all of Phase 3, 4, and 5 — no implementation task may start until all 12 tests exist and are confirmed to fail.

**⚠️ CRITICAL**: Run `pytest tests/test_intel_report.py -v` after writing. ALL 12 tests MUST report FAILED or ERROR (ImportError acceptable — module doesn't exist yet). Zero passes expected.

- [ ] T002 Write all 12 TDD tests in `tests/test_intel_report.py`. Tests must be runnable with `pytest tests/test_intel_report.py -v` from project root. The 12 tests are:
  - `test_executive_summary_yolo_mentions_objects` — given YOLO events with zone_label="person", `executive_summary()` returns a string containing "person"
  - `test_executive_summary_mog2_mentions_motion` — given MOG2 events (zone_label=None), output contains "motion"
  - `test_executive_summary_no_events_safe_fallback` — given empty events list, returns non-empty string without raising
  - `test_object_inventory_counts_classes` — given 3 person + 2 car events, `object_inventory()` returns [{"label":"person","count":3,...},{"label":"car","count":2,...}]
  - `test_object_inventory_empty_for_mog2` — given events with zone_label=None, `object_inventory()` returns []
  - `test_activity_stats_correct_percentages` — given known events + source_info with duration_s, `activity_stats()` returns dict with correct active_pct (verified with math)
  - `test_frame_describer_absent_returns_empty` — monkeypatch moondream import to raise ImportError; `FrameDescriber.describe(any_path)` returns ""
  - `test_frame_describer_missing_file_returns_empty` — pass non-existent Path to `FrameDescriber.describe()`; returns "" without raising
  - `test_intel_report_html_400_no_job` — GET /api/job/intel-report.html with empty session returns 400
  - `test_intel_report_html_400_no_included_events` — GET /api/job/intel-report.html with active job but zero included events returns 400
  - `test_intel_report_export_writes_md_file` — POST /api/job/intel-report/export with active job + included events writes a file at the returned md_path
  - `test_intel_report_markdown_has_json_appendix` — the written Markdown file contains a ```json block; extracting and `json.loads()`-ing it succeeds; first object has "event_index" key

**Checkpoint**: `pytest tests/test_intel_report.py -v` shows all 12 FAILED/ERROR. Implementation phases may now begin.

---

## Phase 3: US1 — Intelligence Report Generation (Priority: P1) 🎯 MVP

**Goal**: Single-click generation of Markdown + PDF intelligence report from any completed detection run, covering all 8 required sections and the JSON data appendix.

**Independent Test**: After running detection (MOG2 or YOLO mode), clicking "Generate Intelligence Report" produces `{stem}_intelligence_{ts}.md` and `{stem}_intelligence_{ts}.pdf` in the output folder. User can open either file and find: executive summary, timeline table, heatmap section, JSON appendix. `pytest tests/test_intel_report.py -k "not frame_describer"` passes (10 of 12 tests).

**Note on US3 constraints**: FR-P6-020 (dual timestamps), FR-P6-021–22 (JSON appendix), FR-P6-023 (100KB/UTF-8), FR-P6-024 (auto-mkdir) are all enforced within this phase — US3 has no separate implementation phase.

### Implementation for User Story 1

- [ ] T003 [P] [US1] Implement `app/core/narrative_synthesizer.py` with four pure functions:
  - `executive_summary(events: list[dict], source_info: dict, settings: dict) -> str` — 2-3 sentence paragraph. For YOLO: name the dominant class and event count. For MOG2: describe motion activity and active_pct.
  - `activity_stats(events: list[dict], source_info: dict) -> dict` — returns dict with: `event_count`, `active_s` (sum of durations), `active_pct` (clamped 0–100), `busiest_period` (clock-formatted start–end of the 60-second sliding window containing the most events; "N/A" if 0 events), `avg_confidence` (mean peak_motion_score), `detection_mode` (from events' zone_label pattern).
  - `object_inventory(events: list[dict]) -> list[dict]` — for YOLO (any event has non-None zone_label): group by zone_label, return [{"label", "count", "first_clock", "last_clock"}] sorted by count desc. For MOG2 (all zone_label=None): return [].
  - `timeline_entries(events: list[dict], descriptions: dict[int, str]) -> list[dict]` — return one dict per event: {"event_num" (1-based), "start_clock", "start_s", "end_clock", "duration_s", "label" (zone_label or "motion"), "confidence_pct" (round(peak_motion_score*100)), "description" (descriptions.get(event_index, "") or "N/A")}. Description truncated to 200 chars.
  Run `pytest tests/test_intel_report.py -k "executive_summary or object_inventory or activity_stats"` — 6 tests must pass.

- [ ] T004 [P] [US1] Create `app/templates/intel_report.html` — self-contained Jinja2 template (autoescape=True, inline `<style>`, all images as `data:image/jpeg;base64,...` or `data:image/png;base64,...` URIs, no external links). Sections in order:
  1. **Header**: source_name, generated_at, detection_mode, duration_fmt
  2. **Executive Summary**: `{{ executive_summary }}` paragraph
  3. **Activity Statistics**: table from `{{ stats }}` (event_count, active_s, active_pct, busiest_period, avg_confidence)
  4. **Object Inventory** (conditional `{% if object_inventory %}`): table with label, count, first_clock, last_clock
  5. **Chronological Timeline**: table from `{{ timeline }}` — columns: #, Start Time, End Time, Duration, Activity, Confidence, Description
  6. **Key Moments** (top 3 by confidence): each with `<img src="data:...">` from thumb_b64, description text
  7. **Activity Heatmap**: `{% if heatmap_b64 %}<img ...>{% else %}<p>Heatmap not available for this run.</p>{% endif %}`
  8. **Detection Configuration**: table from `{{ settings }}` dict
  9. **Data Appendix (JSON)**: `<pre><code>{{ events_json }}</code></pre>` — this is the machine-readable section for Markdown; in PDF it renders as a code block.
  Match the typography and table styling of `app/templates/report.html` (import its CSS class patterns).

- [ ] T005 [US1] Implement `app/core/intel_report_renderer.py` — mirrors `app/core/report_renderer.py` exactly:
  ```python
  from pathlib import Path
  import jinja2
  _TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
  _env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=True)
  def render(context: dict) -> str:
      return _env.get_template("intel_report.html").render(**context)
  ```
  Depends on T004.

- [ ] T006 [US1] Add `GET /api/job/intel-report.html` endpoint to `app/api/job.py`. Guards: (1) no active job → 400 "No active job"; (2) status == "detecting" → 400 "Detection is still in progress"; (3) no included events → 400 "No events to report — no events are currently included". Then:
  - `included = [ev for ev in snap["events"] if ev.get("included", True)]`
  - `thumbnail_gen.run(job_id, source_path, included, logger)`
  - `for ev in included: ev["thumb_b64"] = _b64_file(job_dir/"thumbnails"/f"{ev['event_index']}.jpg")`
  - `heatmap_b64 = _b64_file(job_dir/"heatmap.png")`
  - Descriptions dict: `{ev["event_index"]: "" for ev in included}` (FrameDescriber populated in T011)
  - Build IntelReportContext using `narrative_synthesizer.*` functions + `seconds_to_clock()` + settings snapshot
  - Key moments: top 3 included events by `peak_motion_score` desc, tiebreak by `event_index` asc
  - `from app.core.intel_report_renderer import render as render_intel`; `html = render_intel(context)` 
  - Return `HTMLResponse(html)`
  Run `pytest tests/test_intel_report.py -k "html_400"` — 2 tests must pass. Depends on T003, T005.

- [ ] T007 [US1] Add `POST /api/job/intel-report/export` endpoint to `app/api/job.py`. Same guards and thumbnail generation as T006. Additionally:
  - `output_dir = Path(snap.get("output_dir") or (Path.home() / "Desktop"))` ; `output_dir.mkdir(parents=True, exist_ok=True)`
  - `timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")`
  - `source_stem = Path(snap["source_path"]).stem`
  - Build the Markdown string directly (NOT via the HTML template) with these sections (plain text, not HTML):
    - `# Video Intelligence Report: {source_name}` header with metadata
    - `## Executive Summary` — `executive_summary()` output
    - `## Activity Statistics` — Markdown table from `activity_stats()` output
    - `## Object Inventory` (YOLO only) — Markdown table from `object_inventory()`
    - `## Chronological Timeline` — Markdown table from `timeline_entries()` (descriptions="" until T011)
    - `## Key Moments` — top-3 events with thumbnail path reference and description
    - `## Activity Heatmap` — reference to heatmap file path (not embedded in Markdown)
    - `## Detection Configuration` — Markdown table of settings
    - `## Data Appendix (JSON)` — ` ```json\n{json.dumps(events_records, indent=2)}\n``` ` where events_records is list of dicts with: event_index, start_s, end_s, start_clock, end_clock, peak_motion_score, zone_label, included (omit description key if empty)
  - Enforce UTF-8 + 100KB: `md_text = ...`; if `len(md_text.encode("utf-8")) > 100*1024` then truncate timeline description columns further (already capped at 200 chars in timeline_entries; this is a safety net)
  - `out_path = output_dir / f"{source_stem}_intelligence_{timestamp}.md"` ; `out_path.write_text(md_text, encoding="utf-8")`
  - Return `JSONResponse({"md_path": str(out_path), "moondream_available": FrameDescriber.is_available()})`
  Run `pytest tests/test_intel_report.py -k "export_writes or json_appendix"` — 2 tests must pass. Depends on T006.

- [ ] T008 [P] [US1] Add intelligence report PDF support to `shell/main_window.py`, following `_generate_pdf_report()` exactly:
  - In `__init__`: add `window._cctvGenerateIntelReport = false;` to the JS bridge constants; add `window.addEventListener('cctv:generate-intel-report', e => { window._cctvIntelReportPdfPath = e.detail.pdf_path; window._cctvGenerateIntelReport = true; });`
  - In `_handle_browse_flags()`: add a fifth check after the existing four — `if flags.get("_cctvGenerateIntelReport"): self._generate_intel_report_pdf(flags["_cctvIntelReportPdfPath"])`
  - Add method `_generate_intel_report_pdf(self, pdf_path: str)`: creates a hidden `QWebEnginePage`, loads `http://127.0.0.1:{self._port}/api/job/intel-report.html`, on `loadFinished` calls `page.printToPdf(pdf_path)`, on `pdfPrintingFinished` calls `page.deleteLater()` and removes page from `self._pending_report_pages`
  - Add page to `self._pending_report_pages` list (already exists from Phase 5; reuse it)
  Note: T008 can be implemented in parallel with T003/T004 but can only be verified after T006 is complete.

- [ ] T009 [US1] Add "Video Intelligence" card section to `static/js/pages/export.js` after the existing "Incident Report" card:
  - Card structure: header "Video Intelligence Report", description text, button "Generate Intelligence Report (Markdown + PDF)", status div
  - On button click:
    1. Disable button, show "Generating..."
    2. `fetch('/api/job/intel-report/export', {method: 'POST'})` with try/catch
    3. On success: read `{md_path, moondream_available}` from JSON response; derive pdf_path = md_path.replace(/\.md$/, '.pdf'); dispatch `new CustomEvent('cctv:generate-intel-report', {detail: {pdf_path}})` on `document`; show "Markdown saved to {md_path}. PDF generating to same folder."
    4. If `!moondream_available`: append "Install moondream (pip install moondream) to add visual descriptions."
    5. On error: show error message from response JSON
  - Verify with quickstart.md Scenario 1 (MOG2, no moondream) and Scenario 7 (excluded events check). Depends on T007 and T008.

**Checkpoint**: `pytest tests/test_intel_report.py -v` — 10 of 12 tests pass (frame_describer tests still FAIL). Export page shows Video Intelligence card. Markdown and PDF generated for a completed MOG2 or YOLO run.

---

## Phase 4: US2 — Visual Frame Descriptions via Moondream2 (Priority: P2)

**Goal**: When moondream is installed and cached, each event in the report's timeline has a natural language visual description. When not installed, report generates cleanly with "N/A" descriptions and a frontend notice.

**Independent Test**: With moondream not installed — generate a report and confirm: all descriptions show "N/A", no error in frontend. Confirm `pytest tests/test_intel_report.py -k "frame_describer"` passes (2 tests).

### Implementation for User Story 2

- [ ] T010 [US2] Implement `app/core/frame_describer.py` with `FrameDescriber` class-level singleton:
  ```python
  from pathlib import Path
  class FrameDescriber:
      _model = None
      @classmethod
      def is_available(cls) -> bool:
          try:
              import moondream  # noqa: F401
              return True
          except ImportError:
              return False
      @classmethod
      def describe(cls, image_path: Path) -> str:
          if not cls.is_available():
              return ""
          try:
              from PIL import Image
              if cls._model is None:
                  import moondream as md
                  cls._model = md.vl()
              img = Image.open(str(image_path))
              result = cls._model.query(img, "Briefly describe what is happening in this security camera frame. Focus on people, vehicles, and any notable actions.")
              return result.answer if hasattr(result, "answer") else str(result)
          except Exception:
              return ""
  ```
  Run `pytest tests/test_intel_report.py -k "frame_describer"` — both tests must pass.

- [ ] T011 [US2] Integrate `FrameDescriber` into both endpoints in `app/api/job.py`:
  - In both `GET /api/job/intel-report.html` and `POST /api/job/intel-report/export`, after `thumbnail_gen.run()`:
    ```python
    from app.core.frame_describer import FrameDescriber
    descriptions = {}
    for ev in included:
        thumb = job_dir / "thumbnails" / f"{ev['event_index']}.jpg"
        descriptions[ev["event_index"]] = FrameDescriber.describe(thumb) if thumb.exists() else ""
    ```
  - Pass `descriptions` to `narrative_synthesizer.timeline_entries(included, descriptions)` and to key moments description
  - In POST endpoint: include `"description": desc` in each JSON appendix record (omit key entirely if description is "")
  - In HTML context: pass `moondream_available = FrameDescriber.is_available()` (already returned by POST; add to GET context too for template conditional)
  Depends on T010.

- [ ] T012 [US2] The frontend `static/js/pages/export.js` moondream notice is already implemented in T009 (`if (!moondream_available)` branch). Verify this notice appears correctly with quickstart.md Scenario 2 (no moondream installed). If the branch was already added in T009, this task is a verification-only step — run Scenario 2 and mark complete. If the conditional was omitted in T009, add it now.

**Checkpoint**: `pytest tests/test_intel_report.py -v` — all 12 tests PASS. With moondream not installed: descriptions column shows "N/A", no crash. With moondream installed: descriptions are natural language.

---

## Phase 5: US3 — Markdown RAG-Readiness Validation (Priority: P3)

**Goal**: Confirm the Markdown file is structured for AI chatbot consumption per FR-P6-020 through FR-P6-024. No new implementation — US3 constraints are enforced in T004 (dual timestamps in template) and T007 (JSON appendix, UTF-8, 100KB, auto-mkdir).

**Independent Test**: Run the driving script from `quickstart.md` against the live app. Run quickstart.md Scenario 9 (chatbot smoke test).

- [ ] T013 [US3] Validate RAG-readiness: run the driving script in `quickstart.md` against the live app with a completed detection run. Verify: (1) JSON appendix parses with `json.loads()`; (2) each event has `event_index`, `start_s`, `start_clock`, `end_s`, `end_clock`, `peak_motion_score`, `zone_label`, `included`; (3) Markdown file size < 100 KB; (4) Both `start_clock` and `start_s` are present for every event (dual timestamp requirement FR-P6-020). Fix any failing check in T007 before marking complete.

**Checkpoint**: All US3 requirements verified. Markdown is ready for Phase 7 chatbot consumption.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification pass, documentation update.

- [ ] T014 [P] Run full test suite `pytest tests/ -v` from project root. ALL existing tests (49+) PLUS all 12 new intel_report tests MUST pass. Fix any regressions before marking complete.
- [ ] T015 [P] Run quickstart.md Scenarios 1–8 (full manual verification of all acceptance scenarios). Document any issues found. Fix before marking complete.
- [ ] T016 [P] Update `ROADMAP.md`: add a `## F. Video Intelligence Export — ✅ Shipped in Phase 6` entry (similar to the Phase 5 note in section C), listing what was delivered. Remove Phase 6 from the "Suggested Order" roadmap if listed there.
- [ ] T017 [P] Update `docs/superpowers/specs/2026-06-25-video-intelligence-export-design.md`: change `**Status**: Approved — ready for speckit pipeline` to `**Status**: Shipped in Phase 6 (2026-06-25)`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (TDD tests)**: Depends on Phase 1. **BLOCKS all implementation phases.**
- **Phase 3 (US1)**: Depends on Phase 2 (test file exists and confirmed failing)
- **Phase 4 (US2)**: Depends on Phase 3 checkpoint (US1 complete, 10 tests pass)
- **Phase 5 (US3 validation)**: Depends on Phase 3 + Phase 4 (all 12 tests pass, full app running)
- **Phase 6 (Polish)**: Depends on Phases 3–5 complete

### Within Phase 3 — Task Order

```
T003 [narrative_synthesizer] ──┐
T004 [intel_report.html]      ─┤→ T005 [renderer] → T006 [GET endpoint] → T007 [POST endpoint] → T009 [JS card]
T008 [main_window.py] ────────┘                                           ↗
```

T003, T004, and T008 can run in parallel (different files).  
T005 depends on T004.  
T006 depends on T003 and T005.  
T007 depends on T006.  
T008 can be implemented any time after T002, verified after T006.  
T009 depends on T007 and T008.

### Within Phase 4 — Task Order

T010 → T011 → T012 (sequential: each builds on the previous)

### Parallel Opportunities

- T003, T004, T008 — three different files, fully parallel in Phase 3
- T014, T015, T016, T017 — fully parallel in Phase 6 (different files, read-only tasks)

---

## Implementation Strategy

### MVP First (US1 only, Phase 3)

1. Complete T001 (setup)
2. Complete T002 (all tests fail)
3. Complete T003–T009 (US1 implementation)
4. **STOP and VALIDATE**: `pytest tests/test_intel_report.py -k "not frame_describer"` — 10 pass; quickstart.md Scenario 1
5. US1 delivers standalone value — report generates without Moondream2

### Incremental Delivery

1. Phase 3 done → Markdown + PDF intelligence report working (MOG2 + YOLO, no vision descriptions)
2. Phase 4 done → Visual descriptions in timeline when moondream installed
3. Phase 5 done → Confirmed Markdown is Phase 7 chatbot-ready
4. Phase 6 done → All tests green, full manual verification, docs updated

---

## Notes

- `[P]` = different files, no blocking dependencies — safe to assign to a parallel implementer
- `[US#]` maps each task to the user story it delivers
- Constitution III: write test (T002) → confirm failure → implement (T003+) → confirm pass → commit
- Frontend (`export.js`) is Constitution III exempt — verified via quickstart.md scenarios, not pytest
- `shell/main_window.py` changes use the same driving-script pattern as Phase 5 (no automated test needed; the Qt PDF flow is an end-to-end manual scenario)
- After T011, reset `FrameDescriber._model = None` in test teardown if needed to avoid cross-test pollution (the singleton persists across test runs in the same process)
