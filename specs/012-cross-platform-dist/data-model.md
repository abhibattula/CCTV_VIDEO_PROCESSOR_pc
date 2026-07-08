# Data Model: Cross-Platform Distribution

**Feature**: `012-cross-platform-dist`  
**Date**: 2026-06-30

---

## Entities

### 1. SetupSentinel

The marker that records whether the first-run wizard has been completed.

| Field | Type | Description |
|-------|------|-------------|
| `path` | `Path` | `Path.home() / ".cctv_processor" / ".setup_complete"` |
| `exists` | `bool` | Derived: `path.exists()` |

**Operations**:
- `setup_complete() -> bool` — returns `path.exists()`
- `mark_setup_complete() -> None` — creates the file (atomic: `path.touch()`)

**Lifecycle**: Created once when the user clicks "Download" or "Skip for now" in the wizard. Preserved through app upgrades (lives in `~/.cctv_processor/`, outside the install directory). Never deleted by the app.

**Validation**: File need only exist; contents irrelevant. Size = 0 bytes is valid.

---

### 2. AIModelSpec

Describes a single AI model that the wizard can download.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Display name ("YOLOv8n", "Florence-2", "CLIP ViT-B/32") |
| `url` | `str` | Download URL (HuggingFace Hub or Ultralytics CDN) |
| `dest_path` | `Path` | Where the downloaded file is saved |
| `expected_sha256` | `str` | Hex digest for integrity verification |
| `size_bytes` | `int` | Expected file size for progress display |
| `required` | `bool` | True = critical (YOLOv8n); False = non-critical (Florence-2, CLIP) |
| `skip_if_low_ram` | `bool` | True for Florence-2 and CLIP (skipped when `not AI_FEATURES_ENABLED`) |

**State transitions**:
```
Pending → Downloading → Verifying → Complete
                     ↓            ↓
                   Failed ←── HashMismatch (retry ≤3×)
```

**Validation rules**:
- `expected_sha256` must be a 64-character hex string
- `size_bytes > 0`
- `dest_path` parent directory must exist or be creatable

---

### 3. WizardState

Runtime state of the setup wizard (in-memory only, never persisted).

| Field | Type | Values |
|-------|------|--------|
| `step` | `enum` | `SYSTEM_CHECK`, `DOWNLOADING`, `DONE`, `SKIPPED` |
| `models` | `list[AIModelSpec]` | All models applicable to this device |
| `current_model_index` | `int` | Index into `models` list, updated as downloads progress |
| `retry_count` | `dict[str, int]` | Per-model retry count (reset on new session) |
| `error` | `str \| None` | Last error message; None if none |

**Transitions**:
- `SYSTEM_CHECK → DOWNLOADING` on "Download" click
- `SYSTEM_CHECK → SKIPPED` on "Skip for now" click
- `DOWNLOADING → DONE` when all models downloaded successfully
- `DOWNLOADING → DOWNLOADING` after SHA256 retry
- Any state → `SKIPPED` on "Skip for now" click

---

### 4. SystemCheckResult

Result of the system check step in the wizard.

| Field | Type | Description |
|-------|------|-------------|
| `ram_gb` | `float` | Total physical RAM in GB |
| `platform_name` | `str` | e.g. "Windows 11", "macOS 14.0", "Raspberry Pi OS" |
| `ffmpeg_ok` | `bool` | `True` if imageio-ffmpeg binary resolves |
| `disk_free_gb` | `float` | Free disk space at `~/.cctv_processor/` |
| `disk_ok` | `bool` | `True` if `disk_free_gb >= 3.0` |
| `ai_enabled` | `bool` | `AI_FEATURES_ENABLED` value |
| `is_low_ram_pi` | `bool` | `IS_LOW_RAM_PI` value |

**Display logic**:
- `ffmpeg_ok == False` → warning (not blocking; app can still run)
- `disk_ok == False` → warning shown before download begins
- `is_low_ram_pi == True` → Pi-specific RAM message shown

---

### 5. FrozenBundle

The output of PyInstaller — conceptual entity representing an installed app.

| Attribute | Value |
|-----------|-------|
| Mode | `--onedir` |
| Root at runtime | `sys._MEIPASS` (frozen) or project root (dev) |
| `static/` path | `get_resource_path("static")` |
| `app/templates/` path | `get_resource_path("app/templates")` |
| ffmpeg binary | `imageio_ffmpeg.get_ffmpeg_exe()` (unchanged) |
| Model weights | `~/.cctv_processor/models/` (outside bundle) |

**Constraint**: Model weights are never inside the bundle — they live in the user data directory and survive upgrades.

---

## Entity Relationships

```
FrozenBundle
    └── uses → get_resource_path() → resolves paths from sys._MEIPASS

SetupSentinel
    ├── checked by → launcher.py before showing MainWindow
    └── created by → SetupWizard (on Download or Skip)

WizardState
    ├── contains → list[AIModelSpec]
    ├── reads → SystemCheckResult (on wizard open)
    └── writes → SetupSentinel (on completion)

AIModelSpec
    ├── downloaded by → DownloadWorker (QThread)
    └── verified by → SHA256 check after each download
```

---

## Config Constants (additions to `app/config.py`)

| Constant | Type | Definition |
|----------|------|-----------|
| `IS_LOW_RAM_PI` | `bool` | `IS_PI and not AI_FEATURES_ENABLED` |

Existing constants unchanged: `IS_PI`, `AI_FEATURES_ENABLED`, `_total_gb`, `MODEL_DIR`.
