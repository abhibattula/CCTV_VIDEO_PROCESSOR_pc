# Data Model: Fast Scan — Detection Performance Overhaul

No persistence anywhere (constitution I). Everything below is in-memory,
per-session state.

## Scan speed preset

Part of the job's `settings` dict (`session.snapshot()["settings"]`), set from
`StartJobRequest`:

| Field | Type | Values | Default |
|-------|------|--------|---------|
| `scan_speed` | str | `"thorough"` \| `"balanced"` \| `"fast"` | `"balanced"` |

Derived mapping (module constant in `frame_source.py` / `detection_engine.py`):

| Preset | sample_fps (source-time) | Engine path |
|--------|--------------------------|-------------|
| `thorough` | — (every frame) | Legacy cv2 loop, unmodified (honors legacy `frame_skip`) |
| `balanced` | `min(5.0, source_fps)` | FFmpeg frame_source |
| `fast` | `min(2.0, source_fps)` | FFmpeg frame_source |

MOG2 derived values in sampled modes (`effective_fps = sample_fps`):

| Sensitivity | HISTORY_SECONDS | history (frames) | varThreshold | motion threshold |
|-------------|-----------------|------------------|--------------|------------------|
| low | 28 | `int(28 × fps)` | 32 (unchanged) | 0.01 (unchanged) |
| medium | 20 | `int(20 × fps)` | 16 (unchanged) | 0.002 (unchanged) |
| high | 8 | `int(8 × fps)` | 8 (unchanged) | 0.0005 (unchanged) |

Warmup: `max(5, int(6 × effective_fps))` frames.

## FrameStream (frame_source.py, in-memory only)

Iterator/context-manager over an FFmpeg child process:

| Attribute | Type | Meaning |
|-----------|------|---------|
| `width`, `height` | int | exact frame dimensions delivered (engine-chosen: 320×180-class detect res for MOG2, 640×360 for YOLO) |
| `sample_fps` | float | CFR output rate; `pts_seconds = index / sample_fps` |
| `decoder` | str | chain that passed trial: `"qsv"` \| `"cuda"` \| `"software"` |
| yields | `(np.ndarray bgr24 h×w×3, float pts_seconds)` | one per sampled frame |

Lifecycle: `open → trial-selected → iterate → close()` (terminate→kill child;
idempotent; called on completion, error, and cancellation).

## Decode capability (module-level cache, read-only to API)

```
_selection_cache: {codec_name: "qsv" | "cuda" | "software"}   # per session
```

Exposed via `frame_source.get_acceleration_status()`:

| Field | Type | Meaning |
|-------|------|---------|
| `methods_available` | list[str] | from `ffmpeg -hwaccels` (cached once) |
| `selected` | dict[str, str] | codec → chain chosen by trial (empty until first sampled run) |

## AI device (app/utils/ai_device.py, cached)

| Function | Returns |
|----------|---------|
| `get_ai_device()` | `"cuda"` iff torch importable AND `torch.cuda.is_available()`, else `"cpu"`; cached; never raises |
| `describe_ai_device()` | human string: `"cpu"` or `"cuda:0 — <device name>"` |

## Event dict — unchanged

Sampled modes emit the exact existing event shape (`event_index`, `start_s`,
`end_s`, `start_clock`, `end_clock`, `peak_motion_score`, `zone_label`,
`included`); timestamps are source-time seconds derived from `pts_seconds`.
No downstream consumer (timeline, export, reports, search) changes.

## ffprobe SourceInfo — one additive field

| Field | Type | Meaning |
|-------|------|---------|
| `rotation` | int | degrees from displaymatrix side data (0 when absent/unparseable); non-zero forces the software chain (research D7) |
