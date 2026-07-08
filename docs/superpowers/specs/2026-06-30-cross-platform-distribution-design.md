# Cross-Platform Distribution — Design Document

**Date**: 2026-06-30  
**Branch**: `012-cross-platform-dist`  
**Phase**: 12  

---

## Problem

The CCTV Video Processor PC app runs only in developer mode (`python launcher.py`). Non-technical users on Windows, macOS, Linux, and Raspberry Pi cannot install or use it without Python knowledge. AI model weights (Florence-2, CLIP, YOLOv8n) have no first-run setup experience.

---

## Goals

1. Non-technical users double-click an installer and the app is running within minutes.
2. AI model weights download automatically on first launch via a setup wizard.
3. The app works on all four platforms: Windows x64, macOS (Apple Silicon + Intel), Linux x86_64, Raspberry Pi ARM64.
4. Raspberry Pi with 3–4 GB RAM is supported in YOLO-only mode (AI image descriptions disabled gracefully).
5. GitHub Actions CI/CD automatically builds and publishes installers when a `v*.*.*` tag is pushed.

---

## Architecture

```
Platform Installer (.exe / .dmg / .AppImage / .deb)
    └── PyInstaller Bundle
            Python 3.11 + PyQt6 + FastAPI + OpenCV + torch CPU
            + imageio-ffmpeg (bundled ffmpeg) + app code
            + static/ + app/templates/
        └── First-Run Setup Wizard (shell/setup_wizard.py)
                Downloads AI model weights on first launch
            └── Existing App (FastAPI + PyQt6 shell) — unchanged
```

---

## Raspberry Pi 3–4 GB Support

No Pi model has exactly 3 GB RAM. "3 GB Pi" means:
- Pi 4 **4 GB** model → ~3.7 GB usable after OS overhead
- Pi 4 **2 GB** model → ~1.7 GB usable (app launches, tight memory)
- Pi 5 **4 GB** model → ~3.8 GB usable

**Threshold logic** (existing `app/config.py`):
- `AI_FEATURES_ENABLED = _total_gb >= 5.0` — Florence-2 disabled below 5 GB
- `IS_PI = platform.machine().startswith(("aarch64", "armv")) and platform.system() == "Linux"`

**New config constant**: `IS_LOW_RAM_PI: bool = IS_PI and not AI_FEATURES_ENABLED`  
Used by setup wizard to show Pi-specific messaging.

**Behaviour on 3–4 GB Pi**:
- YOLO detection: fully enabled (6 MB model, ~300 MB peak RAM)
- Florence-2 + CLIP: disabled (5 GB minimum enforced by existing check)
- Setup wizard skips Florence-2 + CLIP download, shows: *"Your Pi has 3–4 GB RAM — motion detection with YOLO works great. AI image descriptions require 5 GB+ and are not available on this device."*
- All other features (export, heatmap, reports without AI descriptions, CSV/JSON logs) work normally.

Florence-2 peak inference RAM is ~2.5–3 GB, which would OOM on a 4 GB Pi with OS overhead. The 5 GB threshold is correct and must not be lowered.

---

## Code Changes Required (Fixes Before Packaging)

| # | File | Issue | Fix |
|---|------|--------|-----|
| 1 | `app/main.py:83` | `Path(__file__).parent.parent / "static"` breaks in PyInstaller frozen bundle | Use `get_resource_path("static")` |
| 2 | `app/core/report_renderer.py` | `Path(__file__).parent.parent / "templates"` breaks in bundle | Use `get_resource_path("app/templates")` |
| 3 | `app/core/intel_report_renderer.py` | Same templates path issue | Use `get_resource_path("app/templates")` |
| 4 | `app/core/frame_analyzer.py:75` | `is_available()` ignores `HF_HOME` env var | Check `HF_HOME` → `HUGGINGFACE_HUB_CACHE` → default |
| 5 | `app/core/clip_indexer.py` | `is_available()` only checks import, not disk | Check `~/.cache/clip/ViT-B-32.pt` exists |
| 6 | `shell/tray.py:35` | `DoubleClick` not fired on macOS 13+ Ventura | Use `Trigger` (single click) on `sys.platform == "darwin"` |

---

## New Files

### `app/utils/resource_path.py`
```python
import sys
from pathlib import Path

def get_resource_path(relative: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).parent.parent.parent / relative  # project root
```

### `app/config.py` additions
```python
IS_LOW_RAM_PI: bool = IS_PI and not AI_FEATURES_ENABLED
```

### `shell/setup_wizard.py`
- `QDialog` — appears on first launch (no `~/.cctv_processor/.setup_complete` sentinel)
- `DownloadWorker(QThread)` — downloads models in background thread with progress signals
- Wizard steps: System Check → Download → Done
- On `AI_FEATURES_ENABLED=False` (any platform): skips Florence-2 + CLIP
- On `IS_LOW_RAM_PI=True`: shows Pi-specific RAM message
- "Skip for now" always available — writes sentinel and continues
- `setup_complete() -> bool` and `mark_setup_complete()` are module-level (testable without QDialog)

### Build infrastructure
- `build/cctv_processor_windows.spec` — PyInstaller, onedir, Windows x64
- `build/cctv_processor_macos.spec` — PyInstaller, onedir, macOS BUNDLE
- `build/cctv_processor_linux.spec` — PyInstaller, onedir, Linux x86_64 + aarch64
- `build/windows/installer.iss` — Inno Setup → `.exe`
- `build/macos/create_dmg.sh` — ad-hoc codesign + `hdiutil` → `.dmg`
- `build/linux/create_appimage.sh` — appimageTool → `.AppImage`
- `build/pi/create_deb.sh` — dpkg-deb → `.deb`
- `.github/workflows/release.yml` — 5 parallel build jobs + release job

---

## PyInstaller Key Decisions

- **onedir** (not onefile): PyQt6-WebEngine requires loose data files
- **torch CPU only**: CI installs `pip install torch --index-url https://download.pytorch.org/whl/cpu` before PyInstaller — no CUDA binaries included
- **datas**: `static/`, `app/templates/`, imageio-ffmpeg binaries directory
- **collect_all**: torch, transformers, open_clip, ultralytics, timm
- **excludes**: torch.cuda, torch.distributed, caffe2, matplotlib, scipy, tkinter, IPython

---

## GitHub Actions Matrix

| Job | Runner | Output | Trigger |
|-----|--------|--------|---------|
| `build-windows` | `windows-latest` | `CCTV-Processor-vX.Y.Z-win64-setup.exe` | tag `v*.*.*` |
| `build-macos-arm` | `macos-14` | `CCTV-Processor-vX.Y.Z-macos-arm64.dmg` | tag `v*.*.*` |
| `build-macos-intel` | `macos-13` | `CCTV-Processor-vX.Y.Z-macos-intel.dmg` | tag `v*.*.*` |
| `build-linux` | `ubuntu-22.04` | `CCTV-Processor-vX.Y.Z-linux-x86_64.AppImage` | tag `v*.*.*` |
| `build-pi` | `ubuntu-latest` + QEMU aarch64 | `CCTV-Processor-vX.Y.Z-pi-arm64.deb` | manual dispatch (slow) |
| `release` | `ubuntu-latest` | GitHub Release with all artifacts | after all builds |

Pi build is a **separate manual-dispatch workflow** (`release-pi.yml`) to avoid blocking regular releases (QEMU ARM64 build takes 45–90 min).

---

## Installer Size Estimates

| Platform | Installer Size | First-Run Download |
|----------|---------------|-------------------|
| Windows x64 | ~1.5–2 GB | ~1 GB model weights |
| macOS (arm64 + intel) | ~1.5–2 GB each | ~1 GB model weights |
| Linux x86_64 | ~1.5–2 GB | ~1 GB model weights |
| Pi ARM64 (4 GB model) | ~1.5 GB | YOLOv8n 6 MB only |

Pi installer includes torch CPU because ultralytics (YOLOv8n) requires it. The first-run wizard skips Florence-2 and CLIP downloads on Pi with < 5 GB RAM, so the post-install download is only 6 MB (YOLOv8n weights).

---

## Testing

- `tests/test_resource_path.py` — dev mode vs frozen mode path resolution
- `tests/test_setup_wizard.py` — pure-Python: sentinel logic, AI skip on low RAM
- `tests/test_frame_analyzer.py` additions — HF_HOME env var honoured
- `tests/test_clip_indexer.py` additions — disk presence check (not just import)

---

## What Does NOT Change

- Existing `IS_PI`, `AI_FEATURES_ENABLED`, `get_desktop_path()`, `open_folder()` — already correct
- `imageio-ffmpeg` — already bundles platform-specific static ffmpeg binary, zero work needed
- `app/utils/ffmpeg_path.py` — already handles frozen bundle via `shutil.which` fallback
- All detection logic, export engine, session state, API endpoints — unchanged
