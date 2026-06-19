# Implementation Plan: Phase 2 — UI Redesign, Tag Filtering & Smart Export

**Branch**: `002-ui-tag-filter` | **Date**: 2026-06-19 | **Spec**: [specs/002-ui-tag-filter/spec.md](spec.md)
**Input**: Feature specification from `/specs/002-ui-tag-filter/spec.md`

---

## Summary

Phase 2 adds five user-facing feature groups on top of the working Phase 1 CCTV processor: (1) label-chip filtering + score threshold slider on the timeline, (2) multi-select with bulk include/exclude and single-level undo, (3) confidence badges + keyboard shortcuts, (4) smart export presets with optional FFmpeg burn-in overlay, and (5) a live detection label dashboard on the processing page.

The backend adds one new endpoint (`PUT /api/job/events/bulk`) and extends the export engine with the drawtext burn-in filter. The majority of work is frontend (vanilla JS/CSS). A shared ES module (`session-state.js`) holds ephemeral UI state (LabelFilter, ScoreThreshold, SelectionSet) so that filter choices survive SPA page navigation within the same session.

---

## Technical Context

**Language/Version**: Python 3.11+ (backend); Vanilla JS ES2022 modules (frontend — no build step)
**Primary Dependencies**: FastAPI, PyQt6+WebEngineView (Chromium), OpenCV, FFmpeg `drawtext` filter (bundled via imageio-ffmpeg)
**Storage**: N/A — UI state in JS module scope; job events remain in `app/session.py` in-memory dict
**Testing**: `pytest tests/ -v` (backend); manual smoke test per quickstart.md (frontend — no headless browser in this stack)
**Target Platform**: Windows 10/11 primary; Linux ARM64 (Raspberry Pi 5) secondary
**Project Type**: Desktop app — PyQt6 shell wrapping a FastAPI SPA served on localhost
**Performance Goals**: Filter + canvas re-render < 100ms for 300 events (SC-P2-007); SSE chart update within 3s of new event (SC-P2-005)
**Constraints**: No new Python packages; no npm/build step; no CDN resources (SPA must work offline); FFmpeg drawtext available in bundled binary
**Scale/Scope**: Single user, single job at a time; 1–500 events typical

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Session-First, No Persistence | ✅ COMPLIANT | UI filter state in JS module scope — no new server-side storage. Bulk toggle mutates `session.events[]` via lock-protected `session.update()` |
| II. Cross-Platform | ✅ COMPLIANT | Burn-in uses `get_ffmpeg()` from `ffmpeg_path.py`; drawtext uses FFmpeg default font (no hardcoded system path) |
| III. Test-First | ✅ COMPLIANT | Tests for `bulk_toggle`, `burn_in` export engine, and `label_filter` export written before implementation code |
| IV. Callback-Driven | ✅ COMPLIANT | Export engine receives `burn_in` as a parameter flag; still uses `on_progress` callback; does not access session directly |
| V. Simplicity & YAGNI | ✅ COMPLIANT | CSS `content-visibility` for virtual scroll (2 CSS lines vs 200 JS lines); no new libraries; single-level undo only |

---

## Project Structure

### Documentation (this feature)

```text
specs/002-ui-tag-filter/
├── plan.md              ← this file
├── research.md          ← Phase 0 output (7 decisions documented)
├── data-model.md        ← Phase 1 output (entities and field definitions)
├── quickstart.md        ← Phase 1 output (7 integration scenarios)
├── contracts/
│   └── api.md           ← Phase 1 output (new + extended endpoints)
└── tasks.md             ← Phase 2 output (created by /speckit-tasks)
```

### Source Code (files modified or created by Phase 2)

```text
BACKEND (Python):
app/
├── api/
│   └── job.py              MODIFY — add BulkToggleRequest model + PUT /api/job/events/bulk endpoint;
│                                     extend ExportRequest with burn_in: bool + label_filter: list[str]
├── core/
│   └── export_engine.py    MODIFY — add _build_burnin_filter() helper; apply -vf drawtext to
│                                     individual clip commands and merged export when burn_in=True;
│                                     apply label_filter to filter included events before export
└── session.py              MODIFY — add bulk_toggle_events(indices, include) method

FRONTEND (JavaScript, no build step):
static/js/
├── session-state.js        CREATE — singleton module: { labelFilter, scoreThreshold, selectionSet,
│                                     lastBulkOp }; export resetUiState()
├── pages/
│   ├── timeline.js         REWRITE — label filter bar, canvas grey-out, virtual scroll via CSS
│   │                                  containment, multi-select (Ctrl+click + checkbox), bulk toolbar,
│   │                                  confidence badges, label tag pills, keyboard nav (Arrow/Space/
│   │                                  Enter/Ctrl+A/Ctrl+D/Ctrl+E/Escape), undo (Ctrl+Z),
│   │                                  label summary chips in toolbar
│   ├── export.js           MODIFY — preset buttons (Security Report, Evidence Pack, Quick Highlights);
│   │                                 burn-in toggle; label filter scope selector; Quick Highlights
│   │                                 auto-select top-10 by score via bulk toggle API
│   ├── processing.js       MODIFY — live label breakdown CSS bar chart (driven by SSE); events/min
│   │                                 counter updated every 10s
│   └── home.js             MODIFY — call resetUiState() after POST /api/job/create succeeds

CSS:
static/css/
├── base.css                MODIFY — add CSS custom properties: --label-person, --label-car, --label-dog,
│                                     --label-cat, --label-bus, --label-bicycle, --label-default;
│                                     add .badge--green/amber/red token classes
├── timeline.css            MODIFY — add .filter-bar, .label-chip, .label-chip.active, .bulk-toolbar,
│                                     .event-card.selected (blue ring), .event-label (pill),
│                                     .confidence-badge (coloured pill),
│                                     .event-card { content-visibility: auto; contain-intrinsic-size: 0 90px }
├── export.css              MODIFY — add .preset-row, .preset-btn, .burn-in-toggle, .label-scope-select
└── processing.css          MODIFY — add .chart-wrap, .chart-bar, .chart-label, .eventsmin-counter

TESTS (Python):
tests/
├── test_session.py         MODIFY — add test_bulk_toggle_include, test_bulk_toggle_exclude,
│                                     test_bulk_toggle_invalid_index
├── test_api_job.py         MODIFY — add test_bulk_toggle_endpoint_success,
│                                     test_bulk_toggle_endpoint_empty_indices,
│                                     test_export_with_label_filter
└── test_export_engine.py   MODIFY — add test_burn_in_drawtext_in_cmd_individual,
│                                     test_burn_in_drawtext_in_cmd_merged,
│                                     test_label_filter_excludes_events,
│                                     test_no_burn_in_when_disabled
```

---

## Complexity Tracking

No constitution violations. No entries required.

---

## Implementation Notes for Task Generation

### session.py addition

```python
def bulk_toggle_events(indices: list, include: bool) -> None:
    """Set included=include for all events at the given indices atomically."""
    with _lock:
        for idx in indices:
            _state["events"][idx]["included"] = include
```

### export_engine.py burn-in addition

The `_build_burnin_filter(start_s, zone_label, recording_start)` helper returns a drawtext filter string:
- Uses `app.utils.time_utils.seconds_to_clock()` for wall-clock time if `recording_start` is set
- Falls back to file-relative `HH:MM:SS` format using `divmod(int(start_s), 3600)` etc.
- Appended to existing video filter with `,` if other `-vf` flags exist (e.g., scale for 720p)

### session-state.js structure

```javascript
const _state = {
  labelFilter:     new Set(),   // active label strings
  scoreThreshold:  0.0,
  selectedIndices: new Set(),   // multi-select
  lastBulkOp:      null,        // { indices: [], prevIncluded: [] }
};
export const uiState = _state;
export function resetUiState() {
  _state.labelFilter     = new Set();
  _state.scoreThreshold  = 0.0;
  _state.selectedIndices = new Set();
  _state.lastBulkOp      = null;
}
```

### timeline.js virtual scroll

Add to each `.event-card` in CSS:
```css
.event-card {
  content-visibility: auto;
  contain-intrinsic-size: 0 90px;
}
```
No JS changes needed. Browser handles off-screen skip automatically.

### Keyboard navigation in timeline.js

Maintain a `focusedIdx` variable (null = no card focused). On `keydown` on the events-list container:
- `ArrowDown`/`ArrowUp`: `focusedIdx ±= 1` (clamp to visible events); scroll card into view; add `.focused` CSS class
- `Space`: toggle the focused event (call `/api/job/events/{focusedIdx}/toggle` PUT)
- `Enter`: open preview modal for focused event
- `Ctrl+A`: select all visible events; update selectionSet
- `Ctrl+D`: clear selectionSet
- `Ctrl+E`: `window.go('/export')`
- `Escape`: clear selectionSet; remove bulk toolbar

### SSE chart in processing.js

The existing SSE endpoint (`/api/stream`) emits lines like `data: {"type":"event","event":{...}}` when new events are found. The processing page already listens to this stream. Add a listener for `type === "event"` messages: extract `event.zone_label`, increment `labelCounts[label]`, update CSS bar widths.

Events/min: every 10s, compute `totalEvents / ((Date.now() - startTime) / 60000)`.
