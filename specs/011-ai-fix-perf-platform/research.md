# Research: Phase 11 — AI Fix, Performance & Cross-Platform

**Branch**: `011-ai-fix-perf-platform` | **Date**: 2026-06-30

---

## Decision 1 — LogBuffer replay implementation

**Decision**: No new `snapshot()` method needed in `LogBuffer`.

**Rationale**: `LogBuffer.subscribe()` (line 36-38, `app/core/log_buffer.py`) already replays the last 100 lines from `self._history[job_id]` into the new subscriber queue before entering the live stream. The root cause of the blank log panel is not a missing server-side replay — it is the frontend falling back to polling (`startPolling()`) instead of creating a new `EventSource`. On SSE error, `onerror` calls `evtSource.close()` and switches to polling, which provides job stats but zero log messages. Fix: change `onerror` to reconnect (create a new `EventSource`) with 3s backoff up to 5 retries. A new connection calls `subscribe()` again, which replays the last 100 entries. No server-side changes required.

**Alternatives considered**:
- Add `snapshot()` method returning all ring buffer entries: rejected — over-engineering; `subscribe()` already replays 100 entries which covers any reasonable disconnect window. The ring buffer holds 2000 entries (LOG_RING_SIZE); replaying all on every reconnect wastes bandwidth.
- Increase the 100-line replay cap in `subscribe()`: deferred — 100 lines covers ~2-3 minutes of typical detection logging. If a user reconnects after a longer absence, they see the most recent 100 lines which is sufficient context.

---

## Decision 2 — max_new_tokens ceiling

**Decision**: Raise `max_new_tokens` from 64 to **100** (not 150 as originally proposed).

**Rationale**: From the existing code comment: "real CCTV frames fire EOS ~20-45s". This means the model naturally terminates generation at the End-of-Sequence token in 20-45 seconds at `num_beams=1`. The 90s task timeout is a 2× safety margin. Raising the token ceiling does NOT meaningfully increase inference time because EOS fires first in almost all cases. The truncation bug happens when a >64-token generation is cut off: `post_process_generation` receives an incomplete token sequence and returns a partially-decoded string with raw fragments. At 100 tokens (≈75 words) the common caption pathologies are eliminated. Choosing 100 over 150 keeps a safety buffer against edge cases where the model generates unusually long sequences on high-content frames — 150 tokens at ~1 tok/s could push near the 90s timeout on very rare frames. 100 tokens ≈ 65 words is sufficient for a detailed CCTV caption.

**Alternatives considered**:
- 150 tokens: possible but marginal — 150 tokens at worst-case ~1 tok/s = 150s inference which could exceed the 90s timeout on edge-case high-content frames.
- 200 tokens: rejected — same risk at higher severity.
- Keep 64: rejected — confirmed root cause of truncation garbage.

---

## Decision 3 — Warning suppression in _run_task

**Decision**: Apply `warnings.catch_warnings()` + filters **inside `_run_task()`** (innermost function).

**Rationale**: `_run_task` is the inference function passed as a lambda to `_run_in_daemon`. The daemon thread runs in a separate thread where warnings filters still propagate (Python's `warnings` module uses per-thread state in `catch_warnings`). Applying the context manager inside `_run_task` is the most surgical approach: it only suppresses warnings during inference, not during other processing. The existing model-load suppression block (around `from_pretrained` calls) is left unchanged. Suppress: `UserWarning` from `torch` and `transformers` (attention mask, cache format warnings); `DeprecationWarning` from `numpy` and `PIL`. **Do not** suppress `RuntimeError` or `ValueError` — genuine inference failures must propagate to the `exc_box` in `_run_in_daemon`.

**Alternatives considered**:
- Wrap `_run_in_daemon` calls with the context manager in `_run_analysis`: rejected — `_run_in_daemon` spawns a daemon thread; the context manager in the calling thread would not apply to the daemon thread's warnings state.
- Global `warnings.filterwarnings` at module level: rejected — too broad, would suppress useful warnings across the entire process.

---

## Decision 4 — YOLO frame skip implementation

**Decision**: Add `YOLO_FRAME_SKIP` config constant and apply it in `yolo_detector.run()` only.

**Rationale**: `detection_engine.py` already has a `frame_skip` parameter (line 324: `if frame_skip > 0 and frame_idx % (frame_skip + 1) != 0`) passed in from `job.py`. YOLO detector does not have this — it processes every frame. Adding a module-level constant `YOLO_FRAME_SKIP = 6 if IS_PI else 3` in config.py and using it in `yolo_detector.run()` mirrors the existing MOG2 pattern. Frame indices are still tracked correctly (frame_idx increments for every frame read, regardless of whether YOLO processes it). The event timing is based on `t_s = frame_idx / fps` which remains correct even with skipped frames — an object present in one frame is almost certainly present in adjacent frames.

**Alternatives considered**:
- Make YOLO frame skip a per-job setting like MOG2: deferred — would require UI changes, which are out of scope for this stabilization phase.
- Use `frame_skip + 1` divisor style (same as MOG2): rejected for YOLO — MOG2's `frame_skip` starts at 1 (skip=1 → every 2nd). For YOLO we use `frame_index % YOLO_FRAME_SKIP == 0` (skip=3 → every 3rd frame, not every 4th) — simpler and more predictable for the user.

---

## Decision 5 — YOLO warm-up module design

**Decision**: Module-level `_model_ready: threading.Event` + `_cached_yolo_model` in `yolo_detector.py`. A `prewarm()` function (called from `job.py` after `/api/job/create`) loads the model in a daemon thread and stores it in `_cached_yolo_model`. `run()` waits on `_model_ready` with 60s timeout then uses `_cached_yolo_model` if set.

**Rationale**: Module-level state is consistent with `FrameAnalyzer._model` pattern already used in the codebase. The daemon thread pattern avoids blocking the main API thread. 60s timeout is generous — on a Pi with slow SD storage, initial model download + load may take 30-40s; on a PC with SSD it is 3-5s. If warm-up hasn't completed when `run()` starts (user clicked Start very quickly), the `wait(60)` ensures we don't start with a cold model unnecessarily. If 60s elapses and the model still isn't ready, `run()` falls back to loading it cold (current behavior) rather than failing.

**Alternatives considered**:
- Warm up in a thread pool executor: rejected — ThreadPoolExecutor.shutdown(wait=True) blocks even after timeout (the same reason `_run_in_daemon` uses a raw daemon thread in frame_analyzer.py).
- Pre-warm on app startup (before any file is loaded): rejected — model download would happen even if the user never uses YOLO mode, wasting RAM on Pi.

---

## Decision 6 — Time-based progress callback

**Decision**: Add a `_last_progress_at: float = time.monotonic()` tracker. In the inner loop, fire `on_progress()` if `frame_idx % BATCH_SIZE == 0 OR time.monotonic() - _last_progress_at >= 2.0`. Apply to both `detection_engine.py` and `yolo_detector.run()`.

**Rationale**: The 2-second wall-clock guarantee ensures the UI never appears frozen for more than 2 seconds, regardless of how many frames the engine processes per second. On a Pi doing <1 fps YOLO inference, BATCH_SIZE=100 would still mean 100+ seconds between callbacks without this fix. The wall-clock guard is reset after every fired callback, so the trigger is not cumulative.

**Alternatives considered**:
- Reduce BATCH_SIZE to 50: partially addresses the problem but doesn't solve it at very low frame rates.
- Emit progress on every frame: excessive — at 60fps this would fire 60 callbacks/second, flooding the SSE channel.

---

## Decision 7 — AI_FEATURES_ENABLED gate placement

**Decision**: `AI_FEATURES_ENABLED: bool = _total_gb >= 5.0` in `app/config.py`. Check as the FIRST condition in `FrameAnalyzer.is_available()`, before any transformers import.

**Rationale**: The threshold of 5.0 GB gives a comfortable margin: Florence-2 weights are ~3 GB in float32, plus the OS/Qt/backend overhead of ~1-2 GB on a Pi, plus the CCTV video frame in RAM. A 4 GB Pi would be at ~100% RAM with AI enabled. A 5 GB machine (edge case — few devices have exactly 5 GB, but if they do, they can support AI). Placing the check first means we never even attempt to import transformers on low-RAM devices, preventing the slow model-availability check.

**Alternatives considered**:
- 4 GB threshold: rejected — leaves <1 GB for OS+Qt+backend on a 4 GB Pi, causing OOM during analysis.
- 6 GB threshold: more conservative but excludes some valid 6 GB laptops unnecessarily.

---

## Decision 8 — Desktop path consolidation

**Decision**: New `app/utils/platform.py` with `get_desktop_path()`. Both callers import from there. Linux fallback order: `$XDG_DESKTOP_DIR` → `~/Desktop` → `~/Downloads` → `~/`.

**Rationale**: Single source of truth eliminates the duplication drift risk. `app/utils/platform.py` already has `platform_utils.py` in `shell/` — the new file lives in `app/utils/` following the existing `app/utils/ffprobe.py`, `app/utils/ffmpeg_path.py` pattern. The import direction `app/api/job.py → app/utils/platform.py` is safe (no circular import). The import `shell/main_window.py → app/utils/platform.py` is also safe since `shell/` already imports `app.config`.

**Alternatives considered**:
- Keep in `shell/platform_utils.py`: rejected — `app/api/job.py` imports from `shell/` would create an unusual import direction.
- Keep duplicates: rejected — they will drift over time.
