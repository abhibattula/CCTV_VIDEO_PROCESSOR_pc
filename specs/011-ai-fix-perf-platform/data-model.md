# Data Model: Phase 11

**Branch**: `011-ai-fix-perf-platform` | **Date**: 2026-06-30

This phase introduces no new persistent data entities. The changes below describe modified entity behaviour and new in-process state.

---

## Modified Entities

### FrameAnalyzer (in-process singleton)

| Field | Before | After | Notes |
|-------|--------|-------|-------|
| `_availability_cache` | Set after transformers import check | Set to `False` immediately if `AI_FEATURES_ENABLED=False` | Short-circuits; no import attempted |
| `caption` return value | May contain `</s>`, `<s>`, `<loc_NNN>` | Always clean English text or `""` | Sanitised by `_clean_caption()` |
| `object_caption` return | May contain raw tokens | Always clean or `""` | Sanitised |
| `detections[].label` | May contain raw tokens | Always clean label string | Sanitised |
| Image passed to model | May be padded to square | Always original aspect ratio | Squaring code removed |
| `max_new_tokens` | 64 | 100 | Prevents mid-token truncation |

### YOLO Detector (module-level state, new)

| Field | Type | Description |
|-------|------|-------------|
| `_model_ready` | `threading.Event` | Set when warm-up thread completes (success or failure) |
| `_cached_yolo_model` | `YOLO \| None` | Pre-loaded model reference; `None` if warm-up failed |

**State transitions**:
```
[app start]            → _model_ready: unset, _cached_yolo_model: None
[job/create]           → prewarm() daemon thread starts
[warm-up success]      → _cached_yolo_model set, _model_ready.set()
[warm-up failure]      → _cached_yolo_model: None, _model_ready.set()
[run() called]         → waits up to 60s on _model_ready; uses cached or loads cold
[job/create again]     → _model_ready reset, new prewarm() starts
```

### LogBuffer (in-process, unchanged behaviour, corrected understanding)

`LogBuffer.subscribe()` already replays the last 100 log lines from `self._history[job_id]` into the subscriber queue on connection. No structural change. The SSE fix is entirely frontend-side (reconnect wrapper instead of fallback to polling).

### Config (module-level constants, new/changed)

| Constant | Before | After |
|----------|--------|-------|
| `BATCH_SIZE` | `500` | `100 if IS_PI else 500` |
| `YOLO_FRAME_SKIP` | (absent) | `6 if IS_PI else 3` |
| `AI_FEATURES_ENABLED` | (absent) | `_total_gb >= 5.0` |

### Desktop Path (new utility)

`app/utils/platform.py` — pure function, no state.

| Platform | Resolution order |
|----------|-----------------|
| Windows | `SHGetFolderPathW` → `~/Desktop` |
| macOS | `~/Desktop` |
| Linux/Pi | `$XDG_DESKTOP_DIR` → `~/Desktop` → `~/Downloads` → `~/` |
