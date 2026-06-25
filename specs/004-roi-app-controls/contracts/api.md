# API Contracts: ROI Selection, Stop Application, New Project

## New: `GET /api/job/preview-frame`

Extracts and serves a single JPEG frame from the current job's source video,
for the ROI editor to draw over.

**Request**: No parameters — operates on the current session's `source_path`
and `job_id`.

**Response (200)**: `image/jpeg` body — the extracted frame, native resolution.

**Response (400)**: `{"error": "No active job"}` — no `source_path`/`job_id`
in the current session (e.g. called before any file is loaded).

**Response (500)**: `{"error": "Could not extract preview frame"}` or
`{"error": "Preview extraction failed: <details>"}` — ffmpeg failed or timed
out (corrupted file, zero-duration clip). The frontend MUST treat this as
"preview unavailable" (per the spec's edge case), not a fatal error — Start
Detection remains usable with `zones: []`.

**Caching**: Idempotent per job — the first call extracts and writes
`{job_dir}/preview_frame.jpg`; subsequent calls for the same job serve the
cached file directly without re-invoking ffmpeg. A fresh `job_id` (issued by
`job/create` on every new file load) guarantees no stale cross-job cache hits.

## Changed (behavior only — schema unchanged): `POST /api/job/start`

The existing `zones: list = []` field on `StartJobRequest` is now actually
populated by the frontend instead of always being `[]`. No schema change —
`zones` already existed; this is the first feature to write a non-empty value
into it. Shape: `[{ "label": str, "points": [[x: float, y: float], ...] }]`,
`x`/`y` normalized to `[0,1]`. Matches `data-model.md`'s `DetectionRegion` wire
shape exactly.

## Changed (behavior only): `POST /api/job/create`

Gains one line: `_cancel_event.set()` immediately before `session.reset()`.
No request/response schema change — this purely closes a race condition
where an in-flight detection thread from a previous job could write into a
freshly-reset session.

## No new endpoint for Stop Application

Triggering a stop is **not** an HTTP call — it's a JS-side bridge flag
(`window._cctvShutdown`) polled by `shell/main_window.py`'s existing
200ms timer, by design (keeps `app/` free of PyQt imports — see
`research.md` §5). The frontend's only HTTP calls in this flow are to
**already-existing** endpoints:

- `POST /api/job/cancel` (unchanged) — called first, to cancel any
  in-progress detection/export before the bridge flag is set.
- `GET /api/health` (unchanged) — polled afterward; a network-level failure
  (not a non-2xx response) is the signal that the backend has actually
  stopped.

## No new endpoint for New Project

`new-project.js` calls only already-existing endpoints:

- `GET /api/job` (unchanged) — to read current `status`/`events`/`output_path`
  and decide which warning (if any) to show.
- `POST /api/job/cancel` (unchanged) — called on confirm (or immediately, if
  no warning was needed), safe to call even when nothing is running.

No `POST /api/job/reset` is introduced — see `research.md` §6 for why this
would duplicate existing behavior.
