# Interface Contract: Setup Wizard

**Module**: `shell/setup_wizard.py`  
**Feature**: `012-cross-platform-dist`  
**Date**: 2026-06-30

---

## Module-Level Functions

### `setup_complete() -> bool`

Returns `True` if the setup sentinel file exists (`~/.cctv_processor/.setup_complete`), `False` otherwise.

- **Side effects**: None (read-only)
- **Thread safety**: Safe to call from any thread
- **Raises**: Never raises; returns `False` on any OS error

### `mark_setup_complete() -> None`

Creates the sentinel file. Idempotent — safe to call multiple times.

- **Side effects**: Creates `~/.cctv_processor/.setup_complete` (creates parent dir if needed)
- **Raises**: Never raises; silently ignores OS errors

---

## `DownloadWorker(QThread)`

Background thread that downloads AI model weight files.

### Constructor

```python
DownloadWorker(models: list[dict], parent=None)
```

`models` is a list of dicts, each with keys:
- `name: str` — display label
- `url: str` — download URL
- `dest: Path` — destination file path
- `sha256: str` — expected SHA256 hex digest
- `size: int` — expected size in bytes
- `required: bool` — True if download failure is critical

### Qt Signals

| Signal | Type signature | Description |
|--------|---------------|-------------|
| `progress` | `(str, int)` | `(model_name, percent_0_to_100)` — emitted each chunk |
| `log_line` | `(str,)` | Human-readable status message for log area |
| `finished` | `(bool, str)` | `(success, error_message)` — `success=True` if all required models downloaded |

### `run() -> None`

Main thread entry point. Downloads each model in sequence:
1. Skip model if `dest.exists()` and SHA256 matches (already downloaded)
2. Stream download in 64 KB chunks, emit `progress` per chunk
3. After download completes, verify SHA256; on mismatch, delete and retry (max 3 attempts)
4. Emit `log_line` for each state transition
5. After all models: emit `finished(True, "")` if all required models succeeded, else `finished(False, <error>)`

**Preconditions**: Models list must not be empty. `dest` parent directories must be creatable.  
**Postconditions**: On success, each `dest` file exists and SHA256 matches.

---

## `SetupWizard(QDialog)`

The first-run setup dialog.

### Constructor

```python
SetupWizard(parent=None)
```

**Behaviour on open**:
1. Performs `SystemCheckResult` analysis (RAM, FFmpeg, disk space)
2. Builds `models` list filtered by `AI_FEATURES_ENABLED`
3. Shows Step 1 (System Check)

### Public Interface

| Method | Description |
|--------|-------------|
| `exec() -> int` | Show dialog modally; returns `QDialog.Accepted` always (wizard never blocks launch) |

### Internal Slots (not part of public contract)

- `_on_download_clicked()` — starts `DownloadWorker`, transitions to Step 2
- `_on_skip_clicked()` — calls `mark_setup_complete()`, calls `accept()`
- `_on_progress(name, pct)` — updates progress bar
- `_on_log(line)` — appends to log area
- `_on_finished(success, error_msg)` — transitions to Step 3 or shows error

### Wizard Step Layout

```
Step 1: System Check
  - RAM: X.X GB [OK / LOW]
  - Platform: [name]
  - FFmpeg: [OK / WARNING]  
  - Disk: X.X GB free [OK / LOW WARNING]
  [If IS_LOW_RAM_PI] "Your Pi has X GB RAM — YOLO motion detection works great.
                      AI image descriptions require 5 GB+ and are not available."
  [Download] [Skip for now]

Step 2: Downloading
  - Per-model progress bar (name + %)
  - Log area (scrollable)
  - [Skip for now] (always visible)

Step 3: Done
  - "Setup complete! Click Launch to open the app."
  [Launch]
```

---

## `get_resource_path(relative: str) -> Path`

**Module**: `app/utils/resource_path.py`

Returns the absolute path to a bundled resource, working in both dev and frozen (PyInstaller) mode.

| Context | Resolution |
|---------|-----------|
| Dev mode | `Path(__file__).parent.parent.parent / relative` (project root) |
| Frozen (`sys.frozen=True`, `sys._MEIPASS` set) | `Path(sys._MEIPASS) / relative` |

- **Raises**: Never raises; caller is responsible for checking existence
- **Thread safety**: Safe (reads `sys` attributes, no mutation)

**Usage**:
```python
from app.utils.resource_path import get_resource_path
static_root = get_resource_path("static")          # in app/main.py
templates_dir = get_resource_path("app/templates") # in report_renderer.py
```

---

## Integration Point: `launcher.py`

```python
from shell.setup_wizard import SetupWizard, setup_complete

# After QApplication created, before MainWindow:
if not setup_complete():
    wizard = SetupWizard()
    wizard.exec()   # always returns; wizard writes sentinel on complete or skip
```

The wizard call is non-blocking after return — MainWindow creation proceeds unconditionally.

---

## Test Contract

Tests in `tests/test_setup_wizard.py` MUST verify:

1. `setup_complete()` returns `False` when sentinel absent
2. `setup_complete()` returns `True` after `mark_setup_complete()`
3. `mark_setup_complete()` is idempotent (safe to call twice)
4. `DownloadWorker` skips Florence-2 and CLIP when `AI_FEATURES_ENABLED=False` (monkeypatch)
5. `DownloadWorker` retries on SHA256 mismatch up to 3 times, then emits `finished(False, ...)`
6. `DownloadWorker` emits `finished(True, "")` when required model already on disk

Tests MUST NOT instantiate `QDialog` or `QApplication`.

Tests in `tests/test_resource_path.py` MUST verify:

1. Dev mode: returns path relative to project root that exists
2. Frozen mode: returns path relative to `sys._MEIPASS` (monkeypatched)
3. After test: `sys.frozen` and `sys._MEIPASS` are cleaned up (no leak between tests)
