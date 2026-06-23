# Data Model: ROI Selection, Stop Application, New Project

## DetectionRegion (frontend-only; serialized into the existing `zones` field)

A single user-drawn polygon restricting where detection looks for activity.
Never persisted — exists only in `static/js/roi.js`'s in-memory state for the
lifetime of the currently-loaded video, and is discarded the moment a
different file is loaded (FR-P4-005).

| Field | Type | Notes |
|---|---|---|
| `id` | string (UUID) | Frontend-only, for list rendering/deletion; never sent to the backend |
| `label` | string | User-editable, defaults to `"Region 1"`, `"Region 2"`, ... |
| `points` | `{x: number, y: number}[]` | Normalized `[0,1]` coordinates, ≥3 points, in the order drawn |

**Wire shape sent to the backend** (inside `POST /api/job/start`'s existing
`zones` field, replacing today's hardcoded `[]`):

```json
{ "zones": [ { "label": "Region 1", "points": [[0.12, 0.30], [0.45, 0.28], [0.40, 0.61]] } ] }
```

This is **exactly** the shape `app/core/detection_engine.py:37-49`'s
`_build_zone_mask()` already expects (`zone.get("points", [])`, normalized
`[0,1]` floats, `[x,y]` pairs) — `label` is carried through but unused by the
mask builder, kept only for the frontend's own region-list UI.

**Validation rule**: A region needs ≥3 points to be closeable into a shape
(enforced client-side at draw time, per FR-P4-002's "closed" requirement); the
backend places no additional constraint on `zones` beyond what already exists
today (an empty list is valid and means "analyze the full frame").

**Lifecycle**: created → (optionally re-labeled) → either included in the next
`job/start` call, deleted individually, or wiped entirely by "Clear All" /
loading a new file. No state transitions beyond "exists" / "doesn't exist" —
there's no draft/saved distinction since regions are never persisted
(Assumptions: per-job only).

## ApplicationRunState (observed, not stored)

Not a data entity with fields — a behavioral state the Stop Application
feature observes via the existing `GET /api/health` endpoint, not a new
session field. Two states:

| State | Observed via |
|---|---|
| Running | `GET /api/health` succeeds (`{"status": "ok"}`) |
| Stopped | `GET /api/health` fails at the network level (connection refused) |

No new backend field is introduced to track this explicitly — uvicorn's own
process lifecycle (via `Server.should_exit`) is the single source of truth,
and the frontend infers state purely by whether health-check requests
succeed or fail.

## No changes to existing entities

- **MotionEvent**, **SourceInfo**, session `_DEFAULTS` (`app/session.py`):
  unchanged. `zones` already exists inside the `settings` dict stored at
  `app/session.py`'s `"settings"` key (set via `session.update(settings=...)`
  in `job.py:126`) — this feature populates a field that was always part of
  the schema, not adding a new one.
- **ExportPreset (custom)** (Phase 3): unchanged — explicitly out of scope
  per this feature's Assumptions (regions are not saved/reusable, so they
  never become preset fields).
