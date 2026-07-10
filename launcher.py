"""
CCTV Video Processor — application entry point.

Starts the FastAPI backend in a daemon thread, then launches the PyQt6 shell.

Fix 1: AA_ShareOpenGLContexts must be set before QApplication is created.
Fix 2: If port is already bound by a previous instance of this app, reuse it
       instead of crashing with Errno 10048.
"""
import shutil
import signal
import socket
import sys
import threading
import time
from pathlib import Path


def _ensure_std_streams(log_path: Path | None = None) -> None:
    """In a PyInstaller windowed build (console=False), sys.stdout and
    sys.stderr are None. uvicorn's log formatter calls sys.stdout.isatty()
    during uvicorn.Config() setup, which raises AttributeError and silently
    kills the backend daemon thread — the UI then shows Chromium's
    connection-refused page. Route both streams to a log file so uvicorn can
    configure logging and backend errors stay visible.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    if log_path is None:
        log_path = Path.home() / ".cctv_processor" / "app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stream = open(log_path, "a", buffering=1, encoding="utf-8", errors="replace")
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


# Must run before uvicorn/app imports so nothing touches the None streams.
_ensure_std_streams()

import uvicorn

from app.config import BACKEND_HOST, BACKEND_PORT, PREVIEW_DIR
from app.main import create_app


# ---------------------------------------------------------------------------
# Fix 1: Qt WebEngine requires this attribute before QCoreApplication exists.
# Import and set it before anything else touches Qt.
#
# PyQt6 publishes no aarch64 wheels usable on Raspberry Pi OS Bookworm
# (they require glibc >= 2.39; Bookworm has 2.36), so the Pi build ships
# without Qt entirely. When Qt is absent, run headless: serve the same web
# UI and open it in the system browser instead of an embedded window.
# ---------------------------------------------------------------------------
try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt, QTimer

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


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


_uvicorn_server: uvicorn.Server | None = None


def _start_backend(port: int):
    global _uvicorn_server
    try:
        app = create_app()
        config = uvicorn.Config(app, host=BACKEND_HOST, port=port, log_level="warning")
        server = uvicorn.Server(config)
        _uvicorn_server = server
        server.run()
    except Exception:
        # This runs in a daemon thread — without this, any startup failure
        # disappears silently and the UI just shows a connection error.
        import traceback
        traceback.print_exc()


def stop_backend():
    """Gracefully stop the backend started by this process (no-op if it
    isn't ours to stop, e.g. when this instance reused a prior instance's
    already-running backend)."""
    if _uvicorn_server is not None:
        _uvicorn_server.should_exit = True


def _run_headless(port: int) -> None:
    """Headless mode (no Qt bundled, e.g. Raspberry Pi): the backend daemon
    thread serves the web UI; open it in the system browser and keep the
    main thread alive until Ctrl+C."""
    import webbrowser

    url = f"http://{BACKEND_HOST}:{port}"
    print(f"CCTV Video Processor — web UI at {url}  (Ctrl+C to quit)")
    threading.Timer(2.0, lambda: webbrowser.open(url)).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        stop_backend()
        shutil.rmtree(PREVIEW_DIR, ignore_errors=True)


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

    if not QT_AVAILABLE:
        _run_headless(backend_port)
        return

    # ── Qt application ────────────────────────────────────────────────────────
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)

    # Handle Ctrl+C — Qt blocks Python SIGINT on all platforms without this dummy timer.
    # The 200ms tick keeps Python's signal-delivery machinery alive inside the Qt event loop.
    signal.signal(signal.SIGINT, lambda *_: qt_app.quit())
    _sig_timer = QTimer()
    _sig_timer.timeout.connect(lambda: None)
    _sig_timer.start(200)

    # ── First-run setup wizard ────────────────────────────────────────────────
    from shell.setup_wizard import SetupWizard, setup_complete
    if not setup_complete():
        wizard = SetupWizard()
        wizard.exec()

    # Pass the resolved port so the window loads the right URL
    from shell.main_window import MainWindow
    window = MainWindow(backend_port=backend_port, on_stop_backend=stop_backend)
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
