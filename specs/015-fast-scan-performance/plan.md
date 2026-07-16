# Implementation Plan: Fast Scan — Detection Performance Overhaul

**Branch**: `015-fast-scan-performance` | **Date**: 2026-07-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/015-fast-scan-performance/spec.md`

## Summary

Detection currently decodes every frame at full resolution through
`cv2.VideoCapture` (measured 1.7× real-time on HEVC 1080p60 → a 24 h file takes
~14 h). This phase replaces the decode head of both detection engines with an
FFmpeg child-process pipeline that samples (fps filter), scales to detect
resolution, and — when the machine supports it — decodes on the GPU with
GPU-side scaling, writing tiny raw BGR frames to a pipe that Python reads.
Measured end-state on the reference clip: 14.2 s vs 68.1 s (≈4.8× faster; 8×
real-time). Users pick Thorough / Balanced (default) / Fast; Thorough is the
untouched legacy path. AI models (YOLO/Florence-2/CLIP) opportunistically use
CUDA when available (no-op on CPU-only machines like the user's). Active
acceleration is surfaced via `/api/system/capabilities` and shown in the UI.

## Technical Context

**Language/Version**: Python 3.12 (backend), vanilla ES modules (frontend, no build step)
**Primary Dependencies**: FastAPI, OpenCV (`cv2`), numpy, bundled FFmpeg 7.1 via `imageio-ffmpeg` (`app/utils/ffmpeg_path.py`); optional: `ultralytics`, `torch`/`transformers`/`open-clip-torch` — **no new dependencies**
**Storage**: none — `scan_speed` lives in the per-job settings dict inside `app/session.py` (session-only)
**Testing**: pytest (`tests/`, ~274 existing); real-video tests guarded with `skipif`
**Target Platform**: Windows/macOS/Linux desktop + headless Pi (identical code paths; hw decode is capability-probed per machine)
**Project Type**: desktop app (FastAPI backend + embedded web UI)
**Performance Goals**: Balanced ≥3× faster than Thorough on the 115 s HEVC 1080p60 reference asset; ≥6× real-time on that footage class on the dev machine; software-only machines still ≥1.2× faster than current
**Constraints**: offline; event parity (count ±1, overlapping ranges) between Balanced and Thorough on the reference asset; engines stay callback-driven; Thorough must remain byte-for-byte the current behavior
**Scale/Scope**: 1 new core module, 2 engine integrations, 1 API field, 1 API extension, 1 UI control + 1 UI status line, ~15–20 new tests

## Constitution Check

1. **Principle I (session-first)** — PASS. `scan_speed` is a per-job setting in the session dict; decode capability is derived at runtime and cached in module memory only. Nothing persisted.
2. **Principle II (cross-platform)** — PASS. All paths `pathlib.Path`; FFmpeg via `get_ffmpeg()`; hw decode is probed per machine, never assumed; subprocess uses list-form commands (spaces-safe).
3. **Principle III (test-first)** — PASS. `app/core/frame_source.py`, engine changes, and API changes get failing tests first. Frontend JS (scan-speed control, acceleration status line) uses the documented exemption → `quickstart.md` scenarios.
4. **Principle IV (callback-driven)** — PASS. `frame_source` is a frame iterator consumed by engines; engines keep the `on_progress`/`on_event` contract and never import session.
5. **Principle V (YAGNI)** — PASS. No new abstraction beyond one frame-source module both engines share; the decoder chain has exactly the three candidates the benchmarks justify; deferred items (chunked parallelism, turbo mode, YOLO cascade) are explicitly out of scope.

**Post-design re-check (Phase 1)**: no violations introduced; Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/015-fast-scan-performance/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions D1–D8 (benchmark-backed)
├── data-model.md        # Phase 1 — settings/capability shapes
├── quickstart.md        # Phase 1 — manual verification scenarios (frontend exemption)
├── contracts/
│   └── fast-scan-api.md # start-job scan_speed + capabilities extension
├── checklists/
│   └── requirements.md  # spec quality checklist (from /speckit.specify)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by plan)
```

### Source Code (repository root)

```text
app/
├── core/
│   ├── frame_source.py        # NEW — FFmpeg pipe frame iterator + decoder auto-selection
│   ├── detection_engine.py    # MOD — sampled path (frame_source) beside untouched legacy loop;
│   │                          #       normalization-guard warning for >30 min inputs
│   └── yolo_detector.py       # MOD — consume frame_source in sampled modes (640×360 frames)
├── api/
│   ├── job.py                 # MOD — StartJobRequest.scan_speed (validated), passed via settings
│   └── system.py              # MOD — /system/capabilities gains acceleration report
└── utils/
    └── ai_device.py           # NEW — cached torch-CUDA device probe for AI stages

app/core/frame_analyzer.py     # MOD — move model+inputs to ai_device (cuda when available)
app/core/clip_indexer.py       # MOD — same device handling

static/js/pages/home.js        # MOD — Scan speed control (Thorough/Balanced/Fast, default Balanced);
                               #       acceleration status line in the system/AI status area
static/css/home.css (or main)  # MOD — styles for the control + status line

tests/
├── test_frame_source.py       # NEW — command construction, chain fallback, pipe reading, cancel/close
├── test_detection_engine.py   # MOD — sampled-mode tests: parity, MOG2 rescale, zero-frame fallback,
│                              #       normalization guard warning
├── test_yolo_detector.py      # MOD — sampled-mode wiring (mocked model)
├── test_api_job.py            # MOD — scan_speed validation + default + settings passthrough
├── test_api_system.py         # MOD — capabilities acceleration shape
└── test_ai_device.py          # NEW — device probe (cpu on this machine; monkeypatched cuda)

README.md / USER_MANUAL.md     # MOD — Scan speed docs + acceleration visibility
```

**Structure Decision**: single-project layout, matching every prior phase. One
new core module (`frame_source.py`) shared by both engines; everything else is
surgical modification of existing files.

## Architecture

### frame_source.py (the core)

```python
def open_frames(source_path, source_info, sample_fps, width, height, logger)
    -> FrameStream   # context manager + iterator of (np.ndarray BGR h×w×3, pts_seconds)
```

- Builds an FFmpeg command per the selected decoder chain and spawns it with
  `stdout=PIPE`; Python reads exactly `width*height*3` bytes per frame.
  `pts_seconds = frames_read / sample_fps` (the `fps` filter emits CFR output,
  which also normalizes VFR sources).
- **Decoder chains** (candidates tried in order, first that passes a ~2 s trial
  decode wins; selection cached per codec for the session):
  1. **Intel Quick Sync**: `-hwaccel qsv -c:v {codec}_qsv` +
     `-vf vpp_qsv=w=W:h=H,hwdownload,format=nv12,fps=N` (GPU-side scale before
     copy-back — the naive full-res copy-back variant measured *slower* than
     software and is never used). Codec map: h264/hevc/vp9/av1/mpeg2 → `_qsv`.
  2. **NVIDIA**: `-hwaccel cuda -hwaccel_output_format cuda` +
     `-vf fps=N,scale_cuda=W:H,hwdownload,format=nv12`.
  3. **Software**: `-vf fps=N,scale=W:H`.
  Output always `-f rawvideo -pix_fmt bgr24 -an` on stdout; stderr drained by a
  daemon thread (deadlock-safe), last lines kept for error reporting.
- **Rotation**: if the probe reports rotation metadata, hardware candidates are
  skipped (FFmpeg's autorotate is reliable in the software chain; rotated CCTV
  is rare). Requires a small `rotation` addition to `app/utils/ffprobe.probe`.
- `close()` terminates the child (`terminate` → `kill` after grace), releasing
  the file handle — wired to cancellation so no orphaned FFmpeg survives (SC-007).
- Module-level `get_acceleration_status()` returns the last/probed selection
  for the capabilities endpoint.

### detection_engine.py integration

- `scan_speed` read from settings; `"thorough"` (or legacy `frame_skip` callers)
  → the existing loop, character-for-character untouched.
- Sampled path: `sample_fps = {"balanced": 5.0, "fast": 2.0}`, capped at the
  source fps (never upsample). MOG2 constants become seconds-based:
  `history = int(HISTORY_SECONDS[sens] * effective_fps)` with
  `HISTORY_SECONDS = {"low": 28, "medium": 20, "high": 8}` (derived from the
  current frame counts at 25 fps); warmup = `int(6 s × effective_fps)`, min 5.
  Spatial thresholds (`MOTION_THRESHOLD`, morphology) unchanged. Progress
  total = `duration_s × sample_fps`. Heatmap/zone-mask/state-machine logic
  unchanged (same W×H frames).
- Zero frames from the pipe → log + fall back to the legacy loop (FR-009).
- `_normalize_via_vc` guard: when triggered for `duration_s > 1800`, emit a
  prominent log warning with estimated time (~source duration) and disk (~size)
  before proceeding (FR-008). The sampled path doesn't use `_open_video` at all
  — FFmpeg CLI tolerates the malformed-edit-list files that break
  `cv2.VideoCapture`, so the repair path fires far less often.

### yolo_detector.py integration

- Sampled modes read 640×360 frames from `frame_source` at the same preset fps
  (YOLO's input size is 640 — feeding detect-res 320×180 would cost accuracy);
  `t_s = idx / sample_fps`; `YOLO_FRAME_SKIP` applies only in Thorough.
  Heatmap accumulates at frame resolution (existing `_write_heatmap` upscales).

### GPU for AI (opportunistic)

- `app/utils/ai_device.py`: `get_ai_device() -> str` — `"cuda"` if
  `torch.cuda.is_available()` else `"cpu"`, cached, never raises (torch may be
  absent). `describe_ai_device()` for the capabilities payload
  (e.g. `"cuda:0 — NVIDIA RTX 3060"` / `"cpu"`).
- `frame_analyzer.py` / `clip_indexer.py`: `.to(get_ai_device())` on model +
  inputs at load/encode time. `yolo_detector`: pass explicit
  `device=get_ai_device()` to inference. On this machine (no CUDA) everything
  resolves to `"cpu"` — bit-identical behavior, verified by tests.

### API + UI

- `StartJobRequest.scan_speed: str = "balanced"`, validated against
  `{"thorough","balanced","fast"}` → 422/400 on invalid; flows through
  `settings` (already `req.model_dump()`).
- `/api/system/capabilities` response gains:
  `{"decode_acceleration": {"methods_available": [...], "selected": {...codec→method...}},
    "ai_device": "cpu"|"cuda:0 — <name>"}` (existing `yolo_available` kept).
- `home.js`: three-option segmented control "Scan speed" beside Sensitivity
  (default Balanced, hint text with the trade-off); start payload includes
  `scan_speed`. Acceleration line in the existing system/AI status card, fed by
  capabilities. Frontend exemption → quickstart scenarios.

## Complexity Tracking

*No constitution violations — table intentionally empty.*
