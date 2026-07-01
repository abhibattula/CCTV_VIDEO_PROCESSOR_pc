# Tasks: Cross-Platform Distribution

**Input**: Design documents from `/specs/012-cross-platform-dist/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/wizard.md ✓, quickstart.md ✓

**TDD Note**: Principle III is active — for all `app/` and `shell/` Python code, test tasks are written FIRST and must fail before implementation tasks run. Build infrastructure files (PyInstaller specs, shell scripts, GitHub Actions YAML) have no automated tests — they are verified by quickstart scenarios.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story this task belongs to (US1–US5)
- Setup and Foundational phases have no story labels

---

## Phase 1: Setup (Build Directory Scaffolding)

**Purpose**: Create the new directory structure required by the build system

- [ ] T001 Create build/ subdirectory tree: `build/windows/`, `build/macos/`, `build/linux/`, `build/pi/` (can use Write tool to create placeholder files in each)

---

## Phase 2: Foundational — Code Fixes + Setup Wizard (Blocking)

**Purpose**: Fix all 6 pre-packaging bugs and implement the setup wizard. ALL platform builds (US1–US5) depend on these being complete.

**⚠️ CRITICAL**: No platform packaging work can begin until this phase is complete.

**TDD order within this phase**: Write test → verify it fails → implement → verify it passes.

### 2a. Resource Path Utility (Fix #1: frozen-bundle paths)

- [ ] T002 Write failing tests for `get_resource_path()` in `tests/test_resource_path.py`: test dev-mode returns project root path that exists; test frozen-mode (monkeypatch `sys.frozen=True`, `sys._MEIPASS=str(tmp_path)`) returns path under `_MEIPASS`; test cleanup removes `sys.frozen` and `sys._MEIPASS` attrs. Run to confirm 3 failures.
- [ ] T003 Implement `app/utils/resource_path.py`: `get_resource_path(relative: str) -> Path` — returns `Path(sys._MEIPASS) / relative` when frozen, `Path(__file__).parent.parent.parent / relative` otherwise. Run T002 tests to confirm they pass.
- [ ] T004 [P] Fix `app/main.py`: import `get_resource_path` from `app.utils.resource_path`; replace the `Path(__file__).parent.parent / "static"` line (~line 83) with `get_resource_path("static")`. Verify `static_root` and `_index` variables are updated consistently.
- [ ] T005 [P] Fix `app/core/report_renderer.py`: import `get_resource_path`; replace `Path(__file__).parent.parent / "templates"` (or equivalent) with `get_resource_path("app/templates")`. Assign to `_TEMPLATES_DIR` constant used by `jinja2.FileSystemLoader`.
- [ ] T006 [P] Fix `app/core/intel_report_renderer.py`: same change as T005 — import `get_resource_path`; replace hardcoded `__file__`-relative templates path with `get_resource_path("app/templates")`.

### 2b. Florence-2 HF_HOME Fix (Fix #4)

- [ ] T007 [P] Add HF_HOME test to `tests/test_frame_analyzer.py`: `test_is_available_respects_hf_home` — monkeypatch `HF_HOME` env var to a temp dir containing the `hub/models--microsoft--Florence-2-base` path; assert `FrameAnalyzer.is_available()` returns True; also test returns False when path absent. Clear `_availability_cache` between cases. Run to confirm failure.
- [ ] T008 Fix `app/core/frame_analyzer.py` `is_available()`: replace the hardcoded `weights_dir = Path.home() / ".cache" / "huggingface" / "hub" / "models--microsoft--Florence-2-base"` (~line 74-76) with env-var chain: `_hf_home = os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE") or str(Path.home() / ".cache" / "huggingface")` then `weights_dir = Path(_hf_home) / "hub" / "models--microsoft--Florence-2-base"`. Add `import os` at top of file if not present. Reset `_availability_cache` to None after the fix. Run T007 tests to confirm they pass.

### 2c. CLIP Disk-Presence Fix (Fix #5)

- [ ] T009 [P] Add disk-presence tests to `tests/test_clip_indexer.py`: `test_is_available_requires_disk_file` — monkeypatch `XDG_CACHE_HOME` or `CLIP_CACHE_DIR` to temp dir; assert `ClipIndexer.is_available()` returns False when `ViT-B-32.pt` absent; create dummy file and assert returns True (with `open_clip` importable; skip if not installed). Run to confirm failure.
- [ ] T010 Fix `app/core/clip_indexer.py` `is_available()`: replace the current body (which only checks `import open_clip`) with: try import, then resolve `cache_root` via `CLIP_CACHE_DIR` env var → `XDG_CACHE_HOME/clip` → `~/.cache/clip`, then return `(cache_root / "ViT-B-32.pt").exists()`. Add `import os` at top. Run T009 tests to confirm they pass.

### 2d. macOS Tray Fix (Fix #6)

- [ ] T011 [P] Fix `shell/tray.py` `_on_activated()` method: import `sys` at top of file; in `_on_activated`, add platform branch — on `sys.platform == "darwin"` check for `ActivationReason.Trigger` (single-click), otherwise keep existing `ActivationReason.DoubleClick` check. (Verified manually via quickstart scenario 7 — macOS tray manual test.)

### 2e. Config Constant (IS_LOW_RAM_PI)

- [ ] T012 [P] Add `IS_LOW_RAM_PI: bool = IS_PI and not AI_FEATURES_ENABLED` to `app/config.py` immediately after the `AI_FEATURES_ENABLED` definition. No new imports needed.

### 2f. Setup Wizard (TDD)

- [ ] T013 Write failing tests in `tests/test_setup_wizard.py` (no QDialog/QApplication needed): `test_setup_complete_false_when_sentinel_absent` — mock sentinel path to nonexistent file; `test_setup_complete_true_after_mark` — call `mark_setup_complete()` in tmp dir, assert `setup_complete()` returns True; `test_mark_setup_complete_idempotent` — call twice, no error; `test_download_worker_skips_heavy_models_on_low_ram` — monkeypatch `AI_FEATURES_ENABLED=False`, assert worker model list contains only YOLOv8n; `test_download_worker_retries_on_sha256_mismatch` — mock download returning wrong hash, assert retries ≤3 then emits finished(False); `test_download_worker_skips_existing_valid_file` — pre-create dest file with correct SHA256, assert download not triggered, emits finished(True). Run all to confirm failures.
- [ ] T014 Implement `shell/setup_wizard.py`: module-level `_SENTINEL = Path.home() / ".cctv_processor" / ".setup_complete"`, `setup_complete() -> bool`, `mark_setup_complete() -> None`; `DownloadWorker(QThread)` with `progress = pyqtSignal(str, int)`, `log_line = pyqtSignal(str)`, `finished = pyqtSignal(bool, str)`, `run()` method downloading models sequentially with SHA256 verify + 3-retry logic; `SetupWizard(QDialog)` with 3-step layout (System Check → Downloading → Done), Skip button always visible, calls `mark_setup_complete()` on any exit path. Import `IS_LOW_RAM_PI`, `AI_FEATURES_ENABLED` from `app.config`. Run T013 tests to confirm they pass.
- [ ] T015 Integrate wizard into `launcher.py`: add `from shell.setup_wizard import SetupWizard, setup_complete` import; after `QApplication` is created and before `MainWindow` is instantiated, add `if not setup_complete(): wizard = SetupWizard(); wizard.exec()`. Verify existing tests still pass.

### 2g. Regression Gate

- [ ] T016 Run `pytest tests/ -v` and confirm all ≥208 existing tests pass plus all new tests added in T002, T007, T009, T013 pass. Zero regressions allowed before proceeding to platform packaging.

---

## Phase 3: User Story 1 — Windows Install (Priority: P1) 🎯 MVP

**Goal**: Non-technical Windows users can download an `.exe` installer, install the app, and run the first-run wizard without touching a terminal.

**Independent Test**: Run the built `.exe` on a clean Windows 11 VM with no Python; confirm app starts, wizard appears, Skip works, main window opens (quickstart scenario 9).

- [ ] T017 [US1] Create `build/cctv_processor_windows.spec`: PyInstaller onedir spec for Windows x64. Include: `Analysis(['launcher.py'], ...)`, `datas=[('../static', 'static'), ('../app/templates', 'app/templates')]` plus `collect_all('imageio_ffmpeg')`, `collect_all('torch')`, `collect_all('transformers')`, `collect_all('open_clip')`, `collect_all('ultralytics')`. `excludes=['torch.cuda', 'torch.distributed', 'caffe2', 'matplotlib', 'scipy', 'tkinter', 'IPython']`. `hiddenimports=['uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'aiofiles', 'fastapi', 'PyQt6.QtPrintSupport', 'imageio_ffmpeg']`. Output name: `CCTV-Video-Processor`.
- [ ] T018 [US1] Create `build/windows/installer.iss`: Inno Setup 6 script. `[Setup]` section: `AppName=CCTV Video Processor`, `AppVersion={#AppVersion}` (passed via `/DAppVersion=x.y.z`), `DefaultDirName={autopf}\CCTV Video Processor`, `DefaultGroupName=CCTV Video Processor`, `OutputBaseFilename=CCTV-Processor-{#AppVersion}-win64-setup`, `Compression=lzma2/ultra64`, `SolidCompression=yes`. `[Files]`: recursive source from `..\dist\CCTV-Video-Processor\*`. `[Icons]`: Desktop shortcut + Start Menu entry pointing to `launcher.exe`. `[Run]`: optional post-install launch.

**Checkpoint**: Windows packaging complete. Can run `pyinstaller build/cctv_processor_windows.spec` then `iscc build/windows/installer.iss /DAppVersion=dev` locally for smoke test (quickstart scenario 9).

---

## Phase 4: User Story 2 — Raspberry Pi Install (Priority: P2)

**Goal**: Pi users install a `.deb` with `sudo dpkg -i`, app starts in YOLO-only mode on 4 GB Pi, shows Pi-specific RAM message in wizard.

**Independent Test**: Install `.deb` on Pi 4 4 GB Pi OS Bookworm; confirm app launches, wizard shows Pi message, YOLO detection works (quickstart scenario independent: verify T012's `IS_LOW_RAM_PI` flag drives wizard messaging).

- [ ] T019 [US2] Create `build/cctv_processor_linux.spec`: PyInstaller onedir spec for Linux x86_64 and aarch64. Same structure as T017 but `name='CCTV-Video-Processor'`, console=False (no terminal window). On CI the aarch64 variant is built inside the QEMU container using this same spec file. Add `DISPLAY=:99` note in comment for CI Xvfb requirement.
- [ ] T020 [US2] Create `build/pi/create_deb.sh`: shell script that wraps the PyInstaller onedir output into a `.deb`. Creates `DEBIAN/control` (Package: cctv-processor, Version: $1, Architecture: arm64, Depends: libc6, Description: CCTV Video Processor), `usr/local/bin/cctv-processor` launcher symlink, `usr/share/applications/cctv-processor.desktop` file. Calls `dpkg-deb --build deb_root "CCTV-Processor-${VERSION}-pi-arm64.deb"`. Usage: `./create_deb.sh 1.0.0`.

**Checkpoint**: Pi packaging script complete. Tested in CI via QEMU aarch64 action.

---

## Phase 5: User Story 3 — macOS Install (Priority: P3)

**Goal**: macOS users (arm64 + intel) drag app from `.dmg` to Applications, bypass Gatekeeper once with right-click → Open, wizard runs normally.

**Independent Test**: Open `.dmg` on macOS 13+ arm64 (and separately on intel runner), drag to Applications, right-click → Open, confirm wizard appears and window restores on single tray click (quickstart scenario 7).

- [ ] T021 [US3] Create `build/cctv_processor_macos.spec`: PyInstaller onedir spec for macOS BUNDLE. `BUNDLE(exe, name='CCTV Video Processor.app', icon=None, bundle_identifier='com.cctvprocessor.app')`. Same datas and collect_all as T017. `codesign_identity=None` (ad-hoc signing done by create_dmg.sh). Include `Info.plist` keys: `NSHighResolutionCapable=True`, `NSRequiresAquaSystemAppearance=False`.
- [ ] T022 [US3] Create `build/macos/create_dmg.sh`: shell script that ad-hoc signs and packages the `.app` into a `.dmg`. Steps: (1) `xattr -cr "dist/CCTV Video Processor.app"`, (2) `codesign --sign - --force --deep --preserve-metadata=entitlements "dist/CCTV Video Processor.app"`, (3) `hdiutil create -volname "CCTV Video Processor" -srcfolder "dist/CCTV Video Processor.app" -ov -format UDZO "CCTV-Processor-${VERSION}-${ARCH}.dmg"`. Usage: `./create_dmg.sh 1.0.0 arm64`.

**Checkpoint**: macOS DMG creation script complete. Both arm64 (macos-14 runner) and intel (macos-13 runner) use this same script with `ARCH` env var.

---

## Phase 6: User Story 4 — Linux Install (Priority: P4)

**Goal**: Linux x86_64 users mark `.AppImage` executable and double-click to run — no installation or dependencies required.

**Independent Test**: Download `.AppImage` on Ubuntu 22.04, `chmod +x`, run, confirm wizard appears and video detection works (quickstart scenario independent: same wizard flow as US1).

- [ ] T023 [US4] Create `build/linux/create_appimage.sh`: shell script that wraps PyInstaller onedir output into an AppImage. Steps: (1) Create `AppDir/` tree with `usr/bin/` containing the PyInstaller output, (2) create `AppDir/CCTV-Video-Processor.desktop` (.desktop file with Name, Exec, Icon, Categories), (3) create `AppDir/AppRun` launcher script (sets `LD_LIBRARY_PATH`, exec the binary), (4) download `appimageTool-x86_64.AppImage` if not present, (5) `./appimageTool-x86_64.AppImage AppDir "CCTV-Processor-${VERSION}-linux-x86_64.AppImage"`. Usage: `./create_appimage.sh 1.0.0`.

**Checkpoint**: Linux AppImage creation script complete. Uses same `cctv_processor_linux.spec` from T019.

---

## Phase 7: User Story 5 — CI/CD (Priority: P5)

**Goal**: Pushing a `v*.*.*` git tag automatically builds all 4 platform installers and publishes them as GitHub Release assets.

**Independent Test**: Push `v0.0.1-test` tag, confirm 4 build jobs start, artifacts uploaded to GitHub Release within 60 minutes. Pi build triggered separately via manual dispatch (quickstart scenario 11).

- [ ] T024 [US5] Create `.github/workflows/release.yml`: trigger on `push: tags: ['v*.*.*']`. Jobs: `build-windows` (runner: `windows-latest`) — install CPU torch, run `pyinstaller build/cctv_processor_windows.spec`, run `iscc`, upload artifact; `build-macos-arm` (runner: `macos-14`) — same pattern, run `./build/macos/create_dmg.sh $VERSION arm64`; `build-macos-intel` (runner: `macos-13`) — same, `arm64` → `intel`; `build-linux` (runner: `ubuntu-22.04`) — install xvfb, `Xvfb :99 &`, `DISPLAY=:99`, run PyInstaller, `./build/linux/create_appimage.sh $VERSION`; `release` job (runs after all builds, runner: `ubuntu-latest`) — `softprops/action-gh-release@v1` to create Release, attach all 4 artifacts, auto-generate release notes from commits. Each build job is `fail-fast: false` so a failure on one platform does not cancel others.
- [ ] T025 [US5] Create `.github/workflows/release-pi.yml`: trigger on `workflow_dispatch` (manual only) with input `version` (string). Single job using `uraimo/run-on-arch-action@v2` with `arch: aarch64`, `distro: bookworm`. Steps: checkout, install CPU torch for aarch64, `pyinstaller build/cctv_processor_linux.spec`, `./build/pi/create_deb.sh ${{ inputs.version }}`, upload artifact to the GitHub Release matching the version tag.

**Checkpoint**: CI/CD complete. All platform builds automated on tag push; Pi build available as separate manual workflow.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation, and verification that the complete feature works end-to-end.

- [ ] T026 [P] Run `pytest tests/ -v` and confirm all tests pass (≥208 existing + new tests from T002, T007, T009, T013). Record final count.
- [ ] T027 Run quickstart.md scenarios 1–8 (all automated scenarios): resource path dev mode, resource path frozen mode (via pytest), HF_HOME test, CLIP disk presence test, wizard sentinel logic, wizard low-RAM gate, regression check (all existing tests). Confirm all pass.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1. BLOCKS all platform phases.
  - Within Phase 2: TDD order enforced — T002 before T003, T007 before T008, T009 before T010, T013 before T014, T014 before T015
  - T016 (regression gate) must pass before any Phase 3+ task
- **Phase 3 (US1 Windows)**: Depends on Phase 2 complete
- **Phase 4 (US2 Pi)**: Depends on Phase 2 complete; can run in parallel with Phase 3
- **Phase 5 (US3 macOS)**: Depends on Phase 2 complete; can run in parallel with Phases 3–4
- **Phase 6 (US4 Linux)**: Depends on T019 (Linux spec from Phase 4); can run after T019
- **Phase 7 (US5 CI/CD)**: Depends on all build scripts (T017–T023) existing; can start after Phase 3
- **Phase 8 (Polish)**: Depends on all user story phases complete

### Within Phase 2 (TDD order)

```
T002 (write resource_path tests) → T003 (implement resource_path)
  → T004 [P] (fix main.py)
  → T005 [P] (fix report_renderer.py)
  → T006 [P] (fix intel_report_renderer.py)
T007 [P] (write HF_HOME tests) → T008 (fix frame_analyzer)
T009 [P] (write CLIP tests) → T010 (fix clip_indexer)
T011 [P] (add IS_LOW_RAM_PI to config)
T012 [P] (fix tray.py)
T013 (write wizard tests) → T014 (implement wizard) → T015 (integrate launcher)
T016 (regression gate — all must pass)
```

### User Story Dependencies

- **US1 (Windows)**: No dependency on US2–US5
- **US2 (Pi)**: No dependency on US1; T019 (Linux spec) also used by US4
- **US3 (macOS)**: No dependency on US1–US2
- **US4 (Linux)**: Depends on T019 from US2 (shared spec)
- **US5 (CI/CD)**: References artifacts from US1–US4 (T017–T023)

---

## Parallel Opportunities

### Phase 2 Parallel Execution

```bash
# Group 1 (after T003 completes):
T004: Fix app/main.py static path
T005: Fix app/core/report_renderer.py templates path
T006: Fix app/core/intel_report_renderer.py templates path

# Group 2 (concurrent with Group 1, different files):
T007: Write HF_HOME tests
T009: Write CLIP disk-presence tests  
T011: Add IS_LOW_RAM_PI to config.py
T012: Fix tray.py macOS trigger

# After Group 1+2:
T008: Fix frame_analyzer.py (after T007)
T010: Fix clip_indexer.py (after T009)

# Wizard (after T011, T012):
T013: Write wizard tests
→ T014: Implement wizard
→ T015: Integrate launcher
```

### Phase 3–6 Parallel (after T016 regression gate)

```bash
# Can all proceed simultaneously (independent files):
T017: Windows .spec
T018: installer.iss
T019: Linux/Pi .spec
T020: create_deb.sh
T021: macOS .spec
T022: create_dmg.sh
T023: create_appimage.sh

# After T019 complete:
T023: create_appimage.sh (uses Linux spec)

# After all T017-T023:
T024: release.yml
T025: release-pi.yml
```

---

## Parallel Example: Phase 2 Code Fixes

```
Agent A: T002 (write resource_path tests) → T003 (implement) → T004 (fix main.py)
Agent B: T007 (write HF_HOME tests) → T008 (fix frame_analyzer)
Agent C: T009 (write CLIP tests) → T010 (fix clip_indexer)
Agent D: T011 (IS_LOW_RAM_PI) + T012 (tray fix)
All agents join → T013 (wizard tests) → T014 (wizard) → T015 (launcher) → T016 (gate)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only — Windows Install)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: All code fixes + wizard (T002–T016) — **CRITICAL: blocks all packaging**
3. Complete Phase 3: Windows spec + Inno Setup (T017–T018)
4. **STOP and VALIDATE**: Run `pyinstaller build/cctv_processor_windows.spec` locally; smoke test the output
5. Demo Windows installer to confirm end-to-end flow

### Incremental Delivery

1. Phase 2 complete → All 6 bugs fixed, wizard works, regression tests pass
2. Phase 3 complete → Windows installer available (MVP for non-technical users)
3. Phase 4 complete → Pi `.deb` available (core home-security use case)
4. Phase 5 complete → macOS `.dmg` available
5. Phase 6 complete → Linux `.AppImage` available
6. Phase 7 complete → CI/CD automated on every `v*.*.*` tag
7. Phase 8 complete → All verification scenarios documented and passing

---

## Notes

- `[P]` tasks touch different files and have no dependency on each other — safe to run in parallel
- Principle III: ALL `app/` and `shell/` Python changes require a failing test written first
- Build infrastructure files (`.spec`, `.iss`, `.sh`, `.yml`) have no automated tests — verified by quickstart scenarios
- Never include CUDA in torch: always install with `--index-url https://download.pytorch.org/whl/cpu`
- `sys.frozen` monkeypatch: ALWAYS clean up with `monkeypatch.delattr(sys, "frozen", raising=False)` in test teardown
- Wizard tests MUST NOT instantiate `QDialog` or `QApplication`
- The wizard `exec()` always returns — it never blocks the main window from appearing
- All 6 code fixes are in Phase 2 (Foundational) because even one missed fix would break the frozen bundle
