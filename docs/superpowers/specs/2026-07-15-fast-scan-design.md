# Phase 15 — Fast Scan: Detection Performance Overhaul

**Date**: 2026-07-15 · **Status**: Approved by user (2026-07-15, "go as per your recommendation")
**Branch**: 015-* (off 014-clip-event-search)

## Problem

`app/core/detection_engine.py` decodes **every frame at full source resolution**
via `cv2.VideoCapture.read()`, then downscales in Python. `frame_skip` is applied
*after* the decode, so skipping saves only the cheap MOG2 work, never the
expensive decode. On a 24-hour recording this means hours of pure video decoding
before any analysis value is produced.

## Measured evidence (2026-07-15, user's PC: Intel UHD Graphics, FFmpeg 7.1 bundled)

Test asset: 115 s HEVC 1080p @ 59.94 fps, 16 Mbps (worst-case codec; 6,864 frames).

| Pipeline | Time | vs current |
|---|---|---|
| Current engine loop (cv2 read → resize → MOG2 ×2 morphology) | 68.1 s (1.7× RT) | baseline |
| FFmpeg software decode, all frames | 44.9 s | — |
| FFmpeg software + `fps=4,scale=320:180` | 49.3 s | 1.4× |
| `-hwaccel d3d11va` + fps + scale (full-res copy-back) | 65.5 s | ✗ slower — copy-back kills it |
| Pure GPU decode, no copy-back | 9.5 s (12× RT) | — |
| **`hevc_qsv` + `vpp_qsv` GPU scale + tiny copy-back + fps=4** | **10.5 s** | — |
| **Realistic end state: qsv decode + fps=4 + scale → bgr24 rawvideo pipe** | **14.2 s (8× RT)** | **≈ 4.8×** |
| `-skip_frame nokey` (keyframes only) + scale | 4.4 s (26× RT) | GOP-locked sampling — deferred |

Key lessons baked into the design:
1. `fps=N` alone does NOT skip decode (inter-frame codecs must decode every
   frame) — the win comes from FFmpeg doing decode+scale in native code and
   Python only ever seeing tiny pre-scaled frames.
2. Hardware decode is only a win when scaling happens **on the GPU before
   copy-back** (`vpp_qsv` / `scale_cuda`); naive `-hwaccel` is slower.
3. Software-only fallback (no usable GPU) is still faster than the current loop.

## Design

### 1. FFmpeg frame-source pipeline (the core change)
New `app/core/frame_source.py`: spawns FFmpeg writing
`-f rawvideo -pix_fmt bgr24` to stdout at detect resolution and sampled fps;
Python reads fixed-size frames from the pipe. Replaces the cv2 read/resize head
of the detection loop. Timestamps derived as `frame_idx / sample_fps`.
- Decoder selection at job start (cached per session): probe codec via existing
  ffprobe util → try `<codec>_qsv` (Intel), `-hwaccel cuda + scale_cuda`
  (NVIDIA), else software `scale`. Selection verified with a ~2 s trial decode;
  any failure falls back down the chain to software. Software chain uses plain
  `fps=N,scale=W:H`.
- Legacy cv2 loop retained as final fallback (zero frames from pipe → legacy
  path, same pattern as `_normalize_via_vc`).

### 2. Scan-speed presets (UI + API)
`scan_speed: thorough | balanced | fast` on StartJobRequest; UI control beside
Sensitivity on Home page.
- **thorough** — legacy full-frame behavior (every frame, current path).
- **balanced** (default) — 5 fps sampling via FFmpeg pipeline.
- **fast** — 2 fps sampling.
MOG2 `history` rescaled to effective fps (background seconds ≈ constant);
`MOTION_THRESHOLD`/`min_area` are spatial per-frame values — unchanged.
`min_event_s` / `merge_gap_s` operate on timestamps — unchanged.

### 3. Opportunistic GPU for AI models
`torch.cuda.is_available()` → run YOLO / Florence-2 / CLIP on `cuda` device,
else CPU (status quo). User's PC has no CUDA → no behavior change there;
NVIDIA users get it free. Surface detected acceleration (decode + AI) in
`/api/system` capabilities and the UI so users can see what's active.

### 4. Guard the normalization landmine
`_normalize_via_vc` re-encodes the ENTIRE file before analysis — on 24 h input
that's hours + double disk. FFmpeg pipe path handles malformed streams better,
shrinking when this triggers; when it would trigger, warn with estimated
cost/size in the log rather than silently re-encoding for very long inputs.

### Explicitly deferred (Phase 16+)
Parallel chunked detection across cores; keyframes-only "Turbo" mode;
YOLO cascade (YOLO only inside MOG2 motion windows); batch queue.

## Quality guardrail (success criterion)
On the test asset, balanced mode must find the same events as thorough mode
(same count ±1, overlapping time ranges) while completing ≥ 3× faster
end-to-end. All existing tests keep passing; engines stay callback-driven
(constitution); no new Python dependencies.

## Release
After Phase 15 merges: 015 → 014 → 001 → master, release **v1.1.0** bundling
Phase 14 CLIP search + the CLIP download fix + Fast Scan.
