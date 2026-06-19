"""
System tray icon — show/hide the main window and quit actions.
"""
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu


class TrayIcon(QSystemTrayIcon):
    def __init__(self, window, parent=None):
        super().__init__(QIcon(), parent=parent)
        self._window = window
        self.setToolTip("CCTV Video Processor")

        menu = QMenu()
        show_action = menu.addAction("Show")
        show_action.triggered.connect(self._show_window)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._quit)
        self.setContextMenu(menu)

        self.activated.connect(self._on_activated)
        self.show()

    def _show_window(self):
        self._window.showNormal()
        self._window.raise_()
        self._window.activateWindow()

    def _quit(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()
