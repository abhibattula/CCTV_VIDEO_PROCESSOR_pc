# Research: Phase 8 — Report Fix + Quick Mode UI

**Date**: 2026-06-29 | **Branch**: `008-fix-report-quick-mode`

All decisions are derived from code-level exploration of the Phase 7 codebase (`007-ui-ai-overhaul`). No external research required — all unknowns were resolved by reading existing source files.

---

## Decision 1: Florence-2 Inference Timeout Value

**Decision**: Reduce `_TASK_TIMEOUT` from 300 s to 90 s; reduce `max_new_tokens` from 128 to 64.

**Rationale**: Florence-2 runs at ~2.8 s/token on this PC with `use_cache=False`. At 128 tokens, worst-case inference is 358 s — past the 300 s timeout. Real CCTV frames trigger EOS well before 64 tokens; synthetic all-black images are the worst case (~180 s at 64 tokens, well within 90 s × 2 safety margin). The 90 s timeout lets genuine CCTV frames succeed; it fails fast enough that the total report time stays under 9 min for 5 events rather than 75+ min.

**Alternatives Considered**:
- Reduce to 32 tokens: too aggressive, may truncate real descriptions mid-sentence.
- Keep 300 s timeout but reduce tokens only: timeout is the failure mode (300 s fires at frame 1 if the daemon thread runs 300 s); reducing tokens to 64 still takes ~180 s worst-case, which is within a 300 s limit — but the daemon thread for the first event would consume 300 s before timing out if something goes wrong, blocking the rest.
- Increase timeout to 600 s: makes total report time worse, not better.

---

## Decision 2: SSE socket.send() Exception Handling

**Decision**: Wrap the `yield` block (or equivalent `send()`) in `app/api/stream.py` with `try/except (asyncio.CancelledError, Exception)`. On `CancelledError`, re-raise (it's how asyncio signals graceful shutdown). On any other exception (e.g., `BrokenPipeError`, `ConnectionResetError`), log at DEBUG level and return, ending the generator.

**Rationale**: The `WARNING:asyncio:socket.send() raised exception` message comes from the SSE response generator trying to push bytes to a disconnected browser. FastAPI / Starlette's `StreamingResponse` (or `EventSourceResponse`) doesn't automatically suppress socket errors on client disconnect. A `try/except` around the `yield` is the correct, minimal fix. Re-raising `CancelledError` ensures the server can shut down cleanly.

**Alternatives Considered**:
- Catching only `BrokenPipeError`: too narrow; connection resets on Windows raise `ConnectionResetError`, not `BrokenPipeError`.
- Using `sse-starlette` library: existing code already works; adding a new dependency violates Principle V.

---

## Decision 3: Thumbnail Progress Fix

**Decision**: Remove the per-event progress loop that ran before `thumbnail_gen.run()`. After `thumbnail_gen.run()` completes, call `session.update(report_stage="thumbnails", report_stage_current=len(included), report_stage_total=len(included))` once.

**Rationale**: `thumbnail_gen.run()` is a synchronous blocking call that generates all thumbnails at once. The existing code incremented a counter in a tight loop **before** calling `run()`, so the SSE stream showed 100% thumbnails before any thumbnail existed. A single post-call update is simpler and honest. Per-event callbacks inside `thumbnail_gen.run()` were considered but would require modifying a shared utility; a single update is sufficient and simpler (Principle V).

**Alternatives Considered**:
- Per-event callback into thumbnail_gen: requires API changes to thumbnail_gen signature; overkill for a progress-only fix.
- Keeping the loop but moving it inside thumbnail_gen: same result as post-call update, more complex.

---

## Decision 4: Quick Report PDF Implementation

**Decision**: Add a "Quick Report (PDF)" button in `static/js/pages/export.js` that dispatches `document.dispatchEvent(new CustomEvent('cctv:save-report-pdf'))` — the exact same event the existing "Generate PDF Report" button already uses.

**Rationale**: The existing "Generate PDF Report" button fires `cctv:save-report-pdf` which the Qt shell intercepts to generate a motion-only PDF from `app/templates/report.html` (the Incident Report). This is exactly the "Quick Report" behavior needed. No new endpoint, no new Qt code. The existing button is in the "Reports & Data Export" section; the new button lives in the "Video Intelligence Report" section for proximity/contrast. Both buttons trigger identical behavior.

**Alternatives Considered**:
- New backend endpoint `GET /api/job/quick-report.html`: adds a new route, Jinja2 render call, and SSE flow — far more complex than reusing the existing Qt event.
- Navigating to `GET /api/job/report.html` in a new tab: opens the HTML in the browser rather than saving a PDF via Qt; not the desired user experience.

---

## Decision 5: intel_report.html img Tag Guard

**Decision**: Wrap the scene breakdown `<img>` tag in `{% if entry.annotated_thumb_b64 %}...{% endif %}`.

**Rationale**: `_annotate_thumbnail()` in `intel_report_renderer.py` returns `""` as a last-resort fallback when PIL is completely absent AND file reading fails. The template currently renders `<img src="data:image/jpeg;base64,">` unconditionally, which produces a broken image icon. A Jinja2 `{% if %}` guard is a one-line fix with no logic change.

**Alternatives Considered**:
- Fix in Python (never return ""): requires changing `_annotate_thumbnail()` to return `None` and updating every caller — more invasive than needed for an edge-case guard.
