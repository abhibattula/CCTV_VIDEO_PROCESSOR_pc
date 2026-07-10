"""Regression tests for the PyInstaller windowed-mode stream fix.

In a console=False (windowed) PyInstaller build, sys.stdout and sys.stderr
are None. uvicorn's ColourizedFormatter calls sys.stdout.isatty() during
uvicorn.Config() setup, raising AttributeError -> ValueError, which kills the
backend daemon thread silently. The UI then shows Chromium's
connection-refused page ("unable to connect").

The launcher must install fallback file streams before uvicorn configures
logging.

Note: the None assignment happens inside each test body (not a fixture)
because pytest's capture manager re-assigns sys.stdout between fixture setup
and the call phase, which would silently undo a fixture-applied None.
"""
import sys

import launcher  # imported with real streams — module-level guard is a no-op


def test_ensure_std_streams_installs_writable_streams(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    log_path = tmp_path / "app.log"
    launcher._ensure_std_streams(log_path=log_path)

    assert sys.stdout is not None
    assert sys.stderr is not None
    print("stdout works")          # must not raise
    sys.stderr.write("stderr works\n")
    assert log_path.exists()


def test_ensure_std_streams_noop_when_streams_present(tmp_path):
    """In dev mode (real console) the helper must not touch the streams."""
    before_out, before_err = sys.stdout, sys.stderr
    launcher._ensure_std_streams(log_path=tmp_path / "app.log")
    assert sys.stdout is before_out
    assert sys.stderr is before_err
    assert not (tmp_path / "app.log").exists()


def test_uvicorn_config_succeeds_after_stream_fix(monkeypatch, tmp_path):
    """End-to-end: after the fix, uvicorn.Config must construct cleanly."""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    launcher._ensure_std_streams(log_path=tmp_path / "app.log")
    assert sys.stdout is not None  # guard: fix actually ran before Config

    import uvicorn
    from fastapi import FastAPI

    config = uvicorn.Config(FastAPI(), host="127.0.0.1", port=59999, log_level="warning")
    server = uvicorn.Server(config)
    assert server is not None


def test_launcher_headless_fallback_when_pyqt6_missing():
    """The Raspberry Pi build ships without PyQt6 (no usable aarch64 wheels).

    Importing launcher without PyQt6 must succeed and set QT_AVAILABLE=False
    so main() takes the headless web-UI path instead of crashing.
    """
    import importlib

    assert launcher.QT_AVAILABLE is True  # dev env has PyQt6
    # Setting an entry to None forces ImportError; submodules must be blocked
    # too or the cached PyQt6.QtWidgets satisfies the import directly.
    saved = {
        name: sys.modules[name]
        for name in list(sys.modules)
        if name == "PyQt6" or name.startswith("PyQt6.")
    }
    for name in saved:
        sys.modules[name] = None
    try:
        importlib.reload(launcher)
        assert launcher.QT_AVAILABLE is False
        assert callable(launcher._run_headless)
    finally:
        sys.modules.update(saved)
        importlib.reload(launcher)  # restore Qt-enabled module state
    assert launcher.QT_AVAILABLE is True
