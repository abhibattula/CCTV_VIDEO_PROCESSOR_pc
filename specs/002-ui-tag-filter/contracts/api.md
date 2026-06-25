# API Contracts: Phase 2 — UI Redesign, Tag Filtering & Smart Export

**Date**: 2026-06-19
**Branch**: `002-ui-tag-filter`

All Phase 1 endpoints are preserved unchanged. Phase 2 adds one new endpoint and extends one existing endpoint.

---

## New Endpoint: Bulk Event Toggle

### `PUT /api/job/events/bulk`

Sets the `included` flag for multiple events in a single request.

**Request body**:
```json
{
  "indices": [0, 2, 5, 11],
  "include": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `indices` | number[] | yes | Array of event indices to update (0-based) |
| `include` | boolean | yes | The `included` value to set on all specified events |

**Validation**:
- `indices` must be non-empty; returns `400` if empty array
- Each index must be valid (0 ≤ idx < len(events)); returns `404` if any index is out of range
- Job must not be in `idle` or `detecting` status; returns `400` otherwise

**Response 200**:
```json
{
  "updated": 4,
  "events": [ ... ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `updated` | number | Count of events whose `included` flag was changed |
| `events` | object[] | Full updated events array (same shape as GET /api/job/events) |

**Response 400** (empty indices):
```json
{ "detail": "indices must be non-empty" }
```

**Response 404** (index out of range):
```json
{ "detail": "Event index 99 not found" }
```

---

## Extended Endpoint: Export Job

### `POST /api/job/export` (extended)

Phase 1 signature is preserved. Phase 2 adds two optional fields.

**Request body (Phase 1 fields unchanged)**:
```json
{
  "output_type": "merged",
  "quality": "original",
  "output_dir": null,
  "burn_in": false,
  "label_filter": []
}
```

**New fields**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `burn_in` | boolean | `false` | If true, render timestamp + label watermark via FFmpeg drawtext on each clip |
| `label_filter` | string[] | `[]` | If non-empty, only export events whose `zone_label` is in this list; empty = include all |

**Burn-in text format**:
- With `recording_start`: `"HH:MM:SS • <label>"` (wall clock + label)
- Without `recording_start`: `"HH:MM:SS • <label>"` (file-relative time)
- No zone_label (MOG2 event): `"HH:MM:SS"` (no bullet or label)

**Burn-in FFmpeg filter string** (applied via `-vf`):
```
drawtext=text='<text>':fontsize=18:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=4:x=10:y=(h-th-10)
```

**label_filter interaction with existing `included` flag**:
- Only events where `included=true` AND `zone_label ∈ label_filter` (or label_filter is empty) are exported
- If label_filter results in zero events, return `400: "No events match the label filter"`

**Response**: Unchanged from Phase 1 — returns `{ "status": "exporting" }` immediately; poll `/api/job` for `status == "export_done"`.

---

## Unchanged Phase 1 Endpoints (reference)

These are NOT modified by Phase 2:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/job/create` | Create new job from source file path |
| GET | `/api/job` | Get full session snapshot |
| POST | `/api/job/start` | Begin detection run |
| POST | `/api/job/cancel` | Cancel active detection |
| GET | `/api/job/events` | Get all events array |
| PUT | `/api/job/events/{idx}/toggle` | Toggle single event included flag |
| POST | `/api/job/preview/{idx}` | Generate preview clip for event |
| GET | `/api/preview/{token}.mp4` | Serve preview clip file |
| GET | `/api/stream` | SSE log + progress stream |
| GET | `/api/system/stats` | CPU/RAM/temperature stats |
| POST | `/api/shell/open-folder` | Open output folder in file manager |
| GET | `/api/shell/pending-path` | Get file picker result |
| POST | `/api/shell/set-output-dir` | Set session output directory |
| GET | `/api/health` | Backend health check |
