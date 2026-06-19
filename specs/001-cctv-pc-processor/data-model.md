# Data Model: CCTV Video Processor PC

**Branch**: `001-cctv-pc-processor` | **Date**: 2026-06-19

All entities live in the in-memory session dict (`app/session.py`). There is no
database. State is discarded when the app exits.

---

## Session (root object)

The single top-level object. One instance per app launch, one job at a time.

```python
SESSION = {
    # Identity
    "job_id":        str,           # uuid4 — new on each reset()

    # Lifecycle
    "status":        str,           # See: Status enum below
    "error":         str | None,    # Human-readable error message when status == "failed"

    # Source video
    "source_path":   str | None,    # Absolute path (str for JSON-safe snapshot)
    "source_info":   SourceInfo,    # See below; empty dict when no file loaded

    # Detection settings (set by /api/job/start)
    "settings":      DetectionSettings,

    # Detection progress
    "progress":      float,         # 0.0 → 1.0
    "events":        list[MotionEvent],

    # Export
    "output_path":   str | None,    # Absolute path to completed output file
    "output_dir":    str,           # User-chosen destination; default: Desktop

    # Internal — not exposed in snapshot to web UI
    "_cancel_event": threading.Event | None,
    "pending_path":  str | None,    # Pending file path from shell bridge
}
```

### Status Enum

| Value | Meaning |
|-------|---------|
| `idle` | No file loaded; app just launched or reset |
| `ready` | File loaded and validated; awaiting Start |
| `detecting` | Background detection thread running |
| `completed` | Detection finished; events available |
| `exporting` | Export thread running |
| `failed` | Detection or export raised an unhandled exception |
| `cancelled` | User cancelled a detection run |

**Transitions**:
```
idle → ready          (POST /api/job/create succeeds)
ready → detecting     (POST /api/job/start)
detecting → completed (detection thread exits normally)
detecting → cancelled (cancel_event set + thread exits)
detecting → failed    (unhandled exception in thread)
completed → exporting (POST /api/job/export)
cancelled → exporting (POST /api/job/export — partial results)
exporting → completed (export thread exits normally; output_path set)
exporting → failed    (FFmpeg error)
any → ready           (POST /api/job/create with new file, after user confirms discard)
```

---

## SourceInfo

Populated by `app/utils/ffprobe.py` when a file is loaded.

```python
SourceInfo = {
    "codec":        str,    # e.g. "h264", "hevc", "mjpeg"
    "fps":          float,  # frames per second (avg_frame_rate, not r_frame_rate)
    "width":        int,    # pixels
    "height":       int,    # pixels
    "duration_s":   float,  # total duration in seconds
    "has_audio":    bool,
    "audio_codec":  str,    # e.g. "aac", "mp3", "pcm_alaw", "" when no audio
    "needs_reencode": bool, # True when codec not in STREAM_COPY_SAFE set
}
```

**Validation rules**:
- `duration_s > 0` — zero-duration files are rejected at create time; ffprobe falls back to estimating from file size and bit_rate for MJPEG AVI files without a proper duration atom
- `width > 0` and `height > 0` — file must be readable by ffprobe
- `fps > 0` — must have a valid frame rate

---

## DetectionSettings

Set by the caller of `POST /api/job/start`. Passed to the engine as a plain dict.

```python
DetectionSettings = {
    "mode":             str,    # "mog2" | "yolo"
    "sensitivity":      str,    # "low" | "medium" | "high"
    "frame_skip":       int,    # 0 = every frame; 1 = every other; 2 = every 3rd
    "padding_s":        float,  # seconds to include before/after each event boundary
    "min_gap_s":        float,  # silence gap required to close an open event
    "min_event_s":      float,  # minimum event duration to be recorded
    "zones":            list,   # [] = full frame; future: list of {x, y, w, h} ROI dicts
    "recording_start":  str | None, # "HH:MM:SS" wall-clock start, or null
}
```

**Defaults** (applied in `POST /api/job/start` if not provided):

| Field | Default |
|-------|---------|
| mode | "mog2" |
| sensitivity | "medium" |
| frame_skip | 1 |
| padding_s | 2.0 |
| min_gap_s | 2.0 |
| min_event_s | 2.0 |
| zones | [] |
| recording_start | null |

---

## MotionEvent

One entry per detected activity period, appended to `SESSION["events"]` via
`session.append_event()` as detection progresses.

```python
MotionEvent = {
    # Timing (file-relative)
    "start_s":      float,      # seconds from start of source video
    "end_s":        float,      # seconds from start of source video

    # Wall-clock times (populated when recording_start is set, else null)
    "start_clock":  str | None, # e.g. "02:47:33" (HH:MM:SS)
    "end_clock":    str | None, # e.g. "02:48:15"

    # Quality
    "peak_score":   float,      # 0.0–1.0; peak motion intensity across the event
    "label":        str | None, # "Person" | "Vehicle" | "Animal" | null (MOG2 always null)

    # User curation
    "included":     bool,       # True = include in export; toggleable via PUT /api/job/events/{idx}/toggle
}
```

**Invariants**:
- `end_s > start_s`
- `end_s - start_s >= min_event_s`
- Events are appended in chronological order (detection is sequential)
- `included` defaults to `True` on creation

---

## Export

Not a stored entity — computed on demand by `POST /api/job/export`. Input:

```python
ExportRequest = {
    "output_type":  str,        # "merged" | "individual"
    "quality":      str,        # "original" | "720p" | "480p"
    "output_dir":   str | None, # absolute path; falls back to SESSION["output_dir"]
}
```

Output written to `SESSION["output_path"]` on success.

**Filename conventions**:

| output_type | Pattern |
|-------------|---------|
| merged | `{source_stem}_activity_{YYYYMMDD_HHMMSS}.mp4` |
| individual | `{source_stem}_event_{N:03d}_{wall_clock_or_offset}.mp4` |

Wall-clock suffix used in individual clip names when `recording_start` is set;
file-relative offset (`HH-MM-SS`) used otherwise.

---

## Write-in-Progress Sentinel

Crash-recovery mechanism (FR-016). On export start, the sentinel is written to
the **known JOBS_DIR location** (not next to the output file) so the app can find
it on relaunch without knowing the previous session's output directory:

```python
sentinel_path = job_dir / "export.writing"   # job_dir = JOBS_DIR / job_id
sentinel_path.write_text(str(output_path))   # contains the output file path
```

On successful export completion:

```python
sentinel_path.unlink(missing_ok=True)
```

On app launch (`app/main.py` lifespan), scan `JOBS_DIR` for any `*.writing`
sentinel files. For each found: read the output file path from its contents,
delete the partial output file at that path if it exists, then delete the
sentinel. This guarantees the scan location is always known regardless of
where the user chose to save the output.

---

## Preview Clip

Ephemeral — not part of session state.

```python
PreviewClip = {
    "token":    str,   # 16-char hex string; used in URL /api/preview/{token}.mp4
    "path":     Path,  # PREVIEW_DIR / f"{token}.mp4"
    "event_idx": int,  # which MotionEvent this clip corresponds to
}
```

Lifecycle: created by `POST /api/job/preview/{idx}`, served by `GET /api/preview/{token}.mp4`,
deleted by background timer after 5 min or on app close (FR-018).
