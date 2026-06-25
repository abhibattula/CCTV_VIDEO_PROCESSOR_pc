"""
PyQt6 main window — QWebEngineView wrapping the FastAPI web UI.

Responsibilities:
- Wait for backend health before loading the web URL
- Inject a JS bridge so cctv:browse / cctv:browse-folder events open QFileDialog
- Handle native OS file drag-and-drop with FR-017 safety check
- Close-to-tray support
"""
import threading
import time
from pathlib import Path

import requests

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QCloseEvent
from PyQt6.QtWidgets import QFileDialog, QMainWindow, QSystemTrayIcon, QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage

from app.config import BACKEND_HOST, BACKEND_PORT


class MainWindow(QMainWindow):
    def __init__(self, backend_port: int = BACKEND_PORT, on_stop_backend=None):
        super().__init__()
        self._base_url = f"http://{BACKEND_HOST}:{backend_port}"
        self._on_stop_backend = on_stop_backend

        self.setWindowTitle("CCTV Video Processor")
        self.resize(1280, 800)

        self._view = QWebEngineView()
        # Allow video autoplay without requiring a user gesture — needed so that
        # preview clips can play automatically after the async POST completes.
        from PyQt6.QtWebEngineCore import QWebEngineSettings
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False
        )
        # Best-effort clipboard access for the debug log's Copy button — the
        # JS side falls back to execCommand('copy') if this still gets denied.
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True
        )
        self.setCentralWidget(self._view)

        self.setAcceptDrops(True)

        # Poll backend until ready, then load the UI
        threading.Thread(target=self._wait_for_backend, daemon=True).start()

        # Timer to check for JS bridge signals injected by the page JS
        self._bridge_timer = QTimer()
        self._bridge_timer.timeout.connect(self._handle_browse_flags)
        self._bridge_timer.start(200)

        self._tray: QSystemTrayIcon | None = None

    # ── Backend readiness ─────────────────────────────────────────────────────

    def _wait_for_backend(self):
        for _ in range(100):  # up to 10 seconds
            try:
                r = requests.get(f"{self._base_url}/api/health", timeout=1)
                if r.ok:
                    QTimer.singleShot(0, self._load_ui)
                    return
            except Exception:
                pass
            time.sleep(0.1)
        QTimer.singleShot(0, self._load_ui)  # load anyway and let it show error

    def _load_ui(self):
        self._view.load(QUrl(f"{self._base_url}/"))
        self._inject_js_bridge()

    # ── JS bridge ─────────────────────────────────────────────────────────────

    def _inject_js_bridge(self):
        """Inject JS that sets window flags when cctv: events are fired."""
        js = """
        window._cctvBrowse = false;
        window._cctvBrowseFolder = false;
        window._cctvShutdown = false;
        window._cctvSaveReportPdf = false;
        window.addEventListener('cctv:browse', function() {
            window._cctvBrowse = true;
        });
        window.addEventListener('cctv:browse-folder', function() {
            window._cctvBrowseFolder = true;
        });
        window.addEventListener('cctv:save-report-pdf', function() {
            window._cctvSaveReportPdf = true;
        });
        window._cctvGenerateIntelReport = false;
        window._cctvIntelReportPdfPath = "";
        window.addEventListener('cctv:generate-intel-report', function(e) {
            window._cctvIntelReportPdfPath = e.detail && e.detail.pdf_path ? e.detail.pdf_path : "";
            window._cctvGenerateIntelReport = true;
        });
        """
        self._view.page().runJavaScript(js)
        # Re-inject on every new page load (navigation resets the JS state)
        self._view.loadFinished.connect(lambda ok: self._view.page().runJavaScript(js))

    def _handle_browse_flags(self):
        """Called every 200ms to check if JS has requested a file dialog."""
        page = self._view.page()

        def check_browse(val):
            if val:
                page.runJavaScript("window._cctvBrowse = false;")
                path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Open Video File",
                    str(Path.home()),
                    "Video Files (*.mp4 *.avi *.mov *.mkv *.m4v *.ts *.mts);;All Files (*)",
                )
                if path:
                    self._post_path(path)

        def check_browse_folder(val):
            if val:
                page.runJavaScript("window._cctvBrowseFolder = false;")
                folder = QFileDialog.getExistingDirectory(
                    self, "Choose Output Folder", str(Path.home())
                )
                if folder:
                    self._post_path(folder)

        def check_shutdown(val):
            if val:
                page.runJavaScript("window._cctvShutdown = false;")
                if self._on_stop_backend:
                    self._on_stop_backend()

        def check_save_report_pdf(val):
            if val:
                page.runJavaScript("window._cctvSaveReportPdf = false;")
                self._generate_pdf_report()

        page.runJavaScript("window._cctvBrowse", check_browse)
        page.runJavaScript("window._cctvBrowseFolder", check_browse_folder)
        page.runJavaScript("window._cctvShutdown", check_shutdown)
        page.runJavaScript("window._cctvSaveReportPdf", check_save_report_pdf)

        def check_intel_report(val):
            if val:
                import json as _json
                try:
                    data = _json.loads(val)
                except Exception:
                    return
                pdf_path = data.get("path", "")
                page.runJavaScript(
                    "window._cctvGenerateIntelReport = false; window._cctvIntelReportPdfPath = '';"
                )
                if pdf_path:
                    self._generate_intel_report_pdf(pdf_path)

        page.runJavaScript(
            'JSON.stringify({flag: window._cctvGenerateIntelReport, path: window._cctvIntelReportPdfPath})',
            check_intel_report,
        )

    def _get_output_dir(self):
        try:
            job = requests.get(f"{self._base_url}/api/job", timeout=2).json()
            return job.get("output_dir") or str(Path.home() / "Desktop")
        except Exception:
            return str(Path.home() / "Desktop")

    def _generate_pdf_report(self):
        output_dir = self._get_output_dir()
        pdf_path = str(Path(output_dir) / f"incident_report_{time.strftime('%Y%m%d_%H%M%S')}.pdf")

        report_page = QWebEnginePage(self._view.page().profile(), self)
        report_page.load(QUrl(f"{self._base_url}/api/job/report.html"))

        def on_load_finished(ok):
            if ok:
                report_page.printToPdf(pdf_path)
            else:
                report_page.deleteLater()
                try:
                    self._pending_report_pages.remove(report_page)
                except ValueError:
                    pass

        def on_pdf_finished(file_path, success):
            report_page.deleteLater()
            try:
                self._pending_report_pages.remove(report_page)
            except ValueError:
                pass

        report_page.loadFinished.connect(on_load_finished)
        report_page.pdfPrintingFinished.connect(on_pdf_finished)
        self._pending_report_pages = getattr(self, "_pending_report_pages", [])
        self._pending_report_pages.append(report_page)

    def _generate_intel_report_pdf(self, pdf_path: str):
        report_page = QWebEnginePage(self._view.page().profile(), self)
        report_page.load(QUrl(f"{self._base_url}/api/job/intel-report.html"))

        def on_load_finished(ok):
            if ok:
                report_page.printToPdf(pdf_path)
            else:
                report_page.deleteLater()
                try:
                    self._pending_report_pages.remove(report_page)
                except ValueError:
                    pass

        def on_pdf_finished(file_path, success):
            report_page.deleteLater()
            try:
                self._pending_report_pages.remove(report_page)
            except ValueError:
                pass

        report_page.loadFinished.connect(on_load_finished)
        report_page.pdfPrintingFinished.connect(on_pdf_finished)
        self._pending_report_pages = getattr(self, "_pending_report_pages", [])
        self._pending_report_pages.append(report_page)

    def _post_path(self, path: str):
        try:
            requests.post(
                f"{self._base_url}/api/shell/filepath",
                json={"path": path},
                timeout=2,
            )
        except Exception:
            pass

    # ── Native drag & drop (FR-017) ───────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if not path:
            return

        # FR-017: if session is completed with uncollected events, navigate to home
        # so the web UI can show the confirmation modal before calling job/create
        try:
            job = requests.get(f"{self._base_url}/api/job", timeout=1).json()
            if (job.get("status") == "completed"
                    and not job.get("output_path")
                    and job.get("events")):
                # Navigate to home — JS there will handle the confirmation modal
                self._view.load(QUrl(f"{self._base_url}/"))
                # Post the pending path so the modal can pick it up after user confirms
                self._post_path(path)
                return
        except Exception:
            pass

        self._post_path(path)
        # Trigger job creation via the pending-path polling mechanism already in home.js
        self._view.load(QUrl(f"{self._base_url}/"))

    # ── Close to tray ─────────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent):
        tray = self._try_get_tray()
        if tray and tray.isVisible():
            self.hide()
            event.ignore()
        else:
            event.accept()

    def _try_get_tray(self) -> QSystemTrayIcon | None:
        if self._tray is None:
            try:
                from PyQt6.QtWidgets import QSystemTrayIcon
                from PyQt6.QtGui import QIcon
                self._tray = QSystemTrayIcon(QIcon(), parent=self)
                self._tray.setToolTip("CCTV Video Processor")
                self._tray.activated.connect(lambda _: self.show())
            except Exception:
                pass
        return self._tray
