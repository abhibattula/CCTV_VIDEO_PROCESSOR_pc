"""
Tests for Qt shell logic — _get_desktop_path, closeEvent, _handle_browse_flags (US5, Phase 10).
Runs without PyQt6 installed by patching sys.modules before importing shell.main_window.
"""
import sys
import time
import types
from unittest.mock import MagicMock

import pytest


def _make_qt_stubs():
    """Build minimal sys.modules stubs so shell.main_window can be imported headlessly."""

    class _FakeQMainWindow:
        """Real base class so 'class MainWindow(_FakeQMainWindow)' works."""
        def __init__(self, *a, **kw):
            pass
        def __getattr__(self, name):
            m = MagicMock()
            object.__setattr__(self, name, m)
            return m

    qt_core = types.SimpleNamespace(
        QTimer=MagicMock(),
        QUrl=MagicMock(),
        Qt=MagicMock(),
        pyqtSignal=MagicMock(),
    )
    qt_gui = types.SimpleNamespace(
        QIcon=MagicMock(),
        QCloseEvent=MagicMock(),
        QDragEnterEvent=MagicMock(),
        QDropEvent=MagicMock(),
    )
    qt_widgets = types.SimpleNamespace(
        QApplication=MagicMock(),
        QMainWindow=_FakeQMainWindow,
        QSystemTrayIcon=MagicMock(),
        QMenu=MagicMock(),
        QAction=MagicMock(),
        QFileDialog=MagicMock(),
    )
    qt_webengine_widgets = types.SimpleNamespace(QWebEngineView=MagicMock())
    qt_webengine_core = types.SimpleNamespace(
        QWebEnginePage=MagicMock(),
        QWebEngineSettings=MagicMock(),
    )
    qt_webchannel = types.SimpleNamespace(QWebChannel=MagicMock())

    # Stub requests so the background health-check thread exits immediately
    fake_requests = MagicMock()
    fake_requests.get.return_value.ok = True

    return {
        "PyQt6": MagicMock(),
        "PyQt6.QtCore": qt_core,
        "PyQt6.QtGui": qt_gui,
        "PyQt6.QtWidgets": qt_widgets,
        "PyQt6.QtWebEngineWidgets": qt_webengine_widgets,
        "PyQt6.QtWebEngineCore": qt_webengine_core,
        "PyQt6.QtWebChannel": qt_webchannel,
        "requests": fake_requests,
    }


@pytest.fixture
def mw_module():
    stubs = _make_qt_stubs()
    originals = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    sys.modules.pop("shell.main_window", None)
    try:
        import shell.main_window as mw
        yield mw
    finally:
        for k, v in originals.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        sys.modules.pop("shell.main_window", None)


def test_get_desktop_path_returns_nonempty_string(mw_module):
    result = mw_module._get_desktop_path()
    assert isinstance(result, str) and len(result) > 0


def test_close_event_hides_when_detecting(mw_module, monkeypatch):
    monkeypatch.setattr(
        mw_module.requests, "get",
        MagicMock(return_value=MagicMock(**{"ok": True, "json.return_value": {"status": "detecting"}})),
    )
    inst = mw_module.MainWindow(backend_port=9999)
    time.sleep(0.05)  # let init thread finish
    event = MagicMock()
    inst.closeEvent(event)
    event.ignore.assert_called_once()


def test_close_event_quits_when_idle(mw_module, monkeypatch):
    monkeypatch.setattr(
        mw_module.requests, "get",
        MagicMock(return_value=MagicMock(**{"ok": True, "json.return_value": {"status": "idle"}})),
    )
    inst = mw_module.MainWindow(backend_port=9999)
    time.sleep(0.05)
    event = MagicMock()
    inst.closeEvent(event)
    mw_module.QApplication.instance.return_value.quit.assert_called()


def test_close_event_quits_when_backend_raises(mw_module, monkeypatch):
    monkeypatch.setattr(
        mw_module.requests, "get",
        MagicMock(side_effect=ConnectionError("refused")),
    )
    inst = mw_module.MainWindow(backend_port=9999)
    time.sleep(0.05)
    event = MagicMock()
    inst.closeEvent(event)
    mw_module.QApplication.instance.return_value.quit.assert_called()


def test_check_shutdown_schedules_qtimer(mw_module):
    inst = mw_module.MainWindow(backend_port=9999)
    time.sleep(0.05)

    page_mock = inst._view.page.return_value

    def js_side_effect(script, *args):
        if not args:
            return
        callback = args[0]
        if "_cctvShutdown" in script and "= false" not in script:
            callback(True)
        elif "JSON.stringify" in script:
            callback('{"flag": false, "path": ""}')
        else:
            callback(False)

    page_mock.runJavaScript.side_effect = js_side_effect

    qt_core = sys.modules["PyQt6.QtCore"]
    qt_core.QTimer.singleShot.reset_mock()

    inst._handle_browse_flags()

    delays = [call.args[0] for call in qt_core.QTimer.singleShot.call_args_list
              if call.args]
    assert 2000 in delays
