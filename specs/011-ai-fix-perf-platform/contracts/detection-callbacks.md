# Contract: Detection Engine Callbacks

**Version**: unchanged from Phase 10 — this documents the existing contract for clarity.

## Callback Signatures (Constitution Principle IV)

```python
on_progress(pct: float) -> None
    # pct: 0.0–1.0 inclusive
    # Called: at least every BATCH_SIZE frames AND at least every 2.0 seconds (Phase 11 addition)
    # Final call: always on_progress(1.0) when detection completes normally

on_event(ev: dict) -> None
    # ev: {
    #   "event_index": int,        # 0-based, incrementing
    #   "start_s": float,          # clip-relative start (seconds)
    #   "end_s": float,            # clip-relative end (seconds)
    #   "peak_motion_score": float, # MOG2 or YOLO confidence
    #   "zone_label": str,         # zone name or YOLO class label
    #   "included": bool,          # True (user may toggle later)
    #   "start_clock": str | None, # wall-clock time if recording_start known
    #   "end_clock": str | None,
    # }
    # Called: once per confirmed detection event (after gap/duration checks pass)
```

## YOLO Warm-up API (new in Phase 11)

```python
# app/core/yolo_detector.prewarm() -> None
#   Call after POST /api/job/create succeeds and ultralytics is installed.
#   Idempotent: safe to call multiple times (subsequent calls are no-ops if
#   _model_ready is already set).
#   Non-blocking: returns immediately; model load happens in daemon thread.
#   Does NOT raise: any exception is caught and logged; _model_ready is set
#   regardless so run() never blocks indefinitely.

def prewarm() -> None: ...
```
