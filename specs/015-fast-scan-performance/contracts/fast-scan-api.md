# API Contract: Fast Scan

Two touched surfaces; everything else unchanged.

## 1. POST /api/job/start — new `scan_speed` field

Request body (`StartJobRequest`) gains:

```json
{
  "mode": "mog2",
  "sensitivity": "medium",
  "scan_speed": "balanced",      // NEW — "thorough" | "balanced" | "fast"
  "frame_skip": 1,               // legacy, honored only when scan_speed == "thorough"
  "padding_s": 2.0,
  "min_gap_s": 2.0,
  "min_event_s": 2.0,
  "zones": [],
  "recording_start": null
}
```

Rules:
- Omitted → `"balanced"` (default changes behavior vs v1.0.x deliberately; Thorough restores it).
- Invalid value → **422** (pydantic `Literal` validation) with a message naming the allowed values.
- `scan_speed` flows into `settings` (`req.model_dump()`) and therefore appears
  in `session.snapshot()["settings"]`, report configuration tables, etc.
- Applies to both `mode: "mog2"` and `mode: "yolo"`.
- Response body unchanged: `{"status": "detecting"}`.

## 2. GET /api/system/capabilities — extended response

```json
{
  "yolo_available": true,                          // existing, unchanged
  "ai_device": "cpu",                              // NEW — "cpu" or "cuda:0 — <name>"
  "decode_acceleration": {                         // NEW
    "methods_available": ["cuda", "vaapi", "dxva2", "qsv", "d3d11va", "d3d12va"],
    "selected": { "hevc": "qsv" }                  // codec → chain chosen by trial; {} before first sampled run
  }
}
```

Rules:
- `methods_available` from `ffmpeg -hwaccels` (cached at first call; `[]` if the
  query fails — endpoint never errors for this).
- `selected` reflects `frame_source`'s session cache; empty object until a
  sampled detection has run.
- `ai_device` from `app/utils/ai_device.describe_ai_device()`; `"cpu"` when
  torch is absent or CUDA unavailable.

## Log surface (informational, not a schema)

Sampled runs log which chain was selected
(`[FASTSCAN] decode: hevc via qsv, 5.0 fps @ 320×180`); fallbacks log the
reason. Normalization guard for >30 min inputs logs a warning with estimated
time/disk before re-encoding (FR-008). All via the existing SSE log buffer.
