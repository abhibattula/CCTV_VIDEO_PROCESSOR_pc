# Implementation Plan: Cross-Platform Distribution

**Branch**: `012-cross-platform-dist` | **Date**: 2026-06-30 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/012-cross-platform-dist/spec.md`

## Summary

Package the CCTV Video Processor PC app as self-contained installers for Windows (.exe via Inno Setup), macOS (.dmg, arm64 + intel), Linux (.AppImage), and Raspberry Pi (.deb), with a first-run QDialog wizard that downloads AI model weights. Six pre-packaging code bugs are fixed first: frozen-bundle resource paths (3 files), Florence-2 HF_HOME env var, CLIP disk presence check, and macOS 13+ tray single-click. GitHub Actions CI/CD on `v*.*.*` tag push builds all installers; Pi is a separate manual-dispatch workflow (45–90 min QEMU build).

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: PyInstaller 6.x, PyQt6 6.x, FastAPI, torch CPU (no CUDA), imageio-ffmpeg, transformers, open_clip, ultralytics, Inno Setup (Windows), appimageTool (Linux), dpkg-deb (Pi), hdiutil + codesign (macOS)  
**Storage**: `~/.cctv_processor/` user data dir (Principle I pre-approved exemption); `.setup_complete` sentinel; model weights at `~/.cctv_processor/models/`  
**Testing**: pytest, `monkeypatch` for `sys.frozen` / `sys._MEIPASS`; no QDialog instantiated in tests  
**Target Platform**: Windows 10+ x64, macOS 12+ arm64 + intel, Ubuntu 20.04+ x86_64, Pi OS Bookworm ARM64  
**Project Type**: Desktop app packaging + CI/CD pipeline  
**Performance Goals**: Wizard shows first download progress within 3 s; full wizard completes at network speed; app launches within 5 s after install  
**Constraints**: No Apple Developer Account (ad-hoc signing only); PyInstaller `--onedir` required by PyQt6-WebEngine; torch CPU only (saves ~3 GB); Pi QEMU build 45–90 min → separate manual-dispatch workflow  
**Scale/Scope**: 5 platform installers, 1 setup wizard dialog, 6 source code fixes, 2 GitHub Actions workflows, ~10 new build files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

1. **Principle I (Session-First, No Persistence)**: Setup sentinel `~/.cctv_processor/.setup_complete` is user configuration — records a one-time user action (completing setup), no reference to any specific job, written only once on explicit user action (clicking Download or Skip). Falls under the pre-approved Principle I exemption. ✓ PASS

2. **Principle II (Cross-Platform by Default)**: `get_resource_path()` returns `Path` objects. All new file operations use `pathlib.Path`. OS detection permitted only for macOS tray quirk (Principle II exception: OS-specific behaviour). No bare `"ffmpeg"` strings added. ✓ PASS

3. **Principle III (Test-First)**: `tests/test_resource_path.py` and `tests/test_setup_wizard.py` written before their implementation files. `DownloadWorker` logic tested via pure-Python monkeypatching; no QDialog instantiated in tests. HF_HOME and disk-presence tests added before fixing production code. Frontend JS exemption does not apply — this is pure Python. ✓ PASS (order enforced in tasks.md)

4. **Principle IV (Callback-Driven)**: Setup wizard never imports or mutates `app/session.py`. Qt signals on `DownloadWorker` serve the same decoupling purpose as callbacks. Detection engines unchanged. ✓ PASS

5. **Principle V (Simplicity & YAGNI)**: One thin `get_resource_path()` utility replaces three broken path patterns. PyInstaller `.spec` files are static configurations. Wizard has exactly 3 steps (system check → download → done). No auto-update mechanism (not in scope). ✓ PASS

*Post-design re-check*: All five gates still pass after Phase 1 design. No violations detected.

## Project Structure

### Documentation (this feature)

```text
specs/012-cross-platform-dist/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── wizard.md        # Setup wizard Python interface contract
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
app/
├── utils/
│   └── resource_path.py          # NEW: frozen-bundle path resolver
├── core/
│   ├── frame_analyzer.py         # FIX: HF_HOME env var in is_available()
│   └── clip_indexer.py           # FIX: disk-presence check in is_available()
├── main.py                       # FIX: static/ served via get_resource_path()
└── config.py                     # ADD: IS_LOW_RAM_PI constant

shell/
├── setup_wizard.py               # NEW: first-run AI model download wizard
└── tray.py                       # FIX: macOS 13+ Trigger vs DoubleClick

launcher.py                       # MODIFY: show wizard before MainWindow

build/
├── cctv_processor_windows.spec   # NEW: PyInstaller spec, Windows x64
├── cctv_processor_macos.spec     # NEW: PyInstaller spec, macOS BUNDLE
├── cctv_processor_linux.spec     # NEW: PyInstaller spec, Linux + Pi ARM64
├── windows/
│   └── installer.iss             # NEW: Inno Setup → .exe installer
├── macos/
│   └── create_dmg.sh             # NEW: ad-hoc codesign + hdiutil → .dmg
├── linux/
│   └── create_appimage.sh        # NEW: appimageTool → .AppImage
└── pi/
    └── create_deb.sh             # NEW: dpkg-deb → .deb package

.github/
└── workflows/
    ├── release.yml               # NEW: tag-triggered multi-platform CI/CD
    └── release-pi.yml            # NEW: manual-dispatch Pi ARM64 build

tests/
├── test_resource_path.py         # NEW: dev mode + frozen mode path tests
├── test_setup_wizard.py          # NEW: sentinel logic, RAM gate, skip flow
├── test_frame_analyzer.py        # ADD: HF_HOME env var coverage
└── test_clip_indexer.py          # ADD: disk-presence coverage
```

**Structure Decision**: Single project (Option 1). All new files integrate directly into the existing repository following its established module layout (`app/`, `shell/`, `tests/`, `build/`, `.github/`).

## Complexity Tracking

> *No constitution violations require justification. This section is informational.*

All five principles pass. Sentinel file is pre-approved under Principle I. OS detection in `tray.py` is explicitly permitted under Principle II for OS-specific UI quirks.
