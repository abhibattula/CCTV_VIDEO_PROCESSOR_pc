# Data Model: Phase 2 — UI Redesign, Tag Filtering & Smart Export

**Date**: 2026-06-19
**Branch**: `002-ui-tag-filter`

---

## Existing Entities (unchanged)

### MotionEvent (dict in `session.events[]`)

Already defined in Phase 1. Phase 2 reads but does not modify its schema.

| Field | Type | Description |
|-------|------|-------------|
| `start_s` | float | Event start time in seconds from video start |
| `end_s` | float | Event end time in seconds from video start |
| `peak_motion_score` | float | 0.0–1.0; detection confidence score |
| `zone_label` | str \| null | YOLO object label ("Person", "Car", etc.); null for MOG2 events |
| `included` | bool | Whether the event is selected for export; default true |
| `start_clock` | str \| null | Wall-clock timestamp if recording_start was set, e.g. "08:35:12" |
| `end_clock` | str \| null | Wall-clock timestamp if recording_start was set |

**Phase 2 note**: `zone_label` is the source of truth for label filtering. MOG2 events have `zone_label = null`.

---

## New Entities (Phase 2)

### LabelFilter (JS module state in `session-state.js`)

Ephemeral UI state persisting within the browser session. Not sent to the server.

| Field | Type | Description |
|-------|------|-------------|
| `activeLabels` | Set\<string\> | Set of label strings currently active as filters; empty = show all |
| `scoreThreshold` | float | 0.0–1.0; events below this are hidden; default 0.0 |

**Lifecycle**:
- Created as a module-level singleton on first import of `session-state.js`
- Persists across SPA navigation (timeline ↔ export ↔ home) until reset
- Reset by calling `resetUiState()` when a new job is created (in `home.js` after POST /api/job/create succeeds)

**Derived computed**:
- `visibleEvents` = events where `zone_label ∈ activeLabels` (or activeLabels is empty) AND `peak_motion_score >= scoreThreshold`

---

### SelectionSet (JS module state in `session-state.js`)

| Field | Type | Description |
|-------|------|-------------|
| `selectedIndices` | Set\<number\> | Set of event array indices the user has multi-selected |
| `lastBulkOp` | BulkOpRecord \| null | Record of the last bulk operation for single-level undo |

**BulkOpRecord sub-type**:

| Field | Type | Description |
|-------|------|-------------|
| `indices` | number[] | Indices affected by the last bulk operation |
| `prevIncluded` | boolean[] | Previous `included` state for each affected index (parallel array) |

**Lifecycle**:
- `selectedIndices` clears on: Escape key, click on empty event list area, navigation to another page
- `selectedIndices` does NOT clear on: navigating to export and back (filter state persists)
- `lastBulkOp` clears after a second bulk operation (only last op is stored)

---

### ExportPreset (constant in `export.js`)

Read-only in Phase 2. Three predefined presets:

| Name | `output_type` | `label_filter` | `quality` | `burn_in` | `auto_top_n` |
|------|---------------|----------------|-----------|-----------|--------------|
| Security Report | `merged` | `["Person"]` | `"original"` | `true` | null |
| Evidence Pack | `individual` | `[]` | `"original"` | `false` | null |
| Quick Highlights | `merged` | `[]` | `"720p"` | `false` | 10 |

**label_filter empty `[]`** means "all labels included" (no label scoping).

---

### BurnInOverlay (FFmpeg drawtext parameters, built in `export_engine.py`)

Not persisted — constructed at export time from export settings.

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | bool | Whether to apply the drawtext filter |
| `timestamp_text` | str | The timestamp portion: wall clock if available, else file-relative time |
| `label_text` | str \| null | The zone_label of the event; omitted if null/empty |
| `ffmpeg_filter_str` | str | The computed drawtext filter string passed to FFmpeg `-vf` |

**Computed filter string format**:
```
drawtext=text='HH:MM:SS • Person':fontsize=18:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=4:x=10:y=(h-th-10)
```
Or without label (MOG2 events):
```
drawtext=text='HH:MM:SS':fontsize=18:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=4:x=10:y=(h-th-10)
```

---

### Label Colour Mapping (constant in `base.css` and `timeline.js`)

Fixed in Phase 2. Used for label tag pills on event cards and canvas strip colours.

| Label | CSS variable | Hex |
|-------|-------------|-----|
| Person | `--label-person` | `#4f8ef7` (blue) |
| Car | `--label-car` | `#f7a24f` (orange) |
| Dog | `--label-dog` | `#4fd97a` (green) |
| Cat | `--label-cat` | `#a24ff7` (purple) |
| Bus | `--label-bus` | `#f74f4f` (red) |
| Bicycle | `--label-bicycle` | `#4fcff7` (teal) |
| (default) | `--label-default` | `#888888` (grey) |

---

### ConfidenceBadge (derived from MotionEvent.peak_motion_score)

Not a stored entity — computed at render time in `timeline.js`.

| Score range | CSS class | Colour |
|-------------|-----------|--------|
| ≥ 0.70 | `badge--green` | `#4fd97a` |
| 0.40–0.69 | `badge--amber` | `#f7c84f` |
| < 0.40 | `badge--red` | `#f74f4f` |

---

### LiveChart (ephemeral in `processing.js`)

Accumulated in-memory while processing page is mounted. Lost on navigation.

| Field | Type | Description |
|-------|------|-------------|
| `labelCounts` | Map\<string, number\> | Count of events per zone_label seen so far |
| `totalEvents` | number | Total events found so far |
| `startTime` | Date | When the current detection run started (for events/min calculation) |
| `eventsPerMin` | float | `totalEvents / ((Date.now() - startTime) / 60000)`; updated every 10s |
