"""
CCTV Video Processor — application entry point.

Starts the FastAPI backend in a daemon thread, then launches the PyQt6 shell.
"""
import shutil
import sys
import threading
import time

import uvicorn

from app.config import BACKEND_HOST, BACKEND_PORT, PREVIEW_DIR
from app.main import create_app


def _start_backend():
    app = create_app()
    uvicorn.run(
        app,
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        log_level="warning",
    )


def main():
    # ── Start backend ─────────────────────────────────────────────────────────
    backend_thread = threading.Thread(target=_start_backend, daemon=True)
    backend_thread.start()

    # ── Qt application ────────────────────────────────────────────────────────
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer

    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    from shell.main_window import MainWindow
    window = MainWindow()
    window.show()

    # ── T072: tray icon ───────────────────────────────────────────────────────
    from shell.tray import TrayIcon
    _tray = TrayIcon(window)  # noqa: F841  (kept alive by reference)

    # ── T057: periodic preview cleanup (every 60s, delete files > 5 min old) ──
    def _cleanup_old_previews():
        if not PREVIEW_DIR.exists():
            return
        cutoff = time.time() - 300
        for f in PREVIEW_DIR.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
            except OSError:
                pass

    cleanup_timer = QTimer()
    cleanup_timer.timeout.connect(_cleanup_old_previews)
    cleanup_timer.start(60_000)  # every 60s

    # ── T057: full preview wipe on quit ──────────────────────────────────────
    def _on_quit():
        shutil.rmtree(PREVIEW_DIR, ignore_errors=True)

    qt_app.aboutToQuit.connect(_on_quit)

    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
