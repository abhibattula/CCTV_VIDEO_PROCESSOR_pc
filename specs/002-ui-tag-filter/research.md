# Research: Phase 2 — UI Redesign, Tag Filtering & Smart Export

**Date**: 2026-06-19
**Branch**: `002-ui-tag-filter`

---

## Decision 1: Virtual Scrolling Strategy

**Decision**: Use CSS `content-visibility: auto` with `contain-intrinsic-size` rather than a JS virtual list.

**Rationale**:
A true JS virtual list (render only visible DOM nodes) requires calculating item heights, scroll position, and a spacer element — around 150–200 lines of careful code that's hard to test and breaks keyboard navigation and focus management. CSS `content-visibility: auto` achieves the same browser-level optimization (skips layout and paint for off-screen elements) with a two-line CSS rule. Chrome and Edge (which Chromium/QWebEngineView uses) support it fully since version 85. For 300–500 event cards of uniform height (≈80px), the performance is indistinguishable from a JS virtual list at the scale this app needs.

**Alternatives considered**:
- *IntersectionObserver virtual list*: More control, but adds ≈200 lines and breaks aria-roving-tabindex keyboard nav.
- *Pagination (50 per page)*: Spec explicitly chose virtual scroll (US2 clarification). Pagination is rejected.
- *clusterize.js (3rd party)*: Adds a dependency, requires a build step; doesn't fit the no-npm constraint.

---

## Decision 2: Shared UI State (LabelFilter / ScoreThreshold Persistence)

**Decision**: Create `static/js/session-state.js` as a singleton ES module holding the shared UI state object. Import it in `timeline.js`, `export.js`, and `app.js`.

**Rationale**:
ES module instances are singletons within a browser page load — the same object reference is returned on every `import`. Since the SPA never reloads the page (it uses `history.pushState`), module-level state in `session-state.js` persists across all page navigations (timeline → export → timeline) within the same session. This exactly matches the spec requirement: "persists across page navigation within the same session; resets only when a new job is loaded."

The reset hook: `home.js` already makes a `POST /api/job/create` call to start a new job. After that call succeeds, `home.js` calls `import('./session-state.js').then(m => m.resetUiState())` to clear filter state.

**Alternatives considered**:
- *URL query params*: Exposes filter state in address bar; requires URL encoding; breaks back button.
- *localStorage*: Persists across sessions; spec says ephemeral within-session only.
- *Python session dict*: Would require new API calls on every filter change; adds latency and complexity.

---

## Decision 3: Burn-In Font on Windows

**Decision**: Use FFmpeg's built-in glyph renderer with no explicit `fontfile` parameter. Fall back gracefully: if `drawtext` filter is unavailable (FFmpeg compiled without freetype), log a warning and skip burn-in without failing the export.

**Rationale**:
The `imageio-ffmpeg` bundled binary (used on Windows) is compiled with `--enable-libfreetype` and includes fallback glyph rendering. Testing confirmed that `drawtext=text='Hello':fontsize=18:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=4:x=10:y=(h-th-10)` renders correctly on Windows with the bundled binary using its built-in sans-serif fallback. No font file needed to be bundled.

On Raspberry Pi 5 (system FFmpeg from apt), the same `drawtext` filter works with the system's DejaVu fonts installed as part of `ffmpeg`'s recommended dependencies.

**Alternatives considered**:
- *Bundle a .ttf file in the app*: Adds ~400KB, raises font licensing questions, overkill.
- *Use `subtitles` filter*: Requires creating an .srt file; more complex than drawtext.
- *PIL/Pillow overlay*: Would require re-encoding every frame through Python; 100× slower than FFmpeg's native drawtext.

---

## Decision 4: Bulk Toggle API Design

**Decision**: Add `PUT /api/job/events/bulk` with body `{ "indices": [0, 2, 5], "include": true }`. Returns `{ "updated": 3 }`.

**Rationale**:
The existing `PUT /api/job/events/{idx}/toggle` makes one HTTP request per card. For a 50-card multi-select bulk operation, that's 50 serial requests × ≈5ms each = 250ms minimum with HOL blocking. A single bulk endpoint processes the same operation in one session lock acquisition, one dict update, and one HTTP round-trip. The implementation is 12 lines in `session.py` + 15 lines in `job.py`.

**Alternatives considered**:
- *N sequential toggle calls from JS*: Works but is slow and causes visual flicker as each card updates one-by-one.
- *WebSocket for bulk ops*: Overkill for a single-user desktop app.
- *PUT /api/job/events with full replacement*: Too broad; sends entire events array over the wire.

---

## Decision 5: Single-Level Undo Implementation

**Decision**: Store a single undo record in `session-state.js` as `undoStack.lastBulkOp = { indices: [...], prevIncluded: [...] }`. Ctrl+Z replays the reverse operation via the bulk toggle API.

**Rationale**:
The spec explicitly requires single-level undo only. A simple object (not an array stack) with `lastBulkOp` captures exactly the last bulk operation. Ctrl+Z calls `PUT /api/job/events/bulk` with the reversed state. If no bulk op was performed, the undo button is greyed out. This is 25 lines of JS.

**Alternatives considered**:
- *Command pattern with history array*: Correct design for multi-level undo but out of scope per spec (Phase 3).
- *Server-side undo*: Would require storing event state history in session.py; violates YAGNI.

---

## Decision 6: Live Detection Chart

**Decision**: Render the live label breakdown chart as CSS flex bars — no canvas, no SVG library. Each label gets a `<div class="chart-bar">` whose `width` is set inline as `%` of the max count.

**Rationale**:
The chart shows 5–10 labels with integer counts that update on each SSE event. CSS flex bars update with a single `style.width` assignment per bar and animate smoothly with `transition: width 0.3s ease`. No canvas size calculations, no coordinate math, no library import. The existing SSE stream (`/api/stream`) already emits event data on each detection; the processing page just needs to accumulate counts from the SSE messages and re-render the bar widths.

**Alternatives considered**:
- *Canvas bar chart*: Requires requestAnimationFrame, coordinate calculation, colour fills. 3× more code.
- *Chart.js or similar*: External dependency, CDN or bundled, no-CDN constraint violated.
- *SVG bars*: More semantic but equivalent complexity to CSS flex; no benefit here.

---

## Decision 7: Quick Highlights Preset (Top-10 Selection)

**Decision**: Implement entirely client-side: sort events array by `peak_motion_score` descending, take the top 10 indices, then call `PUT /api/job/events/bulk` with `{ indices: top10indices, include: true }` followed by `{ indices: remaining, include: false }`.

**Rationale**:
The events array is already in the JS client's memory (fetched on timeline load). Sorting 500 events in JS takes < 1ms. Two bulk API calls update the server state. This avoids adding server-side sort logic and keeps the preset entirely in the export page's JS.

**Alternatives considered**:
- *Server-side `/api/job/events/top-n` endpoint*: More API surface, no benefit since client already has the data.
- *Mark top-10 during detection*: Would require post-processing sort step in detection engine; out of scope.
