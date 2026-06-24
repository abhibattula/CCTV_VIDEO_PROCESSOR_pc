# Phase 0 Research: Phase 5 — Professional Reporting & Activity Insights

All research below was completed during the upstream planning conversation
(three parallel codebase-exploration passes plus one Plan-agent design pass)
and independently spot-verified against the actual installed environment
before this spec/plan cycle began. No outstanding `NEEDS CLARIFICATION`
markers remain in `plan.md`'s Technical Context.

## Decision 1: PDF generation via Qt's bundled Chromium, not a new pip dependency

**Decision**: Render the report as a standalone HTML document server-side
(Jinja2), then convert it to PDF using `QWebEnginePage.printToPdf()` on a
hidden, offscreen page constructed in `shell/main_window.py` — no new pip
dependency.

**Rationale**: The app already ships `PyQt6-WebEngine` (a full Chromium
build) for its own UI. Independently confirmed against the installed
PyQt6-WebEngine 6.7.0 package (`python -c "from PyQt6.QtWebEngineCore import
QWebEnginePage; ..."`): `QWebEnginePage(profile, parent)` can be constructed
standalone with no attached visible view; `printToPdf(path)` and the
`pdfPrintingFinished(filePath, success)` completion signal both exist. This
satisfies the report's PDF requirement with zero new dependencies and
produces nicer, CSS-driven layouts than a manual table-drawing PDF library
would.

**Alternatives considered**:
- `reportlab` — pure Python, no system deps, but layout (thumbnail grids,
  tables) requires manual coordinate-based drawing code; more code for a
  worse-looking result than CSS.
- `weasyprint` — richer HTML→PDF, but depends on native Pango/Cairo/GTK
  libraries that are historically painful to bundle reliably on Windows —
  directly conflicts with this project's "pip install and go" promise.
- `xhtml2pdf` — pure Python, but weak CSS3 support (no flexbox/grid),
  constraining the report's visual design.

## Decision 2: Heatmap accumulation point — inside each engine's existing frame loop

**Decision**: Accumulate a per-pixel activity map as a local `np.ndarray`
inside `detection_engine.run()` (from the already-computed `fg_mask`, after
existing zone-masking) and `yolo_detector.run()` (from filled bounding-box
rectangles, since this engine has no foreground mask). Write the result to
`job_dir/heatmap.png` once, at the end of each function.

**Rationale**: Both engines already decode every frame of the video exactly
once during detection. Re-decoding the whole video a second time purely to
build a heatmap would double the processing time for no benefit — the signal
needed (where motion/objects occurred) is already being computed inline.
Confirmed directly against `detection_engine.py:320-325` that the existing
`fg_mask` is the right tap point, and that `_build_zone_mask()` (lines 37-49)
is the established precedent for "build once, apply per-frame" logic this
phase's accumulator follows. `yolo_detector.py` was confirmed to have no
foreground mask and no zone-mask support at all (a pre-existing Phase-4-era
gap, explicitly out of scope to fix here) — its accumulation strategy
(filled boxes) is necessarily different but produces the same output format.

**Alternatives considered**:
- A second, separate decode pass dedicated to heatmap generation — rejected
  for doubling per-job processing time with no accuracy benefit.
- Skipping YOLO-mode heatmap support entirely (MOG2-only) — considered and
  explicitly rejected after user input; a core feature silently not working
  in one of the app's two detection modes was judged worse than the modest
  extra implementation cost of a bbox-fill accumulation path.

## Decision 3: Thumbnail generation — wire in existing dead code, lazily

**Decision**: Call the already-written-but-never-invoked
`app/core/thumbnail_gen.run()` from inside the new report endpoint itself,
scoped only to the events that will actually appear in the report (the
`included` set), the first time a report is requested for a given job.

**Rationale**: `thumbnail_gen.py` already has exactly the right shape
(320×180 JPEG per event via the same `get_ffmpeg()` subprocess idiom used
everywhere else) but is dead code in the current PC version. Calling it
eagerly after every detection run would do wasted work for the (likely
majority of) jobs that are exported as video and never need a report.
Calling it lazily, scoped to `included` events only, means a job with many
excluded events doesn't pay for thumbnails that will never be shown. The
function is already idempotent (skips existing files), so repeated report
generation for the same job doesn't redundantly re-extract frames.

**Alternatives considered**:
- Eager generation right after detection completes — rejected as wasted
  work for jobs that never request a report, and for events later excluded
  on the Timeline page.
- A separate, user-triggered "build thumbnails" step before reporting —
  rejected as an unnecessary extra click; the existing `/job/preview-frame`
  "compute once, cache, serve" pattern already shows this can be transparent.

## Decision 4: Chain-of-custody hashing — chunked SHA-256, stdlib only

**Decision**: A small `_sha256_file(path, chunk_size=1MiB)` helper using
Python's stdlib `hashlib`, reading in fixed-size chunks rather than loading
an entire file into memory.

**Rationale**: Source CCTV recordings can be multi-gigabyte files; a naive
`hashlib.sha256(path.read_bytes())` would attempt to hold the entire file in
memory at once. No hashing code existed anywhere in this codebase prior to
this phase (confirmed via search) — this is new, simple, fully stdlib logic
with no new dependency.

**Alternatives considered**: None seriously — chunked reading is the
standard, only-reasonable approach for hashing files of unbounded size; no
faster non-cryptographic checksum was considered since the explicit
requirement (FR-P5-005) is a chain-of-custody-style integrity value, where
SHA-256 is the conventional choice.

## Decision 5: CSV/JSON export — two dedicated endpoints, pure backend

**Decision**: Two separate `POST` endpoints (`/job/export/csv`,
`/job/export/json`) rather than one endpoint with a `?format=` parameter;
both write directly into the user's already-selected `output_dir` from the
FastAPI process itself, with no Qt/shell involvement at all.

**Rationale**: This codebase's existing convention is consistently
single-purpose endpoints (e.g. `/job/events` vs `/job/events/bulk` vs
`/job/events/{idx}/toggle`, never one endpoint with internal format
branching). `output_dir` already flows into session state via the existing
shell-bridge folder-picker flow used by video export — no new file-dialog
plumbing is needed, since the FastAPI process already has full filesystem
write access (same as `export_engine.py` writing video files today).

**Alternatives considered**: A single `/job/export/log?format=csv|json`
endpoint — rejected as inconsistent with the established per-purpose
endpoint convention, and as introducing internal branching where this
codebase consistently prefers two small, independently testable handlers.

## Decision 6: No new dependency for Jinja2 — pin the existing transitive version

**Decision**: Add `Jinja2==3.1.6` to `requirements.txt` explicitly.

**Rationale**: Confirmed already installed transitively (pulled in by
Starlette 0.37.2, which the pinned `fastapi==0.111.0` requires) and is the
latest 3.1.x release as of this writing. Pinning it explicitly is a
same-version pin, not an upgrade — zero compatibility risk — and follows
this project's existing practice of pinning every dependency explicitly
rather than relying on transitive resolution.

**Alternatives considered**: Relying on the transitive dependency without
an explicit pin — rejected as fragile; if FastAPI/Starlette's own dependency
constraints ever loosen or change, an explicit pin is what keeps this
feature's templating behavior stable.
