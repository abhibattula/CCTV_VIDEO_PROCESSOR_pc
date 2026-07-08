# Research: Cross-Platform Distribution

**Feature**: `012-cross-platform-dist`  
**Date**: 2026-06-30

---

## 1. PyInstaller + PyQt6-WebEngine: onedir vs onefile

**Decision**: Use `--onedir` (directory bundle), not `--onefile`.

**Rationale**: PyQt6-WebEngine requires loose `.pak`, `.dat`, and `.so`/`.dll` data files at predictable relative paths beside the main executable. The `--onefile` mode extracts everything to a temp directory on each launch (~10 s startup penalty) and QtWebEngine cannot reliably locate its resource files in that layout. `--onedir` produces a folder that installers (Inno Setup, AppImage, dpkg) can wrap directly.

**Alternatives considered**: `--onefile` — rejected (startup penalty + QtWebEngine resource path failures confirmed in PyInstaller #6083).

---

## 2. `sys._MEIPASS` and Resource Path Resolution

**Decision**: New utility `app/utils/resource_path.py` with `get_resource_path(relative: str) -> Path`.

**Rationale**: In a frozen bundle, `__file__` resolves to the extracted temp path, so `Path(__file__).parent.parent / "static"` produces a path that does not exist. PyInstaller sets `sys._MEIPASS` to the bundle root in `--onedir` mode; `sys.frozen` is set to `True`. The utility checks these attributes and falls back to project root in dev mode.

```python
def get_resource_path(relative: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).parent.parent.parent / relative  # project root
```

**Three callers to fix**:
- `app/main.py:83` — `static/` directory for the FastAPI static files mount
- `app/core/report_renderer.py` — Jinja2 `FileSystemLoader` templates dir
- `app/core/intel_report_renderer.py` — same Jinja2 templates dir

**Test strategy**: `monkeypatch.setattr(sys, "frozen", True)` + `monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path))` to simulate frozen mode without actually building.

---

## 3. torch CPU-Only Build

**Decision**: Install `torch` from the CPU-only wheel index before running PyInstaller.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

**Rationale**: The default `pip install torch` includes CUDA binaries (~3 GB). CPU-only wheel is ~900 MB. Since the app never calls CUDA (all inference runs on CPU), including CUDA wastes ~2.1 GB of installer size with no benefit.

**PyInstaller spec excludes**: `torch.cuda`, `torch.distributed`, `caffe2`, `torch.backends.cudnn` to strip any lingering CUDA references even after the CPU-only install.

**Alternatives considered**: Bundle with CUDA for forward compatibility — rejected (doubles installer size; app has never supported GPU inference).

---

## 4. `imageio-ffmpeg` Frozen Bundle

**Decision**: Add `imageio_ffmpeg` binary directory to `datas` in each `.spec` file.

**Rationale**: `imageio-ffmpeg` stores a platform-specific static ffmpeg binary in `imageio_ffmpeg/binaries/`. PyInstaller's `collect_all("imageio_ffmpeg")` collects Python source but may miss the `binaries/` subdirectory. Explicit `datas` entry guarantees the binary is included.

```python
# in .spec file
from PyInstaller.utils.hooks import collect_all
datas, binaries, hiddenimports = collect_all("imageio_ffmpeg")
```

`app/utils/ffmpeg_path.py` already uses `imageio_ffmpeg.get_ffmpeg_exe()` which resolves to the bundled binary path — no code changes needed.

---

## 5. `open_clip` Model Config JSONs

**Decision**: Use `collect_all("open_clip")` in every `.spec` file.

**Rationale**: `open_clip` stores model architecture configs as JSON files in `open_clip/model_configs/`. Without these, `open_clip.create_model_and_transforms()` raises `FileNotFoundError` at runtime. `collect_all` picks up both the Python package and its data files.

**Verification step** (post-build): Confirm `dist/CCTV-Video-Processor/open_clip/model_configs/` contains `.json` files.

---

## 6. macOS Ad-Hoc Signing

**Decision**: `codesign --sign -` (ad-hoc identity) applied to the entire `.app` bundle before DMG creation.

**Rationale**: Ad-hoc signing removes the "App is damaged" message on Apple Silicon Macs (which enforce code signing at the Secure Enclave level). Users still see a "cannot verify developer" Gatekeeper dialog on first launch, but this is bypassed with right-click → Open — a one-time action.

```bash
codesign --sign - --force --deep --preserve-metadata=entitlements \
  "dist/CCTV Video Processor.app"
```

**`xattr -cr`**: Strip quarantine attribute for users who received the app via a web download, documented in DMG README.txt.

**Alternatives considered**: Full Apple Developer Program signing (~$99/yr, notarization pipeline) — rejected (no Apple account available per project constraints).

---

## 7. QEMU ARM64 for Pi Build on GitHub Actions

**Decision**: Use `uraimo/run-on-arch-action@v2` with `arch: aarch64` and `distro: bookworm` for the Pi build. Keep it as a **separate manual-dispatch workflow** (`release-pi.yml`).

**Rationale**: QEMU ARM64 emulation on `ubuntu-latest` takes 45–90 minutes to compile torch extensions from source (no ARM64 wheel available on PyPI for some dependencies). This would block regular tag releases for 90 min. Manual dispatch lets developers trigger the Pi build independently.

**Cache strategy**: Cache pip downloads and PyInstaller build artifacts between runs using `actions/cache@v4` keyed on `requirements.txt` hash to reduce repeat build times.

**Alternatives considered**: Cross-compile on x86_64 with `crossenv` — rejected (too fragile for complex binary extensions like torch).

---

## 8. Linux AppImage

**Decision**: Use `appimageTool` from [AppImage releases](https://github.com/AppImage/AppImageKit) to wrap the PyInstaller `--onedir` output.

**Rationale**: AppImage is a single-file, distribution-agnostic Linux format that works on Ubuntu 20.04+ (glibc 2.31+) without installation. The `create_appimage.sh` script:
1. Creates an `AppDir/` tree with the PyInstaller output
2. Adds a minimal `.desktop` file and icon
3. Calls `appimageTool AppDir/ output.AppImage`

**DISPLAY for PyInstaller on Linux CI**: `apt-get install -y xvfb` + `Xvfb :99 &` + `DISPLAY=:99` prevents Qt from crashing with "cannot connect to X server" during the import phase of PyInstaller analysis.

---

## 9. Inno Setup (Windows Installer)

**Decision**: Inno Setup 6.x to wrap PyInstaller `--onedir` output into a single `.exe` installer.

**Rationale**: Inno Setup is the de-facto standard for Python app installers on Windows, used by Mu Editor, Thonny, and others. It produces a Setup Wizard with Next → Next → Finish UX, creates Start Menu + Desktop shortcuts, and handles uninstallation via Add/Remove Programs.

**Key `installer.iss` sections**:
- `[Setup]` — `AppName`, `AppVersion`, `DefaultDirName={autopf}\CCTV Processor`
- `[Files]` — recursive copy of `dist\CCTV-Video-Processor\*`
- `[Icons]` — Desktop + Start Menu shortcuts pointing to `launcher.exe`
- `[Run]` — optionally launch app after install

---

## 10. Florence-2 `HF_HOME` / `HUGGINGFACE_HUB_CACHE` Fix

**Decision**: In `frame_analyzer.py:is_available()`, resolve the weights directory through the env var chain.

```python
import os
_hf_home = (
    os.environ.get("HF_HOME")
    or os.environ.get("HUGGINGFACE_HUB_CACHE")
    or str(Path.home() / ".cache" / "huggingface")
)
weights_dir = Path(_hf_home) / "hub" / "models--microsoft--Florence-2-base"
```

**Rationale**: The existing code hardcodes `~/.cache/huggingface/hub/...`. Users who set `HF_HOME` (a standard HuggingFace env var) or CI environments that redirect the cache get `False` from `is_available()` even when weights exist.

---

## 11. CLIP Disk-Presence Check Fix

**Decision**: In `clip_indexer.py:is_available()`, check `~/.cache/clip/ViT-B-32.pt` exists before returning True.

```python
import os
xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
cache_root = (
    Path(os.environ["CLIP_CACHE_DIR"]) if os.environ.get("CLIP_CACHE_DIR")
    else Path(xdg) / "clip" if xdg
    else Path.home() / ".cache" / "clip"
)
return (cache_root / "ViT-B-32.pt").exists()
```

**Rationale**: The existing `is_available()` returns True as soon as `import open_clip` succeeds. This causes a 578 MB surprise download the first time `ClipIndexer.embed()` is called, with no user warning.

---

## 12. macOS Tray Single-Click Fix

**Decision**: In `shell/tray.py`, use `ActivationReason.Trigger` for window restoration on macOS 13+.

```python
import sys
def _on_activated(self, reason):
    if sys.platform == "darwin":
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_window()
    else:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()
```

**Rationale**: Qt bug QTBUG-116766 — macOS 13 Ventura no longer forwards `DoubleClick` events from the system tray. `Trigger` (single-click) is delivered reliably on all macOS versions.

---

## 13. `IS_LOW_RAM_PI` Config Constant

**Decision**: Add to `app/config.py`:

```python
IS_LOW_RAM_PI: bool = IS_PI and not AI_FEATURES_ENABLED
```

**Rationale**: The setup wizard needs to display Pi-specific messaging when running on a Pi with < 5 GB RAM (YOLO-only mode). This flag is derivable from existing constants with no new logic. Used only by the wizard — no detection engine changes needed.

---

## Summary of All Decisions

| # | Area | Decision |
|---|------|---------|
| 1 | Packaging mode | `--onedir` (not `--onefile`) |
| 2 | Frozen path resolution | `get_resource_path()` with `sys._MEIPASS` |
| 3 | torch | CPU-only wheel from `download.pytorch.org/whl/cpu` |
| 4 | imageio-ffmpeg | `collect_all("imageio_ffmpeg")` in spec |
| 5 | open_clip configs | `collect_all("open_clip")` in spec |
| 6 | macOS signing | Ad-hoc `codesign --sign -` |
| 7 | Pi CI build | QEMU aarch64, separate manual-dispatch workflow |
| 8 | Linux format | AppImage via appimageTool |
| 9 | Windows format | Inno Setup 6.x wrapping onedir output |
| 10 | HF_HOME fix | Env var chain in frame_analyzer.is_available() |
| 11 | CLIP fix | Disk presence check in clip_indexer.is_available() |
| 12 | macOS tray | `Trigger` event on darwin |
| 13 | Pi RAM flag | `IS_LOW_RAM_PI = IS_PI and not AI_FEATURES_ENABLED` |
