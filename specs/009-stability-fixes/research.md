# Research: Phase 9 — Stability Fixes

## Decision 1: Desktop Path on Windows (B6)

**Decision**: Use `ctypes.windll.shell32.SHGetFolderPathW(0, 0x0000, 0, 0, buf)` to resolve
`CSIDL_DESKTOP (0x0000)` on Windows; fall back to `Path.home() / "Desktop"` on all other platforms.

**Rationale**: `Path.home() / "Desktop"` returns `C:\Users\User\Desktop`. When OneDrive Desktop
Folder Backup is enabled, the actual Desktop folder that Windows Explorer shows is
`C:\Users\User\OneDrive\Desktop`. Shell folder `CSIDL_DESKTOP` always returns the real Desktop
regardless of OneDrive state. `SHGetFolderPathW` is available in `shell32.dll` on all Windows
versions (XP+) with no extra install. `ctypes` is a Python stdlib module — no new dependency.
The Windows Folder ID constants that `SHGetFolderPathW` uses are distinct from path separators
(Principle II guards), so using the Windows Shell API is the correct and minimal fix.

**Alternatives considered**:
- Registry read of `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders\Desktop`
  — works but requires parsing raw reg strings; SHGetFolderPath is the official API.
- `winreg` module — heavier; shell32 ctypes is standard pattern in Python docs.
- `os.path.expanduser("~") + "\\Desktop"` — same as `Path.home()`, wrong on OneDrive.
- `knownpaths` third-party package — extra dependency, Principle V violation.

---

## Decision 2: output_dir Persistence Across session.reset() (B6)

**Decision**: Move `output_dir` out of `_DEFAULTS` in `app/session.py` and into a separate
module-level `_PERSISTENT: dict` dict (still in-memory, still in session.py) that `reset()` 
intentionally does NOT clear.

**Rationale**: `output_dir` is the user's explicit choice of output folder — conceptually closer
to user configuration than to job state (detection results, events, paths). Wiping it on every
`session.reset()` call was an unintentional side-effect: the user set a folder once and expects
it to stick for the session. No disk persistence is involved; the dict lives entirely in RAM and
is lost when the process exits (consistent with Principle I). All reads and writes still go
through `session.update()` / `session.snapshot()` so the lock guarantees are preserved.

**Alternatives considered**:
- Persist `output_dir` to a config file — disk I/O, violates Principle I spirit.
- Pass `output_dir` as a parameter to job/create — requires API change; over-engineered.
- Keep in `_DEFAULTS` and restore it after `reset()` in the API layer — fragile, caller burden.

---

## Decision 3: FrameAnalyzer.is_available() Caching (B2)

**Decision**: Add a class-level `_availability_cache: bool | None = None` in `FrameAnalyzer`.
First call runs the real check (import + filesystem stat) and stores the result. All subsequent
calls return the cached value in O(1) with no I/O.

**Rationale**: The method is called on every `GET /api/job` (every 200 ms during detection).
The transformers import takes several seconds on first call (cold import). The filesystem stat
is cheap on a warm filesystem but still adds up over hundreds of polls. The availability check
result is stable for the process lifetime (model weights are never installed/removed during a
run). A simple class-level bool is the simplest possible cache — no TTL, no invalidation.

**Alternatives considered**:
- `functools.lru_cache` — identical outcome but overkill for a class method.
- Lazy-import transformers at module load — changes startup time, not poll latency.
- Move `is_available()` out of the hot poll path entirely — correct fix at the API layer; also
  done (check removed from `GET /api/job`; result included once in the job snapshot at startup).

---

## Decision 4: SIGINT / Clean Shutdown on Windows (B3)

**Decision**:
1. In `launcher.py`, install a `signal.SIGINT` handler that calls `QApplication.quit()`.
2. Start a `QTimer` with a 200 ms interval (no-op callback) so the Qt event loop yields to the
   Python signal handler regularly — without this, Qt's event loop on Windows swallows Ctrl+C.
3. In `shell/main_window.py` `check_shutdown`, after calling `_on_stop_backend()`, call
   `QTimer.singleShot(2000, QApplication.quit)` to auto-close 2 s after the backend stops.
4. Change `closeEvent` to only hide-to-tray when status is `"detecting"` or `"exporting"`;
   quit immediately otherwise.

**Rationale**: Python's `signal` module on Windows only delivers SIGINT when the Python
interpreter's signal-checking code runs — which requires the event loop to yield control back
to Python. A dummy `QTimer` polling every 200 ms ensures the interpreter's signal machinery
fires. This is a well-known pattern for Qt+Python SIGINT handling on Windows.

**Alternatives considered**:
- `app.exec_()` in a thread with `KeyboardInterrupt` propagation — doesn't work on Windows
  because Qt eats the console Ctrl+C before Python sees it.
- `SetConsoleCtrlHandler` via ctypes — works but complex; the QTimer approach is idiomatic.
- `signal.set_wakeup_fd` — lower-level, requires an OS pipe; more complex than necessary.

---

## Decision 5: Quick Report PDF Real Feedback (B4)

**Decision**:
- Python: In `on_pdf_finished(file_path, success)`, inject
  `window._cctvPdfResult = JSON.stringify({success, path})` into the browser page via
  `self._view.page().runJavaScript(...)`.
- JS: Replace the `setTimeout(3000 → "saved")` pattern. Before dispatch:
  (a) call `GET /api/job`, (b) validate status ≠ "detecting" and ≥1 included event; show
  inline error if not ready. After dispatch: set `window._cctvPdfResult = null`, show
  "Generating…", poll `window._cctvPdfResult` every 500 ms (timeout 120 s). On result,
  show `✅ Saved: <filename>` or `❌ PDF save failed`.

**Rationale**: The existing 200 ms `_bridge_timer` loop in `shell/main_window.py` already uses
the `window._cctv*` flag pattern for bidirectional Python↔JS signalling. Using the same
mechanism keeps the architecture consistent (Principle V). The pre-validation avoids generating
a hidden QWebEnginePage that would silently fail when `/api/job/report.html` returns 400.

**Alternatives considered**:
- WebSocket between Python and JS — far heavier; no WebSocket server in this stack.
- A new REST endpoint `GET /api/job/pdf-result` — adds API surface; the JS flag approach
  is already established and requires no new backend code.
- Native OS notification — platform-specific, complex.

---

## Decision 6: Florence-2 Terminal Noise Suppression (B5)

**Decision**: Wrap the `from_pretrained` calls in `FrameAnalyzer._run_analysis()` with
`contextlib.redirect_stdout(io.StringIO())` to suppress the MISSING-keys table (which Florence-2
prints to stdout). Add `warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")`
before the load. Apply it only for the two `from_pretrained` calls, not the whole method.

**Rationale**: The MISSING-keys output is from Florence-2's `trust_remote_code` model loading
code printing to stdout — it cannot be silenced via `logging` filters. Redirecting stdout
temporarily (while the model loads) is the minimal, targeted fix. FutureWarnings from
`transformers` are cosmetic (attention mask API that the transformers team has not yet enforced).
Suppressing only `transformers` module FutureWarnings avoids masking real warnings from app code.

**Alternatives considered**:
- Monkeypatching `print` — fragile; redirect_stdout is the idiomatic approach.
- `logging.disable(logging.WARNING)` — affects log level, not stdout print statements.
- Filtering at the HuggingFace config level — not exposed as a public API.
- Patching transformers source — ruled out; all fixes must stay in project source tree.
