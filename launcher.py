"""
CCTV Video Processor — application entry point.

Starts the FastAPI backend in a daemon thread, then launches the PyQt6 shell.

Fix 1: AA_ShareOpenGLContexts must be set before QApplication is created.
Fix 2: If port is already bound by a previous instance of this app, reuse it
       instead of crashing with Errno 10048.
"""
import shutil
import socket
import sys
import threading
import time

import uvicorn

from app.config import BACKEND_HOST, BACKEND_PORT, PREVIEW_DIR
from app.main import create_app


# ---------------------------------------------------------------------------
# Fix 1: Qt WebEngine requires this attribute before QCoreApplication exists.
# Import and set it before anything else touches Qt.
# ---------------------------------------------------------------------------
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)


def _port_is_free(host: str, port: int) -> bool:
    """Return True if nothing is listening on host:port right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) != 0


def _our_backend_is_running(host: str, port: int) -> bool:
    """Return True if a healthy CCTV backend is already on this port."""
    try:
        import requests
        r = requests.get(f"http://{host}:{port}/api/health", timeout=1)
        return r.ok and r.json().get("status") == "ok"
    except Exception:
        return False


def _find_free_port(preferred: int) -> int:
    """Return preferred port if free, else the next available port."""
    if _port_is_free(BACKEND_HOST, preferred):
        return preferred
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _start_backend(port: int):
    app = create_app()
    uvicorn.run(
        app,
        host=BACKEND_HOST,
        port=port,
        log_level="warning",
    )


def main():
    # ── Fix 2: smart port selection ───────────────────────────────────────────
    # Case A: preferred port is free          → bind it normally
    # Case B: preferred port is our backend   → reuse, skip starting new one
    # Case C: preferred port is something else → find a free port
    backend_port = BACKEND_PORT
    backend_started = False

    if _port_is_free(BACKEND_HOST, BACKEND_PORT):
        # Normal case
        backend_thread = threading.Thread(
            target=_start_backend, args=(BACKEND_PORT,), daemon=True
        )
        backend_thread.start()
        backend_started = True
    elif _our_backend_is_running(BACKEND_HOST, BACKEND_PORT):
        # Previous instance left a healthy backend running — reuse it.
        # This happens when you close + reopen quickly, or during dev restarts.
        backend_started = True
    else:
        # Something unrelated is on that port — grab the next free one.
        backend_port = _find_free_port(BACKEND_PORT + 1)
        backend_thread = threading.Thread(
            target=_start_backend, args=(backend_port,), daemon=True
        )
        backend_thread.start()
        backend_started = True

    # ── Qt application ────────────────────────────────────────────────────────
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    # Pass the resolved port so the window loads the right URL
    from shell.main_window import MainWindow
    window = MainWindow(backend_port=backend_port)
    window.show()

    # ── Tray icon ─────────────────────────────────────────────────────────────
    from shell.tray import TrayIcon
    _tray = TrayIcon(window)  # noqa: F841  (kept alive by reference)

    # ── Periodic preview cleanup (every 60s, delete clips > 5 min old) ───────
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
    cleanup_timer.start(60_000)

    # ── Full preview wipe on quit ─────────────────────────────────────────────
    def _on_quit():
        shutil.rmtree(PREVIEW_DIR, ignore_errors=True)

    qt_app.aboutToQuit.connect(_on_quit)

    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
