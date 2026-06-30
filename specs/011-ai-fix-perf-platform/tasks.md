# Tasks: AI Fix, Performance & Cross-Platform Support

**Branch**: `011-ai-fix-perf-platform`  
**Input**: Design documents from `specs/011-ai-fix-perf-platform/`  
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Tests**: Included per Constitution Principle III (Test-First, NON-NEGOTIABLE). All `app/core/` and `app/api/` changes require a failing test written BEFORE implementation. Frontend JS (`static/js/`) covered by quickstart.md scenarios per the frontend exemption.

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US4)
- All file paths are project-relative from repo root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Foundational constants and utilities that ALL user stories depend on. Must complete before any story work begins.

- [X] T001 Add `AI_FEATURES_ENABLED: bool = _total_gb >= 5.0` and `YOLO_FRAME_SKIP: int = 6 if IS_PI else 3` to `app/config.py`; change `BATCH_SIZE: int = 500` to `BATCH_SIZE: int = 100 if IS_PI else 500`; optionally add a one-line assertion `assert BATCH_SIZE == 100` in a test when `IS_PI=True` is monkeypatched (can be appended to `tests/test_config.py` if it exists, or skipped if low-priority) [F8: low-priority config assertion]
- [X] T002 [P] Create `app/utils/platform.py` with `get_desktop_path()` supporting Windows (SHGetFolderPathW), macOS (`~/Desktop`), Linux/Pi (`$XDG_DESKTOP_DIR` → `~/Desktop` → `~/Downloads` → `~/`)

**Checkpoint**: `from app.config import AI_FEATURES_ENABLED, YOLO_FRAME_SKIP` works; `from app.utils.platform import get_desktop_path` works with no circular imports.

---

## Phase 2: Foundational — Write Tests First (Constitution III)

**Purpose**: Write ALL test cases BEFORE any implementation. Run them to confirm they fail. This phase is a prerequisite for phases 3–6.

⚠️ **CRITICAL**: Run `pytest tests/test_frame_analyzer.py tests/test_platform_utils.py -v` after writing tests; confirm they fail with `ImportError` or `AssertionError` before proceeding.

- [X] T003 Create `tests/test_frame_analyzer.py` with 7 test functions: `test_clean_caption_strips_special_tokens` (assert `_clean_caption("</s>A person<loc_123>")` → `"A person"`), `test_clean_caption_handles_empty` (assert `_clean_caption("")` → `""`), `test_clean_caption_handles_none_input` (pass `None` via default, assert → `""`), `test_clean_caption_preserves_clean_text` (assert no-op on clean string), `test_is_available_false_when_ai_features_disabled` (monkeypatch `app.config.AI_FEATURES_ENABLED = False`, call `FrameAnalyzer.is_available()`, assert `False`), `test_squaring_removed` (mock processor + model, pass 1920×1080 PIL image to `_run_analysis`, assert processor received original size not 1920×1920), `test_no_warnings_during_inference` (use `pytest.warns(None)` / `warnings.catch_warnings(record=True)`, mock processor + model, call `_run_task()`, assert zero `UserWarning` or `DeprecationWarning` records captured) [F4: SC-002 automated assertion]
- [X] T004 [P] Add 3 tests to `tests/test_platform_utils.py` (create file): `test_get_desktop_path_linux_xdg` (mock `platform.system="Linux"`, `os.environ["XDG_DESKTOP_DIR"]="/tmp/desk"`, `Path("/tmp/desk").is_dir()=True`, assert returns `/tmp/desk`), `test_get_desktop_path_linux_no_desktop` (mock Linux, no XDG, no `~/Desktop`, `~/Downloads` exists, assert returns `~/Downloads`), `test_get_desktop_path_macos` (mock `platform.system="Darwin"`, assert returns `str(Path.home() / "Desktop")`)
- [X] T005 [P] Add 2 tests to existing `tests/test_yolo_detector.py`: (1) `test_yolo_prewarm_sets_event` — mock `ultralytics.YOLO` constructor (no-op), call `yolo_detector.prewarm()`, assert `yolo_detector._model_ready.is_set()` within 5 seconds; (2) `test_time_based_progress_fires` — monkeypatch `time.monotonic()` to advance >2.0s between calls, mock `on_progress` callback, run a minimal yolo_detector loop with 1 frame, assert callback called even though `frame_idx % BATCH_SIZE != 0` [F6: SC-003 automated assertion]
- [X] T006 Run `pytest tests/test_frame_analyzer.py tests/test_platform_utils.py -v --tb=short` and confirm all new tests FAIL (expected — implementation not yet written)

---

## Phase 3: User Story 1 — Readable AI Descriptions (P1) 🎯 MVP

**Goal**: Fix Florence-2 producing raw token garbage (`</s>`, `<loc_NNN>`, `<s>`) and black-image descriptions in Intelligence Reports.

**Independent Test**: `pytest tests/test_frame_analyzer.py -v` → 6 tests pass. For manual: generate any Intelligence Report → zero raw tokens in captions.

- [X] T007 [US1] In `app/core/frame_analyzer.py`: add `import re` (top), add module-level `_SPECIAL_TOKEN_RE = re.compile(r'</s>|<s>|<pad>|<loc_\d+>|</?[A-Z_]+>')` and `def _clean_caption(text: str) -> str: return _SPECIAL_TOKEN_RE.sub('', text or '').strip()` (before `class FrameAnalyzer`)
- [X] T008 [US1] In `app/core/frame_analyzer.py`: delete the 5-line image squaring block (lines 142–146: `if image.width != image.height: ... image = sq`) and its preceding comment `# Florence-2's DaViT vision encoder requires square feature maps`
- [X] T009 [US1] In `app/core/frame_analyzer.py`: change `max_new_tokens=64` → `max_new_tokens=100` in both `_run_task()` (line ~159) and `_region_task()` (line ~205)
- [X] T010 [US1] In `app/core/frame_analyzer.py`: wrap the body of `_run_task()` in `with warnings.catch_warnings():` filtering `UserWarning` from `torch`/`transformers` and `DeprecationWarning` from `numpy`/`PIL`; apply same wrapper inside `_region_task()`
- [X] T011 [US1] In `app/core/frame_analyzer.py`: apply `_clean_caption()` at all three extraction points — `caption` (line ~174), detection labels (line ~186 loop), `object_caption` (line ~216)
- [X] T012 [US1] In `app/core/frame_analyzer.py`: add `from app.config import AI_FEATURES_ENABLED` import; in `is_available()` add as the FIRST check: `if not AI_FEATURES_ENABLED: cls._availability_cache = False; return False`
- [X] T013 [US1] Run `pytest tests/test_frame_analyzer.py -v` — confirm all 6 tests PASS; fix any failures before proceeding

**Checkpoint**: All 6 `test_frame_analyzer.py` tests pass. Florence-2 garbage output fixed at code level. AI gate correctly returns False when RAM < 5 GB.

---

## Phase 4: User Story 2 — Responsive Detection with Live Progress (P2)

**Goal**: Eliminate YOLO cold-start lag, reduce YOLO inference per-frame load, ensure progress bar moves every 2 seconds on all platforms.

**Independent Test**: `pytest tests/test_yolo_detector.py::test_yolo_prewarm_sets_event -v` passes. `pytest tests/test_detection_engine.py -v` remains green. Progress bar moves within 2s (quickstart.md S5).

- [X] T014 [US2] In `app/core/yolo_detector.py`: add module-level `_model_ready = threading.Event()` and `_cached_yolo_model = None`; add `def prewarm() -> None:` function that imports YOLO in a daemon thread, loads `MODEL_DIR / "yolov8n.pt"` into `_cached_yolo_model`, and always calls `_model_ready.set()` in a `finally` block (catches `ImportError` and any load error silently)
- [X] T015 [US2] In `app/core/yolo_detector.py`: in `run()` replace the cold `model = YOLO(str(model_path))` load with `_model_ready.wait(timeout=60); model = _cached_yolo_model or YOLO(str(model_path))`; add `import time` and `_last_progress_at = time.monotonic()` before the detection loop
- [X] T016 [US2] In `app/core/yolo_detector.py`: add `from app.config import YOLO_FRAME_SKIP` import; inside the detection loop, after `frame_idx += 1`, add `if frame_idx % YOLO_FRAME_SKIP != 0: continue` (skip frame); replace `if frame_idx % BATCH_SIZE == 0:` with time-based dual trigger `if frame_idx % BATCH_SIZE == 0 or time.monotonic() - _last_progress_at >= 2.0:` followed by `_last_progress_at = time.monotonic()`
- [X] T017 [US2] In `app/core/detection_engine.py`: add `_last_progress_at = time.monotonic()` before the main detection loop (around line 285 area); replace `if frame_idx % config.BATCH_SIZE == 0:` (line ~388) with `if frame_idx % config.BATCH_SIZE == 0 or time.monotonic() - _last_progress_at >= 2.0:` followed by `_last_progress_at = time.monotonic()` (`time` already imported) — **required for SC-003**; both T016 and T017 MUST ship together to satisfy FR-011 [F7]
- [X] T018 [US2] **(job.py coordination — deferred to T024)** No direct job.py edit in this phase. The prewarm trigger will be added during T024 (US4/Phase 6), which is the single designated job.py edit pass. This avoids a double-edit conflict. [F5 resolution]
- [X] T019 [US2] Run `pytest tests/test_yolo_detector.py tests/test_detection_engine.py -v` — confirm `test_yolo_prewarm_sets_event` and `test_time_based_progress_fires` pass and no regressions

**Checkpoint**: Prewarm test passes. Detection engine tests green. YOLO starts faster; progress callbacks fire every ≤2s.

---

## Phase 5: User Story 3 — Persistent Log Panel During Long Jobs (P3)

**Goal**: Log panel survives SSE disconnect and auto-reconnects, replaying missed log lines from the server-side buffer.

**Independent Test**: quickstart.md S3 — switch tabs during detection, return, verify no log gap. No automated test (frontend JS exemption per Constitution III).

- [X] T020 [US3] In `static/js/pages/processing.js`: extract SSE connection code into a `connectSSE()` function; add module-level `let _sseRetries = 0; const _SSE_MAX_RETRIES = 5; const _SSE_BACKOFF_MS = 3000;`; in `onerror`, replace `startPolling()` fallback with: if `_sseRetries < _SSE_MAX_RETRIES`, increment counter, log "SSE lost — reconnecting (N/5)…", and `setTimeout(connectSSE, _SSE_BACKOFF_MS)`; else log "Connection lost" and fall back to `startPolling()`; inside `onmessage` handler, reset `_sseRetries = 0` on any successful message
- [ ] T021 [US3] Verify via quickstart.md S3: run detection, switch browser tabs for 10s, return, confirm log panel shows recent messages (not blank), and progress bar is still updating

**Checkpoint**: Log panel reconnects after tab switch with no blank state. Scenario S3 passes manually.

---

## Phase 6: User Story 4 — Full Cross-Platform Support (P4)

**Goal**: App installs and runs on macOS, Linux desktop, Linux headless, and Raspberry Pi. Desktop path, tray guard, and minor code cleanup all correct.

**Independent Test**: `pytest tests/test_platform_utils.py -v` → 3 tests pass. Code-inspection for tray guard and launcher comment. quickstart.md S4 on Linux/GNOME.

- [X] T022 [P] [US4] Run `pytest tests/test_platform_utils.py -v` — confirm 3 `get_desktop_path` tests PASS (foundation laid in T002 + T004)
- [X] T023 [US4] In `shell/main_window.py`: delete the `_get_desktop_path()` function (lines 26–38); add `from app.utils.platform import get_desktop_path` import; replace the one `_get_desktop_path()` call site with `get_desktop_path()`; in `__init__` add `self._tray_available = QSystemTrayIcon.isSystemTrayAvailable()`; in `closeEvent`, wrap the `self.hide(); event.ignore()` path with `if self._tray_available and tray and tray.isVisible():`
- [X] T024 [US4] In `app/api/job.py` (**single combined edit pass — covers F5 + F10**): (a) delete the `_get_desktop_path()` function (lines 34–46); (b) add `from app.utils.platform import get_desktop_path` import; (c) replace all `_get_desktop_path()` call sites with `get_desktop_path()`; (d) move `import os` from inside `export_job()` function body to module-level imports at the top of the file [FR-017 / F10]; (e) add prewarm trigger after `POST /api/job/create` success: `try: from app.core import yolo_detector; threading.Thread(target=yolo_detector.prewarm, daemon=True).start() except ImportError: pass` [deferred from T018 / F5]
- [X] T025 [P] [US4] In `launcher.py`: change comment from `# Handle Ctrl+C on Windows` to `# Handle Ctrl+C — Qt blocks Python SIGINT on all platforms without this dummy timer`
- [X] T026 [US4] Run `pytest tests/test_platform_utils.py tests/test_frame_analyzer.py tests/test_yolo_detector.py -v` — confirm all targeted tests still pass after platform refactor

**Checkpoint**: Desktop path tests pass. No circular imports. Tray guard in place. Launcher comment accurate.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: README documentation, full test suite validation, and quickstart scenario confirmation.

- [X] T027 Update `README.md`: add `## Installation by Platform` section with four subsections — macOS (Intel + Apple Silicon, `pip install -r requirements.txt`, imageio-ffmpeg universal binary note), Linux Desktop (Ubuntu 22.04+: `sudo apt install libgl1-mesa-glx libglib2.0-0`, Wayland: `export QT_QPA_PLATFORM=xcb`), Raspberry Pi 64-bit Bookworm (install order: `pip install opencv-python-headless` first, then `pip install -r requirements.txt`; AI disabled on ≤4 GB RAM; YOLO frame-skip auto-enabled; performance expectations), Linux Headless (`uvicorn app.main:app --host 0.0.0.0 --port 5151`, PyQt6 not required)
- [ ] T028 Run full test suite `pytest tests/ -v` — confirm ≥205 tests pass, 0 new failures (baseline: 195 pass before this phase)
- [ ] T029 [P] Run quickstart.md S1 (AI caption quality) and S2 (terminal noise) if Florence-2 weights cached and RAM ≥5 GB
- [ ] T030 [P] Commit all changes with message `fix(011): AI garbage fix, YOLO perf, cross-platform support`

**Checkpoint**: All 30 tasks complete. ≥205 tests pass. quickstart.md scenarios verified.

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (T001–T002)     → no dependencies; start immediately
Phase 2 (T003–T006)     → requires Phase 1 (imports AI_FEATURES_ENABLED, get_desktop_path)
Phase 3 (T007–T013)     → requires Phase 2 tests written and confirmed failing
Phase 4 (T014–T019)     → requires Phase 1 (YOLO_FRAME_SKIP, BATCH_SIZE); independent of Phase 3
Phase 5 (T020–T021)     → independent of Phases 3–4 (pure frontend)
Phase 6 (T022–T026)     → requires Phase 1 (platform.py in place); independent of Phases 3–5
Phase 7 (T027–T030)     → requires Phases 3–6 complete
```

### User Story Dependencies

| Story | Depends On | Can Run Parallel With |
|-------|-----------|----------------------|
| US1 (Florence-2 fix) | Phase 1 + 2 | US2, US3, US4 |
| US2 (YOLO performance) | Phase 1 + 2 | US1, US3, US4 |
| US3 (Log panel) | Phase 1 | US1, US2, US4 |
| US4 (Cross-platform) | Phase 1 + 2 | US1, US2, US3 |

### Within Each User Story

- Tests WRITTEN and CONFIRMED FAILING before implementation (Phases 2–3)
- Config changes before consuming modules (Phase 1 before all)
- Module implementation before API/shell integration (T007–T012 before T018)

---

## Parallel Execution Examples

```bash
# Phase 1 — run together (different files):
T001: app/config.py changes
T002: app/utils/platform.py (new file)

# Phase 2 — run together (different test files):
T003: tests/test_frame_analyzer.py
T004: tests/test_platform_utils.py
T005: tests/test_yolo_detector.py (add one test)

# Phases 3–6 — can run in parallel after Phase 2:
US1: T007–T013  (frame_analyzer.py)
US2: T014–T019  (yolo_detector.py, detection_engine.py, job.py)
US3: T020–T021  (processing.js)
US4: T022–T026  (main_window.py, job.py, launcher.py)
```

---

## Implementation Strategy

### MVP First (US1 — Florence-2 Fix Only)

1. Complete Phase 1 (T001–T002)
2. Complete Phase 2 tests for US1 (T003, T006)
3. Complete US1 (T007–T013)
4. **STOP and VALIDATE**: `pytest tests/test_frame_analyzer.py -v` all pass
5. Ship US1 fix independently if needed

### Full Phase Incremental Delivery

1. Phase 1 + 2 → foundation and tests ready
2. US1 → Florence-2 fix validated
3. US2 → YOLO performance validated
4. US3 → Log panel validated (manual)
5. US4 → Cross-platform validated
6. Phase 7 → Full suite passes

---

## Notes

- `[P]` tasks touch different files — safe to run in parallel
- Constitution Principle III enforced: tests in T003–T005 MUST fail before T007+ implementation
- Frontend JS (T020–T021) exempt from automated test requirement per constitution; documented in quickstart.md S3
- T018 (prewarm trigger) is intentionally deferred to T024 — both job.py edits (US2 prewarm + US4 cleanup) are applied in a SINGLE T024 pass to avoid double-edit conflicts [F5 resolved]
- `_model_ready` must be reset before each new prewarm call if the module is imported fresh per test (use `importlib.reload` or monkeypatch in test T005)
- Commit after each phase completes; never commit broken code to branch
