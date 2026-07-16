# Tasks: Fast Scan — Detection Performance Overhaul

**Feature**: `015-fast-scan-performance` | **Plan**: [plan.md](plan.md) | **Contract**: [contracts/fast-scan-api.md](contracts/fast-scan-api.md)
**TDD**: constitution Principle III — every backend task pairs a failing-test task before its implementation task. Frontend JS tasks cite the exemption and map to quickstart.md scenarios.

## Phase 1: Setup

- [x] T001 Verify baseline: run `python -m pytest tests/ -q` from repo root and confirm the pre-feature suite passes (record count; expect ≥ 274 passed / 2 skipped) so later regressions are attributable.

## Phase 2: Foundational (blocking prerequisites for both engines and both stories)

- [x] T002 [P] Write failing tests for the rotation probe field in `tests/test_ffprobe.py` (or extend the existing probe tests): `probe()` result contains `rotation: 0` for a non-rotated file; a displaymatrix/rotate tag yields the parsed degrees (synthetic ffprobe JSON via monkeypatch); missing/unparseable side data → 0, never raises.
- [x] T003 Implement `rotation` in `app/utils/ffprobe.py` (ffprobe JSON side-data + stderr-fallback default 0). Run T002 to green.
- [x] T004 [P] Write failing tests for `app/core/frame_source.py` in `tests/test_frame_source.py`:
  (a) command construction per chain — qsv chain contains `-hwaccel qsv`, `{codec}_qsv`, `vpp_qsv=w=W:h=H,hwdownload,format=nv12,fps=N`; cuda chain contains `scale_cuda`; software chain contains `fps=N,scale=W:H`; all end with `-f rawvideo -pix_fmt bgr24 -an`;
  (b) codec map — a codec with no `_qsv`/cuda variant (e.g. `mjpeg`) skips hardware candidates; `rotation != 0` skips hardware candidates;
  (c) trial selection — first candidate whose trial (mocked subprocess) delivers ≥1 frame with exit 0 wins; failures fall through to software; selection cached per codec (`_selection_cache`), second call runs no new trial;
  (d) frame iteration — feeding a fake stdout with N×(W·H·3) bytes yields N frames of shape (H, W, 3) with `pts = i / sample_fps`;
  (e) stall watchdog — no bytes for the (test-shortened) watchdog window while child alive → raises/kills, never hangs;
  (f) `close()` — terminates the child (terminate → kill after grace), idempotent, called by the context manager on exceptions;
  (g) `get_acceleration_status()` — returns `methods_available` list and `selected` dict reflecting the cache;
  (h) real-decode integration (skipif no ffmpeg): software chain on a tiny generated test clip (ffmpeg `testsrc`, ~2 s) yields the expected frame count at fps=2 and exact frame dimensions.
- [x] T005 Implement `app/core/frame_source.py` per plan.md Architecture: chain builders + codec maps, trial decode (~2 s, ≥1 frame + exit 0), per-codec session cache, `FrameStream` context-manager/iterator reading exact-size frames with stderr drained by a daemon thread, 30 s stall watchdog, `close()` with 3 s grace, `get_acceleration_status()`, `SAMPLE_FPS = {"balanced": 5.0, "fast": 2.0}` capped at source fps. All FFmpeg invocations via `get_ffmpeg()` (constitution II). Run T004 to green.

**Checkpoint**: frame source fully tested and reusable by both engines.

## Phase 3: User Story 1 — Long recordings finish in a fraction of the time (P1)

**Goal**: scan-speed presets end-to-end: API field → sampled engine paths → UI control; parity + fallback guarantees.
**Independent test**: Balanced vs Thorough on the reference asset — ≥3× faster, events count ±1 with overlapping ranges (quickstart #2–#5; automated parity test on synthetic video).

- [x] T006 [P] [US1] Write failing tests in `tests/test_detection_engine.py` for the sampled MOG2 path:
  (a) synthetic-motion parity — build a short synthetic video (or frame sequence via monkeypatched frame_source) with a known motion window; balanced run emits the same event count as the legacy path with overlapping start/end;
  (b) MOG2 rescale — at sample_fps 5.0/2.0 the engine constructs MOG2 with `history == int(HISTORY_SECONDS[sens] * fps)` and warmup `max(5, int(6*fps))` (assert via monkeypatched `cv2.createBackgroundSubtractorMOG2`);
  (c) timestamps — events derive `start_s`/`end_s` from `pts = i/sample_fps` (feed frames with known indices, assert second-accurate boundaries incl. padding);
  (d) thorough untouched — `scan_speed="thorough"` never imports/opens frame_source (monkeypatch it to raise) and still honors legacy `frame_skip`;
  (e) zero-frame fallback — frame_source yielding nothing → legacy loop runs (monkeypatched `cv2.VideoCapture` counter) and detection completes;
  (f) mid-run failure — frame_source raising after k frames → partial results discarded, legacy loop re-runs, events not duplicated;
  (g) sample-fps cap — source fps 2.0 with balanced → sample_fps 2.0 (no upsample);
  (h) short clip — a 0.1 s source still analyzes ≥1 frame.
- [x] T007 [US1] Implement the sampled path in `app/core/detection_engine.py`: `scan_speed` dispatch (`thorough` → existing loop verbatim), sampled loop consuming `frame_source.open_frames(source_path, source_info, sample_fps, W, H, log)` with seconds-based MOG2 constants (`HISTORY_SECONDS = {"low": 28, "medium": 20, "high": 8}`), warmup, unchanged state machine/heatmap/zone mask, progress vs `duration_s × sample_fps`, zero-frame + mid-run fallback to legacy, `[FASTSCAN]` log lines. Run T006 to green.
- [x] T008 [P] [US1] Write failing tests in `tests/test_api_job.py` (extend): `POST /job/start` default `scan_speed == "balanced"` lands in `session.snapshot()["settings"]`; explicit `"thorough"`/`"fast"` accepted; invalid value → 422 naming allowed values; legacy body without the field still works.
- [x] T009 [US1] Implement `scan_speed: Literal["thorough","balanced","fast"] = "balanced"` on `StartJobRequest` in `app/api/job.py` (flows via existing `req.model_dump()`). Run T008 to green.
- [x] T010 [P] [US1] Write failing tests in `tests/test_yolo_detector.py` (extend, mocked ultralytics): sampled modes read frames from frame_source at 640×360 with `t_s = i/sample_fps` (assert event boundaries); progress denominator is `duration_s × sample_fps` (assert on_progress values with known frame counts); `YOLO_FRAME_SKIP` applied only in thorough; thorough path unchanged (no frame_source import).
- [x] T011 [US1] Implement sampled-mode frame_source consumption in `app/core/yolo_detector.py` per plan (640×360, same presets, heatmap at frame resolution, progress total = `duration_s × sample_fps`). Run T010 to green.
- [x] T012 [US1] Scan-speed UI in `static/js/pages/home.js` + styles: segmented "Scan speed" control (Thorough / Balanced / Fast) beside Sensitivity, Balanced pre-selected, one-line trade-off hint, value sent as `scan_speed` in the start payload, reset to Balanced on New Project. Frontend exemption: verify via quickstart #1, #3–#6, #11.

**Checkpoint**: US1 delivers the headline speedup end-to-end.

## Phase 4: User Story 2 — Automatic acceleration + visibility (P2)

**Goal**: hardware decode auto-selection is already live via Phase 2; add AI-device opportunism and surface both in API + UI.
**Independent test**: capabilities endpoint returns the acceleration shape; on this machine AI device is `cpu` and a Balanced run selects `qsv` (quickstart #2, #8).

- [x] T013 [P] [US2] Write failing tests in `tests/test_ai_device.py` (new): `get_ai_device()` returns `"cpu"` when torch missing (sys.modules block) and when `torch.cuda.is_available()` is False; `"cuda"` when monkeypatched True; result cached; `describe_ai_device()` returns `"cpu"` or `"cuda:0 — <name>"`; never raises.
- [x] T014 [US2] Implement `app/utils/ai_device.py` per data-model. Run T013 to green.
- [x] T015 [P] [US2] Write failing tests for device plumbing: `tests/test_frame_analyzer.py` — model+inputs moved to `get_ai_device()` result (monkeypatched device string, fake model records `.to()` calls); `tests/test_clip_indexer.py` — same for CLIP embed/embed_text; `tests/test_yolo_detector.py` — inference called with explicit `device=get_ai_device()`. On `"cpu"` all existing behavior tests stay green (no-op guarantee).
- [x] T016 [US2] Implement device usage in `app/core/frame_analyzer.py`, `app/core/clip_indexer.py`, `app/core/yolo_detector.py`. Run T015 + the full pre-existing AI test set to green.
- [x] T017 [P] [US2] Write failing tests in `tests/test_api_system.py` (extend): `/system/capabilities` response contains `yolo_available` (unchanged), `ai_device` string, and `decode_acceleration` with `methods_available: list` + `selected: dict`; endpoint never 500s when the ffmpeg hwaccel query fails (monkeypatch to raise → `[]`).
- [x] T018 [US2] Implement the capabilities extension in `app/api/system.py` (ffmpeg `-hwaccels` cached query + `frame_source.get_acceleration_status()` + `describe_ai_device()`). Run T017 to green.
- [x] T019 [US2] Acceleration status line in the Home page system/AI status area (`static/js/pages/home.js` + CSS): shows decode method (after a sampled run) and AI device from capabilities; graceful text before first run. Frontend exemption: quickstart #8.

**Checkpoint**: acceleration is automatic, safe on CPU-only machines, and visible.

## Phase 5: User Story 3 — No silent multi-hour surprises (P3)

- [x] T020 [P] [US3] Write failing test in `tests/test_detection_engine.py`: when the legacy path's normalization trigger fires for a source with `duration_s > 1800` (monkeypatched probe outcome), a warning containing duration and approximate repair scale is emitted via the logger BEFORE `_normalize_via_vc` runs; ≤ 30 min inputs keep current behavior.
- [x] T021 [US3] Implement the guard in `app/core/detection_engine.py` (`_open_video`), message per contract "Log surface". Run T020 to green.

**Checkpoint**: all three stories complete and independently verifiable.

## Phase 6: Polish & Cross-Cutting

- [ ] T022 Run the full suite `python -m pytest tests/ -q`: everything green, ≥ 12 new tests total (SC-005), zero pre-existing failures.
- [ ] T023 [P] E2E benchmark + parity verification against the real app and reference asset (script in scratchpad, like Phase 14's e2e_search.py): create job → Thorough run (record wall time + events) → Balanced run (record wall time + events + selected decoder) → assert SC-001 (≥3×), SC-002 (count ±1, overlapping ranges), SC-007 (cancel mid-run → no ffmpeg process remains, immediate re-run works) → **forced-software Balanced run** (env flag/monkeypatch skipping hw candidates) asserting SC-004 (≥1.2× vs Thorough). Record all numbers in the PR description.
- [ ] T024 [P] Execute quickstart.md scenarios 1–12 (visual scenarios need the user at the real UI; backend-driveable ones may be script-verified) and record PASS/FAIL in the PR description; fix any defects found and re-verify.
- [x] T025 [P] Documentation: README.md (Features + performance note), USER_MANUAL.md ("Scan speed" section: presets, trade-offs, acceleration status line, 24-hour-footage guidance recommending Balanced).

## Dependencies & Execution Order

- Phase 2 blocks everything (T002→T003, T004→T005).
- US1: T006→T007, T008→T009, T010→T011 (T006/T008/T010 parallelizable after Phase 2); T012 after T009. T007 and T011 both depend on T005.
- US2: T013→T014→T015→T016; T017→T018 (needs T005 for status, T014 for device); T019 after T018. US2 backend is parallelizable with US1 backend except T017/T018 (need T005/T014).
- US3: T020→T021; independent of US1/US2 (legacy-path change only).
- Polish last: T022 after all implementation; T023/T024 after T012/T019/T021; T025 anytime after T012.

**MVP scope**: Phase 2 + US1 (presets, sampled engine, API, UI) — delivers the speedup. US2/US3 complete the acceleration visibility and safety promises; target increment is all three.

## Implementation strategy

Strict TDD per constitution: each test task must FAIL before its paired
implementation task starts, and pass after. Superpowers skills in effect:
test-driven-development, verification-before-completion. Thorough mode is
never edited — parity with v1.0.x is guaranteed by not touching that code path.
