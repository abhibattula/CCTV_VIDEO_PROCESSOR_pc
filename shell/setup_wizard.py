"""
First-run setup wizard — downloads AI model weights before the main app starts.

Module-level helpers (setup_complete, mark_setup_complete, _build_model_list,
_http_download) are unit-testable without instantiating any Qt widget.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------

_SENTINEL: Path = Path.home() / ".cctv_processor" / ".setup_complete"


def setup_complete() -> bool:
    """Return True if the first-run sentinel file exists."""
    try:
        return _SENTINEL.exists()
    except OSError:
        return False


def mark_setup_complete() -> None:
    """Create the sentinel file.  Idempotent; never raises."""
    try:
        _SENTINEL.parent.mkdir(parents=True, exist_ok=True)
        _SENTINEL.touch(exist_ok=True)
    except OSError as exc:
        logger.warning("Could not write setup sentinel: %s", exc)


# ---------------------------------------------------------------------------
# Download primitives — canonical implementations live in
# app/core/model_downloader.py (shared with the /api/system/ai-download
# endpoint). These module-level wrappers are kept so existing tests can keep
# monkeypatching shell.setup_wizard._http_download etc.
# ---------------------------------------------------------------------------

from app.core import model_downloader as _md


def _build_model_list() -> list[dict]:
    """Return the list of model dicts to download, filtered by AI_FEATURES_ENABLED."""
    return _md.build_model_list()


def _http_download(url: str, dest_path: Path, progress_cb=None) -> None:
    """Stream-download *url* to *dest_path*, calling progress_cb(bytes_so_far, total) per chunk."""
    return _md.http_download(url, dest_path, progress_cb=progress_cb)


def _verify_sha256(path: Path, expected: str) -> bool:
    return _md.verify_sha256(path, expected)


# ---------------------------------------------------------------------------
# DownloadWorker
# ---------------------------------------------------------------------------

try:
    from PyQt6.QtCore import QThread, pyqtSignal

    class DownloadWorker(QThread):
        progress = pyqtSignal(str, int)    # (model_name, pct)
        log_line = pyqtSignal(str)
        finished = pyqtSignal(bool, str)   # (success, error_msg)

        def __init__(self, models: Optional[list[dict]] = None, parent=None):
            super().__init__(parent)
            self.models = models if models is not None else _build_model_list()
            self._errors: list[str] = []

        def run(self) -> None:
            self._errors = []
            for model in self.models:
                try:
                    ok = self._download_one(model)
                    if not ok and model.get("required"):
                        self._errors.append(f"{model['name']} failed")
                except Exception as exc:
                    msg = f"{model['name']} failed: {exc}"
                    logger.error(msg)
                    if model.get("required"):
                        self._errors.append(msg)

            if self._errors:
                self.finished.emit(False, "; ".join(self._errors))
            else:
                self.finished.emit(True, "")

        def _download_one(self, model: dict) -> bool:
            name = model["name"]
            url: Optional[str] = model.get("url")
            dest: Optional[Path] = model.get("dest")
            sha256: Optional[str] = model.get("sha256")

            # Florence-2: HuggingFace Hub handles it
            if url is None and dest is None:
                self._download_florence2(name)
                return True

            assert dest is not None

            # Check if already cached with matching hash
            if dest.exists():
                if sha256 is None or _verify_sha256(dest, sha256):
                    self.log_line.emit(f"{name}: already cached — skipping")
                    return True
                # Hash mismatch — delete stale file and re-download
                dest.unlink(missing_ok=True)

            # Download with up to 3 retries
            MAX_RETRIES = 3
            for attempt in range(1, MAX_RETRIES + 1):
                self.log_line.emit(f"{name}: downloading (attempt {attempt}/{MAX_RETRIES})")
                try:
                    def _progress(done: int, total: int, _name=name) -> None:
                        pct = int(done * 100 / total) if total else 0
                        self.progress.emit(_name, pct)

                    _http_download(url, dest, progress_cb=_progress)
                except Exception as exc:
                    self.log_line.emit(f"{name}: download error: {exc}")
                    if dest.exists():
                        dest.unlink(missing_ok=True)
                    if attempt == MAX_RETRIES:
                        raise
                    continue

                # Verify SHA256 if provided
                if sha256 is not None:
                    if _verify_sha256(dest, sha256):
                        self.log_line.emit(f"{name}: verified OK")
                        self.progress.emit(name, 100)
                        return True
                    else:
                        self.log_line.emit(f"{name}: SHA256 mismatch, retrying")
                        dest.unlink(missing_ok=True)
                        if attempt == MAX_RETRIES:
                            self.log_line.emit(f"{name}: SHA256 failed after {MAX_RETRIES} attempts")
                            return False
                else:
                    self.log_line.emit(f"{name}: downloaded OK")
                    self.progress.emit(name, 100)
                    return True
            return False

        def _download_florence2(self, name: str) -> None:
            self.log_line.emit(f"{name}: downloading via HuggingFace Hub")
            try:
                from huggingface_hub import snapshot_download
                snapshot_download(
                    repo_id="microsoft/Florence-2-base",
                    local_dir=None,
                    ignore_patterns=["*.msgpack", "flax_model*", "tf_model*"],
                )
                self.log_line.emit(f"{name}: downloaded OK")
                self.progress.emit(name, 100)
            except Exception as exc:
                self.log_line.emit(f"{name}: download failed: {exc}")
                raise

except ImportError:
    # Qt not available (e.g., during unit tests) — provide a minimal stub
    import threading

    class DownloadWorker:  # type: ignore[no-redef]
        def __init__(self, models=None, parent=None):
            self.models = models if models is not None else _build_model_list()
            self._errors: list[str] = []
            self.progress = _Signal()
            self.log_line = _Signal()
            self.finished = _Signal()

        def run(self) -> None:
            self._errors = []
            for model in self.models:
                try:
                    ok = self._download_one(model)
                    if not ok and model.get("required"):
                        self._errors.append(f"{model['name']} failed")
                except Exception as exc:
                    msg = f"{model['name']} failed: {exc}"
                    logger.error(msg)
                    if model.get("required"):
                        self._errors.append(msg)
            if self._errors:
                self.finished.emit(False, "; ".join(self._errors))
            else:
                self.finished.emit(True, "")

        def _download_one(self, model: dict) -> bool:
            name = model["name"]
            url: Optional[str] = model.get("url")
            dest: Optional[Path] = model.get("dest")
            sha256: Optional[str] = model.get("sha256")

            if url is None and dest is None:
                return True  # Florence-2 stub

            assert dest is not None

            if dest.exists():
                if sha256 is None or _verify_sha256(dest, sha256):
                    self.log_line.emit(f"{name}: already cached — skipping")
                    return True
                dest.unlink(missing_ok=True)

            MAX_RETRIES = 3
            for attempt in range(1, MAX_RETRIES + 1):
                self.log_line.emit(f"{name}: downloading (attempt {attempt}/{MAX_RETRIES})")
                try:
                    _http_download(url, dest, progress_cb=None)
                except Exception as exc:
                    self.log_line.emit(f"{name}: download error: {exc}")
                    if dest.exists():
                        dest.unlink(missing_ok=True)
                    if attempt == MAX_RETRIES:
                        raise
                    continue

                if sha256 is not None:
                    if _verify_sha256(dest, sha256):
                        self.log_line.emit(f"{name}: verified OK")
                        return True
                    else:
                        self.log_line.emit(f"{name}: SHA256 mismatch, retrying")
                        dest.unlink(missing_ok=True)
                        if attempt == MAX_RETRIES:
                            self.log_line.emit(f"{name}: SHA256 failed after {MAX_RETRIES} attempts")
                            return False
                else:
                    self.log_line.emit(f"{name}: downloaded OK")
                    return True
            return False

    class _Signal:
        """Minimal signal stub for non-Qt environments."""
        def __init__(self):
            self._callbacks = []

        def connect(self, cb):
            self._callbacks.append(cb)

        def emit(self, *args):
            for cb in self._callbacks:
                cb(*args)


# ---------------------------------------------------------------------------
# SetupWizard (Qt dialog — only defined when PyQt6 is available)
# ---------------------------------------------------------------------------

try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QProgressBar, QTextEdit, QStackedWidget, QWidget,
    )
    from PyQt6.QtCore import Qt

    class SetupWizard(QDialog):
        """First-run dialog that downloads AI model weights."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("CCTV Video Processor — First Run Setup")
            self.setMinimumWidth(520)
            self.setModal(True)

            self._worker: Optional[DownloadWorker] = None
            self._models = _build_model_list()
            self._stack = QStackedWidget()
            self._build_ui()

            layout = QVBoxLayout(self)
            layout.addWidget(self._stack)

        # ------------------------------------------------------------------
        # UI construction
        # ------------------------------------------------------------------

        def _build_ui(self):
            self._stack.addWidget(self._build_step1())
            self._stack.addWidget(self._build_step2())
            self._stack.addWidget(self._build_step3())
            self._stack.setCurrentIndex(0)

        def _build_step1(self) -> QWidget:
            from app.config import IS_LOW_RAM_PI, AI_FEATURES_ENABLED
            import psutil
            import shutil

            page = QWidget()
            layout = QVBoxLayout(page)

            layout.addWidget(QLabel("<h2>Welcome to CCTV Video Processor</h2>"))
            layout.addWidget(QLabel("First-run check complete. Ready to download AI models."))

            total_gb = psutil.virtual_memory().total / 1e9
            free_gb = shutil.disk_usage(Path.home()).free / 1e9

            ram_status = "OK" if total_gb >= 5.0 else "LOW"
            disk_status = "OK" if free_gb >= 2.0 else "LOW WARNING"

            info = QLabel(
                f"RAM: {total_gb:.1f} GB [{ram_status}]\n"
                f"Disk free: {free_gb:.1f} GB [{disk_status}]"
            )
            info.setStyleSheet("font-family: monospace;")
            layout.addWidget(info)

            if IS_LOW_RAM_PI:
                warn = QLabel(
                    f"Your Pi has {total_gb:.1f} GB RAM — YOLO motion detection works great.\n"
                    "AI image descriptions require 5 GB+ and are not available."
                )
                warn.setWordWrap(True)
                layout.addWidget(warn)

            btn_layout = QHBoxLayout()
            self._btn_download = QPushButton("Download AI Models")
            self._btn_skip = QPushButton("Skip for Now")
            self._btn_download.clicked.connect(self._on_download_clicked)
            self._btn_skip.clicked.connect(self._on_skip_clicked)
            btn_layout.addWidget(self._btn_download)
            btn_layout.addWidget(self._btn_skip)
            layout.addLayout(btn_layout)

            return page

        def _build_step2(self) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.addWidget(QLabel("<h3>Downloading AI Models…</h3>"))

            self._progress_label = QLabel("Starting…")
            layout.addWidget(self._progress_label)

            self._progress_bar = QProgressBar()
            self._progress_bar.setRange(0, 100)
            layout.addWidget(self._progress_bar)

            self._log_area = QTextEdit()
            self._log_area.setReadOnly(True)
            self._log_area.setMaximumHeight(160)
            layout.addWidget(self._log_area)

            btn_skip2 = QPushButton("Skip for Now")
            btn_skip2.clicked.connect(self._on_skip_clicked)
            layout.addWidget(btn_skip2)

            return page

        def _build_step3(self) -> QWidget:
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.addWidget(QLabel("<h2>Setup Complete!</h2>"))
            self._done_label = QLabel("Click Launch to open the app.")
            self._done_label.setWordWrap(True)
            layout.addWidget(self._done_label)

            btn_launch = QPushButton("Launch")
            btn_launch.clicked.connect(self.accept)
            layout.addWidget(btn_launch)

            return page

        # ------------------------------------------------------------------
        # Slots
        # ------------------------------------------------------------------

        def _on_download_clicked(self):
            self._stack.setCurrentIndex(1)
            self._worker = DownloadWorker(models=self._models)
            self._worker.progress.connect(self._on_progress)
            self._worker.log_line.connect(self._on_log)
            self._worker.finished.connect(self._on_finished)
            self._worker.start()

        def _on_skip_clicked(self):
            mark_setup_complete()
            self.accept()

        def _on_progress(self, name: str, pct: int):
            self._progress_label.setText(f"{name}: {pct}%")
            self._progress_bar.setValue(pct)

        def _on_log(self, line: str):
            self._log_area.append(line)

        def _on_finished(self, success: bool, error_msg: str):
            mark_setup_complete()
            if success:
                self._done_label.setText("Setup complete! Click Launch to open the app.")
            else:
                self._done_label.setText(
                    f"Some optional models failed to download:\n{error_msg}\n\n"
                    "The app will still work — you can retry any time from the\n"
                    "AI Models card on the Home page."
                )
            self._stack.setCurrentIndex(2)

        def exec(self) -> int:  # type: ignore[override]
            super().exec()
            return QDialog.DialogCode.Accepted.value

except ImportError:
    # Tests run without PyQt6
    class SetupWizard:  # type: ignore[no-redef]
        def __init__(self, parent=None):
            pass

        def exec(self) -> int:
            return 1
