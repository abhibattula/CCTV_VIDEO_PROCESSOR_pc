# Quickstart & Verification Scenarios

**Feature**: `012-cross-platform-dist`  
**Date**: 2026-06-30

These scenarios verify the feature works end-to-end. Run them after implementation, in order.

---

## Scenario 1: Resource Path Utility — Dev Mode

**Goal**: Confirm `get_resource_path()` returns the correct project root path in normal dev mode.

**Steps**:
1. From the project root (no PyInstaller bundle): `python -c "from app.utils.resource_path import get_resource_path; p = get_resource_path('static'); print(p, p.exists())"`
2. Expected output: `<project_root>/static True`

**Pass criteria**: Path ends with `/static` and `p.exists()` is `True`.

---

## Scenario 2: Resource Path Utility — Frozen Mode (via pytest)

**Goal**: Confirm `get_resource_path()` uses `sys._MEIPASS` when `sys.frozen` is set.

**Steps**:
1. `pytest tests/test_resource_path.py -v`
2. Expected: all tests pass, including `test_frozen_mode_uses_meipass`

**Pass criteria**: 0 failures.

---

## Scenario 3: Florence-2 HF_HOME Respected

**Goal**: Confirm `FrameAnalyzer.is_available()` checks the custom HF_HOME path.

**Steps**:
1. `pytest tests/test_frame_analyzer.py -v -k "hf_home"` 
2. Expected: `test_is_available_respects_hf_home` passes

**Pass criteria**: Test passes without touching `~/.cache/huggingface/`.

---

## Scenario 4: CLIP Disk Presence Check

**Goal**: Confirm `ClipIndexer.is_available()` returns False when weights file is absent.

**Steps**:
1. `pytest tests/test_clip_indexer.py -v -k "disk_presence"`
2. Expected: `test_is_available_requires_disk_file` passes (returns False when `.pt` absent)

**Pass criteria**: Test passes; no download initiated during test.

---

## Scenario 5: Setup Wizard — Sentinel Logic

**Goal**: Confirm wizard shows on first launch, skips on subsequent launches.

**Steps**:
1. `pytest tests/test_setup_wizard.py -v`
2. Expected: all tests pass including `test_sentinel_controls_wizard_display`

**Pass criteria**: 0 failures.

---

## Scenario 6: Setup Wizard — Low RAM Pi Gate

**Goal**: Confirm wizard skips Florence-2 and CLIP on devices with `AI_FEATURES_ENABLED=False`.

**Steps**:
1. `pytest tests/test_setup_wizard.py -v -k "low_ram"` 
2. Expected: `test_download_skips_heavy_models_on_low_ram` passes — only YOLOv8n download triggered

**Pass criteria**: Test verifies exactly 1 model downloaded (YOLOv8n), not 3.

---

## Scenario 7: macOS Tray Single-Click (Manual — macOS only)

**Goal**: Confirm tray icon restores window on single-click on macOS 13+.

**Steps**:
1. `python launcher.py`
2. Minimize the window to tray
3. Single-click the tray icon
4. Expected: window restores

**Pass criteria**: Window appears on single-click (not double-click required).
Note: Document this scenario in `quickstart.md` per Principle III frontend exemption pattern for manual verification.

---

## Scenario 8: Full Application Still Works After Code Fixes

**Goal**: Regression check — confirm all 6 fixes don't break existing functionality.

**Steps**:
1. `pytest tests/ -v --ignore=tests/test_resource_path.py --ignore=tests/test_setup_wizard.py`
2. Expected: ≥208 tests pass (all existing tests)

**Pass criteria**: Same pass count as before this phase (208+), 0 regressions.

---

## Scenario 9: PyInstaller Build Smoke Test (Local Windows)

**Goal**: Confirm the Windows `.spec` file produces a working bundle.

**Prerequisites**: Clean venv with CPU-only torch, PyInstaller installed.

**Steps**:
1. `pip install torch --index-url https://download.pytorch.org/whl/cpu`
2. `pip install pyinstaller -r requirements.txt`
3. `pyinstaller build/cctv_processor_windows.spec`
4. Run `dist/CCTV-Video-Processor/launcher.exe`
5. Expected: browser UI loads, no "static files not found" error

**Pass criteria**: App starts, index.html loads in QWebEngineView.

---

## Scenario 10: Wizard Shown on First Launch, Skipped on Second

**Manual integration test** (run after Scenario 9):

**Steps**:
1. Delete `~/.cctv_processor/.setup_complete` if it exists
2. Run the installer or `dist/.../launcher.exe`
3. Expected: Setup wizard appears before main window
4. Click "Skip for now"
5. Expected: Main window opens; wizard does not appear
6. Close and relaunch
7. Expected: Wizard does NOT appear — goes straight to main window

**Pass criteria**: Wizard appears exactly once; sentinel persists across launches.

---

## Scenario 11: GitHub Actions CI — Tag Push

**Goal**: Confirm all 4 platform builds trigger on `v*.*.*` tag.

**Steps**:
1. Push a test tag: `git tag v0.0.1-test && git push origin v0.0.1-test`
2. Check GitHub Actions tab
3. Expected: `build-windows`, `build-macos-arm`, `build-macos-intel`, `build-linux` jobs start; `build-pi` does NOT start (separate manual workflow)
4. After all jobs complete: GitHub Release created with 4 installer artifacts

**Pass criteria**: All 4 artifacts appear on the Release within 60 minutes.
