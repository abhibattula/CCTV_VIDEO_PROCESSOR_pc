# Roadmap — Future Phases

This is a living list of features and improvements identified as good next
steps for this project, beyond what's shipped (Phases 1-7: detection, timeline
review, undo, export presets, theme, ROI zone drawing, Stop Application, New
Project, activity heatmap overlay, PDF/HTML incident report, CSV/JSON event log
export, Video Intelligence Report with Moondream2 visual descriptions,
Florence-2 AI frame analysis, CLIP semantic embeddings, Claude Haiku LLM
executive summary, report format modal, 4-stage SSE progress, Scene Breakdown
with annotated thumbnails, SVG activity timeline, log panel polish). Nothing here is scheduled or committed — when one of these gets
picked up, it should run through the project's normal speckit pipeline
(`/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` →
`/speckit.analyze` → `/speckit.implement`) and get its own numbered spec under
`specs/`, exactly like Phases 1-4 did.

Items are grouped by theme, not priority. See "Suggested Order" at the bottom
for a recommended sequence.

---

## A. Batch & Unattended Processing

Queue multiple videos and process them sequentially (e.g. overnight,
unattended), with one summary view across all of them when done.

**Why**: Real CCTV review work is rarely "one clip at a time" — a security
manager typically has a folder per day per camera. This is the single
biggest gap between "functional tool" and "fits how the job actually works."

**Why it's not trivial**: This is the first roadmap item that pushes against
`.specify/memory/constitution.md` Principle I's deliberate "one job at a time,
all state in a single in-memory dict" design. Adding a queue means either (a)
a queue of jobs processed one at a time through the existing single-job
session model (simplest, preserves the architecture, no new persistence), or
(b) genuinely concurrent multi-job processing (bigger change, would need
per-job session state instead of one global session — a real architectural
shift, not a bolt-on). Option (a) should be the default assumption unless a
future spec pass finds a strong reason otherwise.

**Builds on**: `app/api/job.py`'s existing create/start/cancel lifecycle,
`app/session.py`'s reset-between-jobs pattern (already proven safe by Phase
4's New Project work).

**Effort**: Medium-high. **Impact**: High for recurring/professional use.

---

## B. AI / Smart Differentiators

### B1. Privacy face/plate blur on export
Redact faces or license plates in exported clips, so an "Evidence Pack" can
be shared externally without exposing bystanders' identities.

**Builds on**: The existing YOLO person detector (`app/core/yolo_detector.py`)
already locates people in-frame; this adds a Gaussian-blur pass over those
bounding boxes inside `app/core/export_engine.py`'s FFmpeg pipeline (likely
via `drawbox`/`boxblur` filters, similar in spirit to the existing burn-in
overlay feature). License-plate detection would need a small dedicated
model/heuristic (not currently in the codebase) — faces-only is the smaller,
faster-to-ship first cut.

**Effort**: Low-medium. **Impact**: High (directly enables a use case —
sharing footage with a third party — that today requires manual redaction in
another tool).

### B2. Natural-language event search
Search events by description ("show me the red car") instead of only by
detected label or score threshold.

**Builds on**: `app/core/thumbnail_gen.py` already generates a thumbnail per
event — this adds a CLIP (or similar) embedding pass over those thumbnails
and a lightweight similarity search, surfaced as a search box on the Timeline
page alongside the existing label-filter chips.

**Effort**: Medium (new model dependency, new embedding-index logic, no
existing precedent in this codebase to build on). **Impact**: High — this is
the most genuinely differentiated idea on this list versus typical
motion-alert tools.

### B3. Object tracking across frames
The same person walking through frame becomes one tracked entity instead of
several separate motion events.

**Builds on**: `app/core/detection_engine.py`/`yolo_detector.py`'s per-frame
detection loop — this adds a tracker (e.g. a simple centroid/IoU tracker, or
a lightweight re-identification model) layered on top, not a replacement of
the existing detection logic.

**Effort**: Medium-high (real tracking-by-detection logic, new edge cases
around occlusion/re-entry). **Impact**: Medium-high — makes review feel
"smart" rather than "many similar alerts," but is more substantial than it
first sounds.

### B4. Smarter highlight ranking
Improve the existing "Quick Highlights" preset's top-N-by-score selection
with deduplication (don't pick 3 near-identical consecutive events) and
diversity (spread picks across the video's timeline, not all from one burst).

**Builds on**: `app/core/export_engine.py`'s existing auto-top-N logic for
the Quick Highlights preset — this is a refinement of existing code, not a
new subsystem.

**Effort**: Low. **Impact**: Medium — quality-of-life improvement to an
existing feature, not a new capability.

---

## C. Professional Reporting — ✅ Shipped in Phase 5

PDF/HTML incident report with per-event thumbnail grid, activity heatmap,
timestamps, labels, confidence scores, and chain-of-custody SHA-256 hashes
for source and exported files. CSV and JSON event log export (one-click,
timestamped files, respects label filter). Activity heatmap overlay on the
zone-drawing preview after detection. All shipped in Phase 5.

**Remaining ideas in this space** (not yet implemented):
- Label-filter support on the HTML report (currently always shows the full
  included set — no per-label report generation)
- A real completion signal from PDF printing back into the SPA (current UX is
  an optimistic 3-second message, same pattern as Stop Application)
- Async/background thumbnail generation for very large event sets

---

## D. Settings, Onboarding & Quality-of-Life Polish

- **A real Settings page** — persisted defaults for detection
  sensitivity/padding, default export output folder, and theme, using the
  same user-configuration persistence pattern already established by
  `app/api/presets.py`/`presets.json` (same Principle I exemption already
  covers this — no new constitution work needed).
- **First-run experience** — a brief tour, or a "Load Sample Video" button,
  instead of a cold empty drop zone for a first-time user or evaluator.
- **Desktop notifications** (Windows toast) when a long detection or export
  finishes, so the user isn't stuck babysitting the Processing page.
- **Recent files** list on the Home page.

**Why**: this is the layer that separates "functional" from "feels finished
and professional" — none of these add new capability, but together they're
what makes an app feel like a polished, considered product rather than a
working prototype.

**Effort**: Low, per item. **Impact**: Medium, but cumulative and highly
visible — this is exactly the kind of polish a major tech company's app would
have by default.

---

## E. Trust & Robustness

- **GPU (CUDA) toggle for YOLO** — `ultralytics` already supports device
  selection; this is mostly exposing a setting plus detecting CUDA
  availability (extending `app/api/system.py`'s existing capability-check
  pattern), not new ML work.
- **Inline tooltips** explaining what Sensitivity/Padding/Min Event Duration
  actually do and trade off, reducing "why did it miss this event" confusion.

**Effort**: Low. **Impact**: Medium, mostly for power users / reducing
support burden.

---

## F. Video Intelligence Export — ✅ Shipped in Phase 6

Natural language "Video Intelligence Report" (Markdown + PDF) generated from any
completed detection run. Report includes: executive summary, activity statistics,
object inventory (YOLO), chronological timeline, key moments with thumbnails,
activity heatmap section, detection configuration, and a machine-readable JSON
data appendix structured for AI chatbot RAG context.

Optional Moondream2 local vision model (~2 GB, offline, `pip install moondream`)
adds visual descriptions to each event thumbnail in the timeline — graceful fallback
when not installed. Markdown output is structured for Phase 7's in-app AI chatbot.

All shipped in Phase 6.

**Remaining ideas in this space** (not yet implemented):
- Phase 7 shipped the LLM executive summary (Claude Haiku via `ANTHROPIC_API_KEY`)
  and replaced Moondream2 with Florence-2; see Section G below.
- In-app AI chatbot that loads the intelligence report Markdown as RAG context
  and lets the user ask natural language questions about the footage (Phase 8 target)
- Per-session Florence-2 / CLIP download progress indicator (currently downloads
  block silently on first run; a WebSocket progress stream would improve UX)

---

## G. UI/UX Overhaul + Enhanced AI Analysis — ✅ Shipped in Phase 7

**Branch:** `007-ui-ai-overhaul`

### What shipped
- **Florence-2-base** replaces BLIP — task-driven prompts, object detection, region captions
- **CLIP ViT-B/32** semantic frame indexing — `.clip.npy` sidecars for Phase 8 search
- **Claude Haiku API** optional executive summary (set `ANTHROPIC_API_KEY`)
- **Report format modal** — choose Markdown / PDF / both before generating
- **4-stage SSE progress** — live Thumbnails → AI Analysis → Writing → PDF bars
- **Scene Breakdown** in HTML preview — annotated thumbnails, bounding boxes, confidence bars
- **SVG Activity Timeline** — visual event density strip at top of report
- **Log panel polish** — timestamps, severity colours, Show/Hide toggle, Copy button
- **NarrativeSynthesizer** enriched: `temporal_analysis()`, `trend_direction()`, full captions

### Foundation laid
- CLIP embeddings enable Phase 8 semantic search ("find frames with a person")
- LLMSynthesizer pattern reusable for Phase 8 chatbot
- FrameAnalyzer detection data feeds Phase 8 video Q&A context

---

## Suggested Order

This is one reasonable sequence, not the only one — re-evaluate when any item
is actually picked up:

1. ~~**C (Professional Reporting)**~~ — **shipped in Phase 5**
2. ~~**F (Video Intelligence Export)**~~ — **shipped in Phase 6**
3. ~~**G (UI/UX Overhaul + Enhanced AI)**~~ — **shipped in Phase 7**
4. **D (Settings + first-run polish)** — same low-risk, high-perceived-value
   profile; natural to bundle 2-3 of these into one phase the way Phase 3
   bundled undo+presets+theme.
5. **B1 (face/plate blur)** — contained, high-impact, standalone; doesn't
   touch the job/session architecture.
6. **A (batch processing)** — deliberately last among the "foundational"
   items, because it deserves its own explicit conversation about the
   single-job-at-a-time tradeoff rather than being smuggled in as a side
   effect of something else.
7. **B2/B3 (semantic search, object tracking)** — the most exciting and the
   most speculative; CLIP embeddings from Phase 7 make B2 (semantic search)
   much closer — best explored once the more foundational items above are in
   place and there's a clearer sense of what users actually ask for next.
8. **B4, E** — low-effort items that can slot into whichever phase has spare
   capacity; no need to schedule them on their own.
