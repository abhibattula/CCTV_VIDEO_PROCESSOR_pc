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

---

## Model Download Strategy (A1 Remediation)

This section specifies the exact download mechanism for each AI model used by `DownloadWorker`.

### YOLOv8n (~6 MB)

**Strategy**: Use `ultralytics` library's built-in download, redirected to `MODEL_DIR`.

```python
import os
from app.config import MODEL_DIR
os.environ["YOLO_CONFIG_DIR"] = str(MODEL_DIR)
from ultralytics import YOLO
YOLO("yolov8n.pt")  # downloads to MODEL_DIR/yolov8n.pt automatically
```

**SHA256**: Ultralytics validates the downloaded model hash internally using its own manifest. The wizard does NOT need to separately SHA256-verify YOLOv8n — call `YOLO("yolov8n.pt")` and check the file exists at `MODEL_DIR / "yolov8n.pt"` after the call.

**Progress**: Ultralytics prints download progress to stdout. The wizard can redirect stdout or simply emit a log message ("Downloading YOLOv8n...") and then ("YOLOv8n ready") after completion.

**Alternative raw URL** (if direct HTTP needed for progress bar):
`https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt`

---

### Florence-2 (~444 MB, 15+ files)

**Strategy**: Use `huggingface_hub.snapshot_download()` with `tqdm_class` progress.

```python
from huggingface_hub import snapshot_download
import os

hf_home = (
    os.environ.get("HF_HOME")
    or os.environ.get("HUGGINGFACE_HUB_CACHE")
    or str(Path.home() / ".cache" / "huggingface")
)
snapshot_download(
    repo_id="microsoft/Florence-2-base",
    local_dir=None,  # uses HF_HOME/hub/ by default
    ignore_patterns=["*.msgpack", "flax_model*", "tf_model*"],
)
```

**SHA256**: HuggingFace Hub performs SHA256 verification of every file automatically via `huggingface_hub`'s built-in integrity checks. The wizard does NOT need to re-verify — call `snapshot_download()` and check that `weights_dir.exists()` afterward.

**Progress**: `snapshot_download()` accepts a `tqdm_class` parameter. For the wizard, emit `progress("Florence-2", pct)` signals by subclassing `tqdm` with a custom `update()` that calls `self.progress.emit(...)`.

**`expected_sha256`**: Set to `None` in `AIModelSpec` for Florence-2 — HF Hub handles integrity.

---

### CLIP ViT-B/32 (~578 MB, single file)

**Strategy**: Use `open_clip`'s built-in download via `create_model_and_transforms()`. The file downloads to `~/.cache/clip/ViT-B-32.pt` (or XDG_CACHE_HOME/clip/).

```python
import open_clip
# Downloads ViT-B-32.pt to ~/.cache/clip/ on first call
open_clip.create_model_and_transforms("ViT-B-32-quickgelu", pretrained="openai")
```

**SHA256**: The known SHA256 of `ViT-B-32.pt` (OpenAI pretrained) is:  
`40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af`

The wizard MUST verify this hash after the download completes. If mismatch, delete and retry (up to 3 times).

**Progress**: `open_clip` uses `urllib.request.urlretrieve` with a reporthook internally. The wizard can intercept by temporarily monkeypatching `urllib.request.urlretrieve` with a hook that calls `self.progress.emit("CLIP ViT-B/32", pct)`. Alternatively, use direct raw download:

```python
# Direct download with progress (alternative to open_clip's internal download):
CLIP_URL = "https://openaipublic.azureedge.net/clip/models/40d36571/ViT-B-32.pt"
```

**`expected_sha256`**: `"40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af"` — verify after download.

---

### AIModelSpec Instances (concrete values)

```python
YOLO_SPEC = AIModelSpec(
    name="YOLOv8n",
    url="https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt",
    dest_path=MODEL_DIR / "yolov8n.pt",
    expected_sha256=None,  # ultralytics validates internally
    size_bytes=6_536_616,  # ~6.2 MB
    required=True,
    skip_if_low_ram=False,
)

FLORENCE2_SPEC = AIModelSpec(
    name="Florence-2",
    url=None,  # uses huggingface_hub.snapshot_download()
    dest_path=None,  # HF Hub manages cache path
    expected_sha256=None,  # HF Hub validates internally
    size_bytes=444_000_000,  # ~444 MB (approx)
    required=False,
    skip_if_low_ram=True,
)

CLIP_SPEC = AIModelSpec(
    name="CLIP ViT-B/32",
    url="https://openaipublic.azureedge.net/clip/models/40d36571/ViT-B-32.pt",
    dest_path=Path.home() / ".cache" / "clip" / "ViT-B-32.pt",
    expected_sha256="40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af",
    size_bytes=353_976_371,  # ~338 MB actual
    required=False,
    skip_if_low_ram=True,
)
```

`DownloadWorker` builds the models list at startup: always includes `YOLO_SPEC`; appends `FLORENCE2_SPEC` and `CLIP_SPEC` only if `AI_FEATURES_ENABLED=True`.
