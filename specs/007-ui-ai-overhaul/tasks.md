# Tasks: UI/UX Overhaul & Enhanced AI Analysis

**Input**: `specs/007-ui-ai-overhaul/`
**Branch**: `007-ui-ai-overhaul`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/api.md ✓, quickstart.md ✓

**Tests**: TDD is MANDATORY for all `app/core/` and `app/api/` files (Constitution Principle III).
Frontend JS (`static/js/`) is exempt — verified via quickstart.md manual scenarios instead.

**Organization**: Tasks are grouped by phase. US1 (P1) = AI pipeline. US2 (P1) = Report overhaul. US3 (P2) = UI polish.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unfinished dependencies)
- **[Story]**: User story (US1, US2, US3)
- All `app/core/` and `app/api/` tasks require a failing test written first

---

## Global Constraints (apply to ALL tasks)

1. All file paths via `pathlib.Path` — no bare string concatenation
2. `open-clip-torch` and `anthropic` MUST use `try/except ImportError` — graceful no-op when absent
3. `session.update()` for all writes to session state — never mutate live dict directly
4. TDD sequence for `app/core/` and `app/api/`: write test → confirm fail → implement → confirm pass → commit
5. `FrameAnalysis` dict shape: `{caption: str, object_caption: str, detections: list[dict], clip_embedding_path: str|None}`
   - `caption` and `object_caption` are `""` (not `None`) when absent
   - `detections` is `[]` (not `None`) when absent
6. SSE event backwards compatibility: new event types (`report_stage`, `report_done`) are additive
7. `formats` param on export endpoint defaults to `["md", "pdf"]` (backwards compat)
8. Florence-2: use `Florence2ForConditionalGeneration`, `device_map="cpu"` (not "auto"), no `trust_remote_code`
9. CLIP model name: `'ViT-B-32-quickgelu'` (WITH `-quickgelu` suffix) — plain `'ViT-B-32'` loads wrong weights
10. Per-frame Florence-2 inference timeout: 30 seconds; on timeout → `caption=""`, log WARN, continue
11. CLIP sidecar write failure: log WARN, skip embedding for that event, continue report — do NOT abort

---

## Phase 1: Setup

**Purpose**: Branch verified and CLAUDE.md plan pointer updated. Branch already exists.

- [ ] T001 Verify branch `007-ui-ai-overhaul` is active; confirm `CLAUDE.md` between `<!-- SPECKIT START -->` and `<!-- SPECKIT END -->` points to `specs/007-ui-ai-overhaul/plan.md`; no code changes needed if already correct

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: All failing tests for US1 + US2 backend modules MUST exist before any implementation begins (Constitution Principle III). Frontend JS tasks are exempt.

**Independent test criteria**: `pytest tests/test_frame_analyzer.py tests/test_llm_synthesizer.py -v` shows all new tests collected and failing (ImportError or assertion failures). Zero passes.

- [ ] T002 Write ALL failing TDD tests before any implementation code:
  - `tests/test_frame_analyzer.py` — new file: tests for `FrameAnalyzer.analyze()`, `FrameAnalyzer.is_available()`, empty return when Florence-2 absent, correct dict shape `{caption, object_caption, detections, clip_embedding_path}`
  - `tests/test_llm_synthesizer.py` — new file: tests for `LLMSynthesizer.synthesize()` with no API key → returns rule-based string, with mock API error → falls back, `llm_used` flag returns correctly
  - `tests/test_narrative_synthesizer.py` — update existing file: add tests for new `temporal_analysis()` method (early/middle/late counts), `trend_direction()` method (rising/falling/sporadic/uniform)
  - `tests/test_intel_report.py` — partial update (C1 FIX — Principle III: new app/core/ logic requires failing tests first):
    - Test that `job.py` export endpoint accepts `formats=["md"]` param and returns `pdf_path=None`; mock FrameAnalyzer
    - Test response fields: `florence_available` is bool, `llm_used` is bool, `llm_notice` is str (M2 FIX)
    - Test `intel_report_renderer._build_svg_timeline(events, duration_s)` returns a string starting with `<svg` containing at least one `<rect` per event
    - Test `intel_report_renderer._annotate_thumbnail(thumb_path, detections=[])` returns a non-empty base64 string when thumb exists; returns non-empty base64 string when thumb missing (fallback)
    - Test `intel_report_renderer._build_scene_breakdown(events)` returns list of length min(5, len(events)); each entry has keys `{rank, caption, object_caption, detections, thumbnail_b64}`
  - `tests/test_stream.py` — new file (C2 FIX — Principle III: new app/api/ logic requires failing tests first):
    - Test that when session `report_stage` is non-empty, SSE poll emits a `report_stage` type event with stage/current/total/ts fields
    - Test that when session `report_done_pending` is True, SSE poll emits a `report_done` type event with md_path/pdf_path; after emission `report_done_pending` is reset to False
    - Test that when `report_stage=""` and `report_done_pending=False`, no `report_stage` or `report_done` events are emitted
  - Run `pytest` to confirm all new tests FAIL (not skip — ImportError or AttributeError is acceptable) before proceeding to T003

---

## Phase 3: User Story 1 — AI Pipeline (Florence-2 + CLIP + LLM)

**Story goal**: Replace BLIP-based single caption with multi-task Florence-2 pipeline + optional CLIP embeddings + optional LLM executive summary.

**Independent test criteria**: `pytest tests/test_frame_analyzer.py tests/test_llm_synthesizer.py tests/test_narrative_synthesizer.py -v` — all tests pass.

- [ ] T003 [US1] Implement `app/core/frame_analyzer.py` — Florence-2 multi-task singleton:
  - Class `FrameAnalyzer` with class-level singleton `_instance`
  - `is_available() -> bool`: try importing `Florence2ForConditionalGeneration`; return True if weights cached at `Path.home() / ".cache" / "huggingface" / "hub" / "models--microsoft--Florence-2-base"` (M1 FIX — use pathlib.Path, not bare `~` string)
  - `analyze(image_path: Path) -> dict`: loads image with PIL, runs three tasks:
    1. `<MORE_DETAILED_CAPTION>` → `caption`
    2. `<OD>` → `detections` (list of `{label, bbox}`)
    3. `<REGION_CAPTION>` on first detected object crop (if any) → `object_caption`
  - 30-second timeout per task using `concurrent.futures.ThreadPoolExecutor`; on timeout set field to `""`/`[]` and log WARNING
  - Model load: `Florence2ForConditionalGeneration.from_pretrained("microsoft/Florence-2-base", torch_dtype=torch.float32, device_map="cpu")`
  - Graceful fallback: if Florence-2 not installed or model load fails → return `{caption:"", object_caption:"", detections:[], clip_embedding_path:None}`
  - Attach `clip_embedding_path` from `ClipIndexer.embed(image_path)` call (import `clip_indexer` lazily)
  - All tests in `tests/test_frame_analyzer.py` must pass after implementation
  - Exact API signatures in `specs/007-ui-ai-overhaul/research.md`

- [ ] T004 [P] [US1] Implement `app/core/clip_indexer.py` — CLIP ViT-B/32 embedding writer:
  - Class `ClipIndexer` with class-level singleton
  - `is_available() -> bool`: try `import open_clip`
  - `embed(image_path: Path) -> str | None`: if unavailable return None; load image, embed with `open_clip.create_model_and_transforms('ViT-B-32-quickgelu', pretrained='openai')`, L2-normalise, save to `image_path.parent / (image_path.stem + '.clip.npy')`, return absolute path string
  - On `.npy` write failure (OSError): log WARNING, return None — never raise to caller
  - All paths via `pathlib.Path`
  - Unit tested by tests in `tests/test_frame_analyzer.py` (uses ClipIndexer internally)

- [ ] T005 [P] [US1] Implement `app/core/llm_synthesizer.py` — Claude Haiku API wrapper:
  - Class `LLMSynthesizer`
  - `is_available() -> bool`: `anthropic` installed AND `ANTHROPIC_API_KEY` env var is non-empty
  - `synthesize(events: list[dict], duration_s: float, narrative: NarrativeSynthesizer) -> tuple[str, bool, str]`:
    Returns `(summary_text, llm_used, notice_text)`
    - If available: build prompt from structured event JSON, call `client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=512, messages=[...])`, return `(text, True, "")`
    - On any exception or if unavailable: call `narrative.executive_summary(events)`, return `(text, False, "Executive summary: rule-based synthesis — LLM API unavailable")`
  - Prompt must include: video duration, event count, per-event dict with `{timestamp, confidence, caption, detections, object_caption}`
  - All tests in `tests/test_llm_synthesizer.py` must pass
  - Exact API signatures in `specs/007-ui-ai-overhaul/research.md`

---

## Phase 4: User Story 1 — NarrativeSynthesizer Enhancements

**Story goal**: Enrich rule-based executive summary with temporal distribution and trend direction.

**Independent test criteria**: `pytest tests/test_narrative_synthesizer.py -v` — all new tests pass.

- [ ] T006 [US1] Update `app/core/narrative_synthesizer.py` — add two new public methods:
  - `temporal_analysis(events: list[dict], duration_s: float) -> dict`:
    Divides video into thirds. Returns `{"early": int, "middle": int, "late": int, "peak_third": str}`.
    `peak_third` is "early", "middle", or "late" (highest count wins; ties go to earliest).
  - `trend_direction(events: list[dict], duration_s: float) -> str`:
    Compares first-half vs second-half event density.
    Returns one of: `"rising"` (2nd half ≥ 1.5× first), `"falling"` (1st half ≥ 1.5× second), `"sporadic"` (uneven, no clear trend), `"uniform"`.
  - Update `executive_summary(events: list[dict], duration_s: float = None) -> str` to call both new methods and incorporate results into the summary paragraph
  - Remove the 200-character truncation from event descriptions (search for `[:200]` or `[0:200]` and remove)
  - All existing tests must still pass; all new tests from T002 must pass
  - Do NOT modify method signatures for existing public methods (backwards compat)

---

## Phase 5: User Story 2 — Report API & SSE Stage Progress

**Story goal**: Add `formats` param to export endpoint, emit SSE stage events during generation, wire FrameAnalyzer into report pipeline.

**Independent test criteria**: `pytest tests/test_intel_report.py -v` — formats param test passes; SSE stage events test passes.

- [ ] T007 [US2] Update three files — session state, API endpoint, SSE stream:

  **`app/session.py`**:
  - Add FIVE fields to `_DEFAULTS` (H1 FIX — adds `report_done_pending` to prevent race condition):
    `"report_stage": "", "report_stage_current": 0, "report_stage_total": 0, "report_stage_timestamp": "", "report_done_pending": False`

  **`app/api/job.py`** — update `POST /job/intel-report/export`:
  - Accept JSON body `{"formats": list[str]}` (default `["md", "pdf"]` if missing); validate each element is "md" or "pdf"; return HTTP 400 if list is empty or contains invalid values
  - Import and use `FrameAnalyzer` (from `app.core.frame_analyzer`) for per-event analysis; store results in session event data
  - Import and use `LLMSynthesizer` (from `app.core.llm_synthesizer`)
  - Emit stage events via `session.update(report_stage="thumbnails", report_stage_current=n, report_stage_total=total)` at each stage boundary; for `ai_analysis` also update `report_stage_timestamp`
  - Response body: `{md_path: str|None, pdf_path: str|None, florence_available: bool, llm_used: bool, llm_notice: str}` — remove `moondream_available` field
  - Skip PDF generation if `"pdf"` not in formats (do not call Qt bridge); skip .md write if `"md"` not in formats
  - On completion (success OR error): `session.update(report_stage="", report_done_pending=True)` — set `report_done_pending=True` BEFORE clearing `report_stage` so the SSE loop can capture it (H1 FIX)

  **`app/api/stream.py`**:
  - In the SSE poll loop, when `snap.get("report_stage")` is non-empty, emit:
    `{"type": "report_stage", "stage": ..., "current": ..., "total": ..., "ts": ...}`
  - When `snap.get("report_done_pending")` is True, emit `{"type": "report_done", "md_path": ..., "pdf_path": ...}` THEN call `session.update(report_done_pending=False)` to prevent duplicate emission (H1 FIX — no prior-state tracking needed; `report_done_pending` flag is the single source of truth)

  All tests from T002's job.py section must pass.

---

## Phase 6: User Story 2 — Report Template & Renderer

**Story goal**: Scene Breakdown section with annotated thumbnails, SVG activity timeline, full-length descriptions, confidence colour bars.

**Independent test criteria**: `pytest tests/test_intel_report.py -v` — all intel_report_renderer tests pass (written in T002). Additionally: generate a report via the running app; verify Scene Breakdown section and SVG timeline are present in the output.

- [ ] T008 [US2] Update two files — renderer and HTML template:

  **`app/core/intel_report_renderer.py`**:
  - Add `_build_svg_timeline(events: list, duration_s: float) -> str`:
    Returns inline SVG string. viewBox `"0 0 800 48"`. Background rail at y=20, h=8, fill=#2e3147, rx=4.
    Per event: `x = int(event_start_s / duration_s * 800)`, `h = max(8, int(confidence * 32))`,
    `y = 20 - h//2`, w=4, rx=2. Fill colour: MOG2=#6b7280, YOLO person=#3b82f6, YOLO vehicle=#f97316, YOLO other=#8b5cf6.
  - Add `_annotate_thumbnail(thumb_path: Path, detections: list) -> str`:
    Opens JPEG with PIL, draws bounding boxes with `ImageDraw.rectangle` (outline=#4f8ef7, width=2) and labels.
    Returns base64-encoded JPEG string. Falls back to original thumbnail if PIL fails.
  - Add `_build_scene_breakdown(events: list) -> list`:
    Returns top 5 events sorted by confidence descending (fewer if <5 events). For each: annotate thumbnail, include full caption, object_caption, detections, rank.
  - Update `render(...)` method to pass `svg_timeline`, `scene_breakdown` to Jinja2 template context
  - Use the `LLMSynthesizer.synthesize()` result for executive summary (pass `llm_notice` to template too)

  **`app/templates/intel_report.html`**:
  - Add SVG timeline section at top of report body (above the timeline table): render `{{ svg_timeline|safe }}`
  - Add Scene Breakdown section: render each entry as a card with: annotated thumbnail (`<img src="data:image/jpeg;base64,{{ entry.thumbnail_b64 }}">`), h3 with timestamp + confidence, full paragraph caption, italic object_caption sub-line, detection label pills
  - Confidence colour bars on timeline table rows: add `<div class="conf-bar" style="width:{{ (event.confidence*100)|int }}%; background: {{ conf_colour }}"></div>`
    Colour scale: ≥0.8 = #22c55e, ≥0.5 = #f59e0b, <0.5 = #ef4444
  - LLM notice: if `{{ llm_notice }}` is non-empty, render a muted italic line in the executive summary section: `<p class="llm-notice"><em>{{ llm_notice }}</em></p>`
  - Event descriptions in timeline table: no length truncation — render full `{{ event.caption }}`

---

## Phase 7: User Story 3 — Export Page UI

**Story goal**: Report format modal, 4-stage SSE progress display, AI readiness badges.

**Independent test criteria**: quickstart.md Scenarios 1, 2, 4 — all steps pass.

- [ ] T009 [US3] Update `static/js/pages/export.js`:
  - Add report format modal HTML (injected into DOM, not a separate file): two checkboxes (Markdown, PDF), Cancel and Generate buttons; shown before any POST call
  - Persist format choice in `localStorage["intelReportFormat"]` as `{"md": bool, "pdf": bool}`; pre-select on modal open
  - POST body: `{"formats": [...]}` with selected formats; validate at least one selected before enabling Generate
  - 4-stage SSE progress UI: listen to `/api/stream` for `report_stage` events during generation; render four named stage rows with count/status; each stage gets a checkmark when complete
  - AI readiness badges: read `florence_available` and `llm_available` from `/api/job/status` response; render "Florence-2 ready" (green badge) or "AI analysis unavailable" (grey badge); render "LLM synthesis on" (blue badge) only if `llm_available=true`
  - Remove check for `moondream_available` (replaced by `florence_available`)
  - Frontend JS — no automated test; verified by quickstart.md Scenarios 1, 2, 4

---

## Phase 8: User Story 3 — Processing & Debug UI

**Story goal**: Timestamped, colour-coded log panel on Processing page; enhanced debug drawer.

**Independent test criteria**: quickstart.md Scenarios 3, 5 — all steps pass.

- [ ] T010 [P] [US3] Update `static/js/pages/processing.js` — log panel:
  - Add "Show Logs" / "Hide Logs" toggle button (hidden by default) near page header
  - Log panel element: hidden by default (`display:none`); revealed on toggle
  - Each log entry format: `HH:MM:SS  SEVERITY  message` where severity is one of INFO/EVENT/WARN/ERROR
  - Colour coding: INFO=#9ca3af (grey), EVENT=#3b82f6 (blue), WARN=#f59e0b (amber), ERROR=#ef4444 (red)
  - Stage separator headings: when a new processing stage begins, insert a `<hr>` with stage name label
  - "Copy" button at top-right of log panel: copies all log text to `navigator.clipboard`
  - Frontend JS — no automated test; verified by quickstart.md Scenario 3

- [ ] T011 [P] [US3] Update `static/js/debug-log.js` — enhanced entries:
  - Prefix each entry with `HH:MM:SS.mmm` timestamp (using `new Date().toTimeString().slice(0,8)` + `.` + ms)
  - For fetch/XHR entries: append `(N ms)` duration and HTTP status badge (e.g. `200 OK`)
  - Error styling: entries with status >= 400 get `border-left: 3px solid #ef4444`
  - Count badge: update the debug drawer toggle button to show total request count as a chip badge
  - Frontend JS — no automated test; verified by quickstart.md Scenario 5

---

## Phase 9: Cleanup & Documentation

**Purpose**: Remove replaced module, update optional deps docs, update ROADMAP.

- [ ] T012 Cleanup three items (no new tests needed — existing tests must still pass):
  - Before deleting `app/core/frame_describer.py`: run `grep -r "frame_describer" app/ tests/` and update ALL found import sites (L1 FIX — job.py and others may still reference frame_describer); then delete the file
  - Update `requirements.txt`: replace the BLIP comment block with documentation for new optional deps:
    ```
    # Optional — AI visual frame analysis in intelligence reports (install separately)
    # pip install transformers accelerate
    # Model microsoft/Florence-2-base (~230 MB) downloads on first use
    #
    # Optional — semantic frame embeddings for Phase 8 chatbot (install separately)
    # pip install open-clip-torch
    # Model ViT-B-32-quickgelu (~600 MB) downloads on first use
    #
    # Optional — LLM executive summaries in intelligence reports (install separately)
    # pip install anthropic
    # Requires ANTHROPIC_API_KEY environment variable
    ```
  - Update `tests/test_intel_report.py`: replace any `from app.core.frame_describer import FrameDescriber` with `from app.core.frame_analyzer import FrameAnalyzer`; replace `moondream_available` references with `florence_available`
  - Run `pytest tests/ -q` — zero failures before committing

- [ ] T013 [P] Update documentation (no tests needed):
  - `ROADMAP.md`: update Phase 7 entry to show "SHIPPED", update the moondream2/BLIP references to Florence-2, update Phase 8 to note CLIP embeddings are now stored from Phase 7
  - Update `docs/superpowers/plans/2026-06-19-cctv-pc-processor.md` Phase 7 status to complete
  - Update `docs/superpowers/specs/2026-06-26-ui-ai-overhaul-design.md` if it exists — mark Phase 7 shipped; no code changes

---

## Dependency Graph

```
T001 (setup)
  └─ T002 (TDD fail-first) — MUST complete before T003, T004, T005, T006, T007
       ├─ T003 (frame_analyzer.py)
       │    └─ T007 (job.py — imports FrameAnalyzer)
       ├─ T004 [P] (clip_indexer.py — called by frame_analyzer)
       ├─ T005 [P] (llm_synthesizer.py)
       │    └─ T007 (job.py — imports LLMSynthesizer)
       └─ T006 (narrative_synthesizer.py)
            └─ T007 (LLMSynthesizer uses NarrativeSynthesizer fallback)
                 └─ T008 (renderer — uses FrameAnalyzer data + LLMSynthesizer)
                      └─ T009 (export.js — consumes SSE events + report format)
                           ├─ T010 [P] (processing.js — independent)
                           └─ T011 [P] (debug-log.js — independent)
T012 (cleanup — after T003 confirmed working)
T013 [P] (docs — after T012)
```

## Parallel Execution Opportunities

| Parallel set | Tasks | Condition |
|---|---|---|
| Set A | T003, T004, T005 | After T002 complete; different files, no interdependencies |
| Set B | T010, T011 | After T009 (or truly independent — no shared JS files) |
| Set C | T012, T013 | Final cleanup; T012 must finish before T013 starts ROADMAP update |

## Implementation Strategy

**MVP scope (US1 only)**: Complete T001 → T002 → T003 → T004 → T005 → T006.
After T006, Florence-2 descriptions appear in reports even before the full report overhaul (T007–T008).
US2 (T007–T008) delivers the format modal, SSE progress, and new report sections.
US3 (T009–T011) delivers UI polish on top of a fully working feature.

**Suggested delivery order**: Phase 2 (T002) → Phase 3 (T003–T005 parallel) → Phase 4 (T006) → Phase 5 (T007) → Phase 6 (T008) → Phase 7 (T009) → Phase 8 (T010–T011 parallel) → Phase 9 (T012–T013).

## Task Count Summary

| Phase | Tasks | Story | TDD required |
|---|---|---|---|
| Setup | 1 (T001) | — | No |
| Foundational | 1 (T002) | — | Writes tests |
| US1 AI Pipeline | 3 (T003–T005) | US1 | Via T002 |
| US1 Synthesis | 1 (T006) | US1 | Via T002 |
| US2 API & SSE | 1 (T007) | US2 | Via T002 |
| US2 Renderer | 1 (T008) | US2 | Manual (quickstart) |
| US3 Export UI | 1 (T009) | US3 | Manual (quickstart) |
| US3 Processing/Debug UI | 2 (T010–T011) | US3 | Manual (quickstart) |
| Cleanup & Docs | 2 (T012–T013) | — | No |
| **Total** | **13** | | |
