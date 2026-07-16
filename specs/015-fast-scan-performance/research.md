# Research: Fast Scan — Detection Performance Overhaul

All benchmarks measured 2026-07-15 on the target machine (Intel UHD Graphics,
driver 31.0.101.2130, bundled FFmpeg 7.1) against the reference asset:
115 s HEVC 1080p @ 59.94 fps, 16 Mbps, 6,864 frames — deliberately the
worst-case decode load.

| # | Pipeline | Time | Real-time factor |
|---|----------|------|------------------|
| 0 | Current engine loop (cv2 read → resize → gray → MOG2 → 2× morphology) | 68.1 s | 1.7× |
| 1 | FFmpeg software decode, all frames, null sink | 44.9 s | 2.6× |
| 2 | FFmpeg software + `fps=4,scale=320:180` | 49.3 s | 2.3× |
| 3 | `-hwaccel d3d11va` + fps + scale (full-res copy-back) | 65.5 s | 1.8× ✗ |
| 4 | Pure GPU decode, no copy-back (`-hwaccel_output_format d3d11`) | 9.5 s | 12× |
| 5 | `hevc_qsv` + `vpp_qsv` GPU scale + tiny copy-back + fps=4 | 10.5 s | 11× |
| 6 | Realistic end state: qsv + fps=4 + scale → **bgr24 rawvideo** (what Python reads) | 14.2 s | 8× |
| 7 | `-skip_frame bidir` + fps + scale (software) | 30.9 s | 3.7× |
| 8 | `-skip_frame nokey` (keyframes only) + scale | 4.4 s | 26× |

## D1 — Frame delivery: FFmpeg rawvideo pipe (chosen)

**Decision**: Spawn FFmpeg as a child process emitting `-f rawvideo -pix_fmt
bgr24` at detect resolution/sample rate; Python reads fixed-size frames from
stdout (`app/core/frame_source.py`).

**Rationale**: Rows 0 vs 6 — 4.8× end-to-end on the worst codec with zero new
dependencies (constitution V) and the same `np.ndarray` BGR frames the engines
already consume. FFmpeg does decode, frame-dropping, scaling, and color
conversion in native code; Python only ever touches 320×180×3 = 173 KB/frame
at ≤5 fps.

**Alternatives considered**:
- `cv2.grab()` for skipped frames — saves only retrieve/convert (~30 %), decode
  still dominates; rejected.
- PyAV — same FFmpeg underneath but a new binary dependency + packaging burden
  on 5 platforms; rejected (constitution V, "no new dependencies").
- `cv2.CAP_PROP_HW_ACCELERATION` — OpenCV's FFmpeg build on Windows wheels has
  inconsistent hwaccel support and no GPU-side scaling control; rejected
  (row 3 shows naive hwaccel is a regression).

## D2 — Decoder auto-selection: qsv → cuda → software, trial-verified

**Decision**: Candidate chains tried in order at job start, each verified by a
~2 s trial decode (≥1 frame delivered, exit 0); first success cached per codec
for the session. Chains:
1. Intel: `-hwaccel qsv -c:v {codec}_qsv` + `vpp_qsv=w=W:h=H,hwdownload,format=nv12,fps=N`
2. NVIDIA: `-hwaccel cuda -hwaccel_output_format cuda` + `fps=N,scale_cuda=W:H,hwdownload,format=nv12`
3. Software: `fps=N,scale=W:H`

**Rationale**: Row 3 proves hardware decode **without GPU-side scaling is
slower than software** (full-res frame copy-back) — the chain must scale
on-GPU before `hwdownload` (row 5: 10.5 s). Trial verification is mandatory
because hwaccel failures are driver/codec/profile-specific and often only
manifest at runtime (e.g. 10-bit HEVC on older iGPUs). d3d11va is deliberately
absent: FFmpeg 7.1 has no d3d11-native scale filter usable here, so d3d11va
always implies full-res copy-back — the measured regression.

**Alternatives considered**: static capability detection from
`ffmpeg -hwaccels` alone (lists methods, not whether they work for this codec
on this driver — insufficient); benchmarking all chains per job (adds ~10 s
startup for marginal gain — rejected; cached trial is enough).

## D3 — Sampling rates and MOG2 retuning

**Decision**: Balanced = 5 fps, Fast = 2 fps of source time, capped at native
fps (never upsample). MOG2 `history` becomes seconds-based:
`HISTORY_SECONDS = {"low": 28, "medium": 20, "high": 8}` ×
`effective_fps` (current constants 700/500/200 ÷ 25 fps ≈ those values, so
Thorough-equivalent adaptation time is preserved). Warmup = 6 s ×
effective_fps (min 5 frames). Spatial parameters (`varThreshold`,
`MOTION_THRESHOLD`, 3×3 ellipse kernel, CLAHE-on-high) unchanged — they are
per-frame, resolution-relative quantities.

**Rationale**: min event duration defaults to 2 s → 10 samples/event at 5 fps,
4 at 2 fps — ample for the ratio-threshold state machine. MOG2 `history` is
denominated in *frames*; leaving it unscaled at 5 fps would stretch background
adaptation from ~20 s to ~100 s and change sensitivity behavior — the one real
quality trap in fps sampling, addressed head-on.

**Alternatives**: keyframes-only (`-skip_frame nokey`, row 8, 26×) — sampling
rate is GOP-locked (often 1 fps or worse) and quality-risky; deferred as a
possible future "Turbo" preset. `-skip_frame bidir` (row 7) — inferior to the
qsv chain, adds decoder-specific behavior variance; rejected.

## D4 — Thorough = the untouched legacy path

**Decision**: `scan_speed="thorough"` executes the existing
`cv2.VideoCapture` loop with zero modifications (including probe/normalize
and legacy `frame_skip` honoring). The sampled path is additive code.

**Rationale**: Spec FR-002/acceptance 2 requires v1.0.x-identical Thorough
results; keeping the old loop intact makes that guarantee trivially true, and
it doubles as the final fallback when the pipe yields zero frames (FR-009).

## D5 — YOLO mode frames at 640×360

**Decision**: In sampled modes `yolo_detector` consumes `frame_source` at
640×360 (not detect-res 320×180), same preset fps; `YOLO_FRAME_SKIP` remains
only in Thorough.

**Rationale**: yolov8n's native input is 640 px — feeding 320×180 would halve
effective resolution and measurably hurt small-object recall. 640×360 keeps
the decode win (still 9× less pixel traffic than 1080p) without an accuracy
cliff. Box coordinates land in frame space; the existing `_write_heatmap`
upscale handles rendering.

## D6 — GPU for AI: central cached torch probe

**Decision**: `app/utils/ai_device.py` → `get_ai_device()` returns `"cuda"`
iff `torch.cuda.is_available()` (import-guarded, cached, never raises), else
`"cpu"`. Florence-2 and CLIP move model + inputs to that device; ultralytics
gets an explicit `device=` argument. Reported via
`describe_ai_device()` in capabilities.

**Rationale**: user requirement "add GPU acceleration if GPU is available; my
PC does not have GPU" — must be a strict no-op on CPU-only machines. A single
cached helper avoids three divergent detection snippets (constitution V).
Shipped installers bundle CPU-only torch, so this benefits source installs /
future CUDA bundles; on this machine tests pin the `"cpu"` path.

**Alternative**: user-facing GPU toggle (ROADMAP §E) — rejected for this
phase; automatic-with-visibility is simpler and matches the request.

## D7 — Rotation metadata → software chain

**Decision**: Extend `ffprobe.probe()` with a `rotation` field (side-data
displaymatrix); when non-zero, skip hardware candidates and use the software
chain, where FFmpeg autorotate is dependable.

**Rationale**: autorotate across hwaccel + vpp filter graphs is
version/driver-fragile; rotated sources are rare in CCTV (fixed cameras), so
trading acceleration for correctness there is the right default. Cheap to
implement, removes a whole failure class from the trial/fallback path.

## D8 — Normalization guard threshold

**Decision**: `_normalize_via_vc` trigger on inputs `> 1800 s` logs a
prominent warning first: repair takes on the order of the video's duration and
roughly the source's size on disk. It still proceeds (correctness first); the
sampled FFmpeg path doesn't use the cv2 probe at all, so this now fires only
in Thorough mode or after fallback.

**Rationale**: FR-008 requires "no silent multi-hour surprises"; blocking or
prompting from a worker thread would need new UI machinery (YAGNI) — a loud,
early, cost-estimating log line in the existing SSE log panel meets the
requirement.
