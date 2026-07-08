"""
AI model weight downloader — the single download engine shared by the
first-run wizard (shell/setup_wizard.py) and the /api/system/ai-download
endpoint, so users who skipped the wizard can install AI models later from
the Home page.

Plain Python: no Qt. Thread-safe status registry so the frontend can poll
download progress.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import urllib.request
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

ProgressCb = Optional[Callable[[str, int], None]]   # (model_name, pct)
LogCb = Optional[Callable[[str], None]]


# ---------------------------------------------------------------------------
# Model list
# ---------------------------------------------------------------------------

def build_model_list() -> list[dict]:
    """Return the list of model dicts to download, filtered by AI_FEATURES_ENABLED."""
    from app.config import AI_FEATURES_ENABLED, MODEL_DIR

    models: list[dict] = [
        {
            "name": "YOLOv8n",
            "url": "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt",
            "dest": MODEL_DIR / "yolov8n.pt",
            "sha256": None,  # ultralytics validates internally
            "size": 6_536_616,
            "required": True,
        }
    ]

    if AI_FEATURES_ENABLED:
        models.append({
            "name": "Florence-2",
            "url": None,  # uses huggingface_hub.snapshot_download()
            "dest": None,
            "sha256": None,
            "size": 444_000_000,
            "required": False,
        })
        models.append({
            "name": "CLIP ViT-B/32",
            "url": "https://openaipublic.azureedge.net/clip/models/40d36571/ViT-B-32.pt",
            "dest": Path.home() / ".cache" / "clip" / "ViT-B-32.pt",
            "sha256": "40d365715913c9da98579312b702a82c18be219cc2a73407c4526f58eba950af",
            "size": 353_976_371,
            "required": False,
        })

    return models


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def http_download(url: str, dest_path: Path, progress_cb=None) -> None:
    """Stream-download *url* to *dest_path*, calling progress_cb(done, total) per chunk."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest_path.with_suffix(dest_path.suffix + ".part")

    try:
        with urllib.request.urlopen(url) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk = 65536
            with open(tmp, "wb") as fh:
                while True:
                    data = resp.read(chunk)
                    if not data:
                        break
                    fh.write(data)
                    downloaded += len(data)
                    if progress_cb and total:
                        progress_cb(downloaded, total)
        tmp.replace(dest_path)
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def verify_sha256(path: Path, expected: str) -> bool:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest() == expected


# ---------------------------------------------------------------------------
# Download orchestration (plain functions — callable from any thread)
# ---------------------------------------------------------------------------

def download_florence2(log_cb: LogCb = None, progress_cb: ProgressCb = None) -> None:
    """Download Florence-2 weights via HuggingFace Hub. Raises on failure."""
    _log(log_cb, "Florence-2: downloading via HuggingFace Hub")
    from huggingface_hub import snapshot_download
    snapshot_download(
        repo_id="microsoft/Florence-2-base",
        local_dir=None,
        ignore_patterns=["*.msgpack", "flax_model*", "tf_model*"],
    )
    _log(log_cb, "Florence-2: downloaded OK")
    if progress_cb:
        progress_cb("Florence-2", 100)


def download_one(model: dict, progress_cb: ProgressCb = None, log_cb: LogCb = None) -> bool:
    """Download a single model with retries + SHA256 verification.

    Returns True on success (or already cached), False on verification failure.
    Raises on unrecoverable download errors.
    """
    name = model["name"]
    url: Optional[str] = model.get("url")
    dest: Optional[Path] = model.get("dest")
    sha256: Optional[str] = model.get("sha256")

    # Florence-2: HuggingFace Hub handles caching/download
    if url is None and dest is None:
        download_florence2(log_cb=log_cb, progress_cb=progress_cb)
        return True

    assert dest is not None

    # Already cached with matching hash?
    if dest.exists():
        if sha256 is None or verify_sha256(dest, sha256):
            _log(log_cb, f"{name}: already cached — skipping")
            return True
        dest.unlink(missing_ok=True)  # stale — re-download

    for attempt in range(1, MAX_RETRIES + 1):
        _log(log_cb, f"{name}: downloading (attempt {attempt}/{MAX_RETRIES})")
        try:
            def _progress(done: int, total: int, _name=name) -> None:
                if progress_cb and total:
                    progress_cb(_name, int(done * 100 / total))

            http_download(url, dest, progress_cb=_progress)
        except Exception as exc:
            _log(log_cb, f"{name}: download error: {exc}")
            if dest.exists():
                dest.unlink(missing_ok=True)
            if attempt == MAX_RETRIES:
                raise
            continue

        if sha256 is not None:
            if verify_sha256(dest, sha256):
                _log(log_cb, f"{name}: verified OK")
                if progress_cb:
                    progress_cb(name, 100)
                return True
            _log(log_cb, f"{name}: SHA256 mismatch, retrying")
            dest.unlink(missing_ok=True)
            if attempt == MAX_RETRIES:
                _log(log_cb, f"{name}: SHA256 failed after {MAX_RETRIES} attempts")
                return False
        else:
            _log(log_cb, f"{name}: downloaded OK")
            if progress_cb:
                progress_cb(name, 100)
            return True
    return False


def download_models(
    models: Optional[list[dict]] = None,
    progress_cb: ProgressCb = None,
    log_cb: LogCb = None,
) -> tuple[bool, str]:
    """Download all models. Returns (success, error_message).

    A failure of a *required* model fails the whole run; optional-model
    failures are logged but don't.
    """
    if models is None:
        models = build_model_list()

    errors: list[str] = []
    for model in models:
        try:
            ok = download_one(model, progress_cb=progress_cb, log_cb=log_cb)
            if not ok and model.get("required"):
                errors.append(f"{model['name']} failed")
        except Exception as exc:
            msg = f"{model['name']} failed: {exc}"
            logger.error(msg)
            _log(log_cb, msg)
            if model.get("required"):
                errors.append(msg)

    if errors:
        return False, "; ".join(errors)
    return True, ""


def _log(log_cb: LogCb, line: str) -> None:
    logger.info(line)
    if log_cb:
        log_cb(line)


# ---------------------------------------------------------------------------
# Background download + status registry (for the /api/system endpoints)
# ---------------------------------------------------------------------------

_LOG_TAIL = 50

_status_lock = threading.Lock()
_status: dict = {
    "state": "idle",       # idle | running | done | error
    "model": "",
    "pct": 0,
    "log": [],
    "error": "",
}
_thread: Optional[threading.Thread] = None


def get_status() -> dict:
    """Return a snapshot of the current download status (thread-safe copy)."""
    with _status_lock:
        snap = dict(_status)
        snap["log"] = list(_status["log"])
        return snap


def start_background_download() -> bool:
    """Start downloading all (missing) models in a daemon thread.

    Returns True if a new download was started, False if one is already
    running. On completion, invalidates FrameAnalyzer's availability cache so
    AI features activate without an app restart.
    """
    global _thread
    with _status_lock:
        if _status["state"] == "running":
            return False
        _status.update(state="running", model="", pct=0, log=[], error="")

    def _progress(name: str, pct: int) -> None:
        with _status_lock:
            _status["model"] = name
            _status["pct"] = pct

    def _log_line(line: str) -> None:
        with _status_lock:
            _status["log"].append(line)
            del _status["log"][:-_LOG_TAIL]

    def _run() -> None:
        try:
            ok, err = download_models(progress_cb=_progress, log_cb=_log_line)
            with _status_lock:
                _status["state"] = "done" if ok else "error"
                _status["error"] = err
        except Exception as exc:  # never let the worker die silently
            logger.exception("Background model download crashed")
            with _status_lock:
                _status["state"] = "error"
                _status["error"] = str(exc)
        finally:
            reset_ai_availability_caches()

    _thread = threading.Thread(target=_run, name="ai-model-download", daemon=True)
    _thread.start()
    return True


def reset_ai_availability_caches() -> None:
    """Invalidate per-process AI availability caches after weights change."""
    try:
        from app.core.frame_analyzer import FrameAnalyzer
        FrameAnalyzer._availability_cache = None
        FrameAnalyzer.unavailable_reason = None
    except Exception:
        pass


def _reset_status_for_tests() -> None:
    with _status_lock:
        _status.update(state="idle", model="", pct=0, log=[], error="")
