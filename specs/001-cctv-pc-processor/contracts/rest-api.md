# REST API Contract

**Service**: CCTV Processor Backend (FastAPI, localhost:5151)
**Version**: 1.0 | **Date**: 2026-06-19

All endpoints return `application/json` unless noted. Errors return
`{"detail": "<human-readable message>"}` with appropriate HTTP status.

---

## Health

### GET /api/health
Returns `200 {"status": "ok"}`. Used by PyQt6 shell to confirm backend is ready before
loading the web UI.

---

## Job Lifecycle

### POST /api/job/create
Load and validate a video file. Creates a new session job.

**Request body**:
```json
{ "source_path": "/abs/path/to/video.mp4" }
```

**Response 200**:
```json
{
  "job_id": "uuid4-string",
  "status": "ready",
  "source_info": {
    "codec": "h264",
    "fps": 30.0,
    "width": 1920,
    "height": 1080,
    "duration_s": 3661.5,
    "has_audio": true,
    "needs_reencode": false
  },
  "warnings": ["Codec 'mjpeg' requires re-encoding — export will be slower."]
}
```

**Errors**:
- `400` — file not found, unreadable by ffprobe, or insufficient disk space

**Side effects**:
- Calls `session.reset()` first — any prior session is discarded
- Caller (web UI) is responsible for FR-017 confirmation before calling this endpoint

---

### GET /api/job
Return a deep copy of the current session state.

**Response 200**:
```json
{
  "job_id": "...",
  "status": "detecting",
  "source_path": "/abs/path/video.mp4",
  "source_info": { ... },
  "settings": { ... },
  "progress": 0.63,
  "events": [ ... ],
  "output_path": null,
  "output_dir": "/Users/user/Desktop",
  "error": null
}
```

---

### POST /api/job/start
Start background detection. Session must be in `ready`, `completed`, `failed`, or
`cancelled` status.

**Request body**:
```json
{
  "mode": "mog2",
  "sensitivity": "medium",
  "frame_skip": 1,
  "padding_s": 2.0,
  "min_gap_s": 2.0,
  "min_event_s": 2.0,
  "zones": [],
  "recording_start": "02:30:00"
}
```

All fields optional; defaults applied server-side (see data-model.md).

**Response 200**:
```json
{ "status": "detecting" }
```

**Errors**:
- `400` — session status does not permit starting (e.g. already detecting)

---

### POST /api/job/cancel
Set the cancel event. Detection thread stops at the next checkpoint.
Partial events are preserved in session state.

**Response 200**:
```json
{ "status": "cancelled" }
```

---

### GET /api/job/events
Return the current events list.

**Response 200**:
```json
[
  {
    "start_s": 45.2,
    "end_s": 52.8,
    "start_clock": "02:31:15",
    "end_clock": "02:31:22",
    "peak_score": 0.042,
    "label": null,
    "included": true
  }
]
```

---

### PUT /api/job/events/{idx}/toggle
Toggle the `included` flag for a single event by index.

**Response 200**: Returns the updated event object.

**Errors**:
- `404` — index out of range

---

### POST /api/job/export
Start background export of all included events.

**Request body**:
```json
{
  "output_type": "merged",
  "quality": "original",
  "output_dir": "/Users/user/Desktop"
}
```

**Response 200**:
```json
{ "status": "exporting" }
```

**Errors**:
- `400` — session not in `completed` or `cancelled` status
- `400` — no events with `included: true`

---

## Preview

### POST /api/job/preview/{idx}
Extract a short clip for the event at index `idx` and return its serving URL.

**Response 200**:
```json
{ "url": "/api/preview/a1b2c3d4e5f6.mp4", "token": "a1b2c3d4e5f6" }
```

**Errors**:
- `404` — event index out of range
- `500` — FFmpeg extraction failed

---

### GET /api/preview/{token}.mp4
Serve a preview clip by token. Token must be 16 hex characters (sanitised server-side).

**Response 200**: `video/mp4` binary stream

**Errors**:
- `400` — invalid token format
- `404` — clip expired or not yet created

---

## SSE Stream

### GET /api/stream
Server-Sent Events stream for live progress during detection and export.

**Response**: `text/event-stream`; each event is a JSON-encoded `data:` line.

**Message types**:

```json
{ "type": "log",       "line": "[MOG2] frame 900/27000", "progress": 0.033, "event_count": 0, "status": "detecting" }
{ "type": "log",       "line": "[EVENT] 00:01:23 → 00:01:31 (8s)", "progress": 0.05, "event_count": 1, "status": "detecting" }
{ "type": "done",      ... }
{ "type": "keepalive", ... }
```

Keepalive messages are sent every 30 seconds to prevent proxy timeouts.
A `done` message is sent when the background thread closes the log buffer.

---

## Shell Bridge

### POST /api/shell/filepath
Receive a file or folder path from the PyQt6 shell (after QFileDialog completes).

**Request body**:
```json
{ "path": "/abs/path/to/video.mp4" }
```

**Response 200**:
```json
{ "ok": true, "path": "/abs/path/to/video.mp4" }
```

---

### GET /api/shell/pending-path
Poll for a path posted by the shell. Returns and clears the pending path atomically.

**Response 200**:
```json
{ "path": "/abs/path/to/video.mp4" }
```
or `{ "path": null }` when nothing pending.

---

### POST /api/shell/open-folder
Ask the shell to open the output folder in the OS file manager.

**Response 200**: `{ "ok": true }` or `{ "ok": false }` if no output path set.

---

### POST /api/shell/set-output-dir
Update the session's default output directory.

**Request body**: `{ "path": "/abs/path/to/folder" }`

**Response 200**: `{ "ok": true, "output_dir": "/abs/path/to/folder" }`
