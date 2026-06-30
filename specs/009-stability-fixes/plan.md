# Implementation Plan: Phase 9 — Stability Fixes

**Branch**: `009-stability-fixes` | **Date**: 2026-06-29 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/009-stability-fixes/spec.md`

## Summary

Six targeted bug fixes for a local desktop CCTV processor (FastAPI + PyQt6 + vanilla JS SPA):
browse race condition cancellation, FrameAnalyzer availability caching, SIGINT/clean-quit,
Quick Report PDF truthful feedback, Florence-2 terminal noise suppression, and correct Desktop
path on Windows 11 with OneDrive + preservation of output_dir across video loads.

## Technical Context

**Language/Version**: Python 3.12, JavaScript (ES2020, no build step)
**Primary Dependencies**: PyQt6, FastAPI/uvicorn, requests, ctypes (stdlib), transformers
**Storage**: In-memory session dict (`app/session.py`) — no disk persistence for job state
**Testing**: pytest 8.x (`pytest tests/ -v` from repo root)
**Target Platform**: Windows 10/11 (primary); macOS/Linux not affected by Desktop path fix
**Project Type**: Desktop app (PyQt6 shell + FastAPI backend + vanilla JS SPA)
**Performance Goals**: `/api/job` polls must return in <100 ms after first call
**Constraints**: Fully offline; no new pip dependencies; all fixes in project source tree
**Scale/Scope**: Single-user, single-job-at-a-time desktop app

## Constitution Check

### Pre-implementation

1. **Principle I — Session-First, No Persistence**
   - `output_dir` persistence: Moving `output_dir` to `_PERSISTENT` keeps it in-memory
     (no disk write). The field persists across `session.reset()` but is still lost on process
     exit. This is user-configuration-equivalent (user explicitly chose a folder; wiping it
     was unintentional). No new disk persistence. ✅ Compliant with Principle I intent.
   - All other fixes do not add persistence. ✅

2. **Principle II — Cross-Platform by Default**
   - `_get_desktop_path()` uses `sys.platform == "win32"` guard and
     `ctypes.windll.shell32.SHGetFolderPathW` only on Windows; falls back to
     `Path.home() / "Desktop"` everywhere else. This is OS-detection for a shell folder
     location, which is in the same spirit as the existing OS-detection exemption for
     "opening a folder in the file manager." All path construction after obtaining the
     Desktop string still uses `pathlib.Path`. ✅ Documented in Complexity Tracking.

3. **Principle III — Test-First**
   - New backend Python logic (`app/session.py`, `app/core/frame_analyzer.py`,
     `app/api/job.py`) requires failing tests written before implementation. Tests:
     `test_session_output_dir_persists_across_reset()`,
     `test_frame_analyzer_availability_cached()`, `test_get_desktop_path_returns_string()`.
   - Frontend JS changes (`static/js/pages/home.js`, `static/js/pages/export.js`):
     cite **frontend exemption**; scenarios documented in `quickstart.md`.
   - `launcher.py` and `shell/main_window.py` are Qt shell code (not `app/api` or
     `app/core`); SIGINT and close-event changes verified via manual smoke-test per
     the frontend-exemption pattern; documented in `quickstart.md`. ✅

4. **Principle IV — Callback-Driven Processing**: No changes to detection or export engines. ✅

5. **Principle V — Simplicity & YAGNI**: Each fix is the smallest targeted change that
   addresses the root cause. No new abstractions, no new dependencies. ✅

## Project Structure

### Documentation (this feature)

```text
specs/009-stability-fixes/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── quickstart.md        ← Phase 1 output (manual smoke-test scenarios)
├── checklists/
│   └── requirements.md  ← quality checklist
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code — Files Modified

```text
app/
├── session.py                          ← B6: _PERSISTENT dict; output_dir not cleared by reset()
├── core/
│   └── frame_analyzer.py               ← B2 + B5: availability cache; suppress stdout/FutureWarning
└── api/
    └── job.py                          ← B2 + B6: remove is_available() from poll; _get_desktop_path()

shell/
└── main_window.py                      ← B3 + B4 + B6: SIGINT auto-quit; PDF result injection; desktop path

launcher.py                             ← B3: SIGINT handler + dummy QTimer

static/js/pages/
├── home.js                             ← B1: abort token + error handling
└── export.js                           ← B4: pre-validate + real PDF feedback + open-folder link

tests/
├── test_session.py                     ← new tests for B2 + B6
└── test_frame_analyzer_cache.py        ← new tests for B2
```

## Implementation Details

### B1 — Browse Race Condition (`static/js/pages/home.js`)

**Root cause**: `pollPendingPath()` has no cancellation; multiple clicks create multiple chains.

**Fix**:
```javascript
let _browseToken = 0;   // module-level

// Browse button click:
function onBrowseClick() {
  const myToken = ++_browseToken;
  window.dispatchEvent(new CustomEvent("cctv:browse"));
  pollPendingPath(myToken, 0);
}

function pollPendingPath(token, attempts) {
  if (token !== _browseToken || attempts > 60) return;   // stale chain → stop
  fetch("/api/shell/pending-path")
    .then(r => r.json())
    .then(data => {
      if (token !== _browseToken) return;  // re-check after async
      if (data.path) loadFile(data.path);
      else setTimeout(() => pollPendingPath(token, attempts + 1), 200);
    })
    .catch(err => {
      if (token !== _browseToken) return;
      showLoadError("Browse failed — backend unreachable: " + err.message);
    });
}
```

Error display uses an existing `#load-error` element or injects a dismissable banner.

---

### B2 — Cache FrameAnalyzer.is_available() (`app/core/frame_analyzer.py`)

**Root cause**: Cold import + disk stat on every 200 ms poll.

**Fix**: Add `_availability_cache: bool | None = None` at class level. In `is_available()`:
```python
_availability_cache: bool | None = None

@classmethod
def is_available(cls) -> bool:
    if cls._availability_cache is not None:
        return cls._availability_cache
    try:
        from transformers import AutoModelForCausalLM  # noqa: F401
    except Exception:
        cls._availability_cache = False
        return False
    weights_dir = (
        Path.home() / ".cache" / "huggingface" / "hub" / "models--microsoft--Florence-2-base"
    )
    cls._availability_cache = weights_dir.exists()
    return cls._availability_cache
```

Also remove the `FrameAnalyzer.is_available()` call from the `GET /api/job` handler in
`app/api/job.py` (line ~143). The `florence_available` field is already returned in the job
snapshot for the settings panel — compute it once at startup or on demand, not on every poll.

---

### B3 — SIGINT + Clean Quit (`launcher.py`, `shell/main_window.py`)

**launcher.py** — add after `qt_app = QApplication(sys.argv)`:
```python
import signal

def _sigint_handler(*_):
    qt_app.quit()

signal.signal(signal.SIGINT, _sigint_handler)

# Qt's event loop doesn't yield to Python's signal handler unless a timer forces
# the interpreter's signal-checking code to run.
_sig_timer = QTimer()
_sig_timer.timeout.connect(lambda: None)  # no-op; just keeps Python awake
_sig_timer.start(200)
```

**shell/main_window.py** — `check_shutdown` callback change:
```python
def check_shutdown(val):
    if val:
        page.runJavaScript("window._cctvShutdown = false;")
        if self._on_stop_backend:
            self._on_stop_backend()
        QTimer.singleShot(2000, QApplication.instance().quit)  # auto-close 2 s after stop
```

**shell/main_window.py** — `closeEvent` change:
```python
def closeEvent(self, event: QCloseEvent):
    # Only hide to tray if a detection/export job is actively running.
    try:
        import requests as _req
        job = _req.get(f"{self._base_url}/api/job", timeout=0.5).json()
        active = job.get("status") in ("detecting", "exporting")
    except Exception:
        active = False

    tray = self._try_get_tray()
    if active and tray and tray.isVisible():
        self.hide()
        event.ignore()
    else:
        QApplication.instance().quit()
        event.accept()
```

---

### B4 — Quick Report PDF Real Feedback (`shell/main_window.py`, `static/js/pages/export.js`)

**Python — `on_pdf_finished` in `_generate_pdf_report`**:
```python
def on_pdf_finished(file_path, success):
    import json as _json
    result_js = (
        f"window._cctvPdfResult = {_json.dumps({'success': success, 'path': file_path})};"
    )
    self._view.page().runJavaScript(result_js)
    report_page.deleteLater()
    ...
```

Apply the same treatment to `_generate_intel_report_pdf`.

**Python — `on_load_finished` in `_generate_pdf_report`**:
When `ok` is False (report.html returned 4xx), inject an error result instead of silently
deleting the page:
```python
def on_load_finished(ok):
    if ok:
        report_page.printToPdf(pdf_path)
    else:
        # Inject failure so JS poll gets a result
        import json as _json
        err_js = f"window._cctvPdfResult = {_json.dumps({'success': False, 'path': ''})};"
        self._view.page().runJavaScript(err_js)
        report_page.deleteLater()
        ...
```

**JS — `export.js` Quick Report handler** (replace entire click handler):
```javascript
container.querySelector("#quick-report-btn").addEventListener("click", async () => {
  const btn = container.querySelector("#quick-report-btn");
  const statusEl = container.querySelector("#intel-report-status");

  // Pre-validate
  let job;
  try { job = await fetch("/api/job").then(r => r.json()); }
  catch { statusEl.textContent = "❌ Backend unreachable."; return; }

  if (!job.job_id) {
    statusEl.textContent = "❌ No active job — run detection first.";
    return;
  }
  if (job.status === "detecting") {
    statusEl.textContent = "❌ Detection in progress — wait for it to finish.";
    return;
  }
  const included = (job.events || []).filter(e => e.included);
  if (included.length === 0) {
    statusEl.textContent = "❌ No included events — include at least one on the Timeline page.";
    return;
  }

  btn.disabled = true;
  statusEl.textContent = "Generating…";
  window._cctvPdfResult = null;
  window.dispatchEvent(new CustomEvent("cctv:save-report-pdf"));

  // Poll for result (Python injects window._cctvPdfResult after PDF prints)
  const MAX_POLLS = 240;  // 120 s at 500 ms each
  let polls = 0;
  const pollId = setInterval(() => {
    polls++;
    if (window._cctvPdfResult !== null || polls >= MAX_POLLS) {
      clearInterval(pollId);
      const result = window._cctvPdfResult;
      window._cctvPdfResult = null;
      if (result && result.success) {
        const fname = result.path.replace(/.*[\\/]/, "");
        statusEl.textContent = "✅ Saved: " + fname;
      } else {
        statusEl.textContent = "❌ PDF save failed — check that detection is complete.";
      }
      btn.disabled = false;
    }
  }, 500);
});
```

---

### B5 — Suppress Florence-2 Terminal Noise (`app/core/frame_analyzer.py`)

In `_run_analysis()`, wrap the `from_pretrained` block:
```python
import io
import contextlib
import warnings

if cls._model is None:
    # ... compatibility patches ...
    with contextlib.redirect_stdout(io.StringIO()), \
         warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning, module="transformers")
        cls._processor = AutoProcessor.from_pretrained(
            "microsoft/Florence-2-base", trust_remote_code=True
        )
        cls._model = AutoModelForCausalLM.from_pretrained(
            "microsoft/Florence-2-base",
            dtype=torch.float32,
            device_map="cpu",
            trust_remote_code=True,
            attn_implementation="eager",
        )
```

---

### B6 — Correct Desktop Path + Preserve output_dir

**`app/session.py` — add `_PERSISTENT` dict**:
```python
_PERSISTENT: dict = {
    "output_dir": None,   # survives session.reset(); user chose this folder
}

def reset() -> None:
    with _lock:
        _state.clear()
        _state.update(copy.deepcopy(_DEFAULTS))
        # Merge persistent fields back in — output_dir survives video-load resets
        for k, v in _PERSISTENT.items():
            if k not in _state:
                _state[k] = v

def update(**kwargs) -> None:
    with _lock:
        _state.update(kwargs)
        # Keep _PERSISTENT in sync for fields it owns
        for k in _PERSISTENT:
            if k in kwargs:
                _PERSISTENT[k] = kwargs[k]
```

Remove `"output_dir": None` from `_DEFAULTS`.

**`app/api/job.py` — `_get_desktop_path()` helper**:
```python
import sys

def _get_desktop_path() -> str:
    if sys.platform == "win32":
        try:
            import ctypes, ctypes.wintypes
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(0, 0, 0, 0, buf)
            if buf.value:
                return buf.value
        except Exception:
            pass
    return str(Path.home() / "Desktop")
```

Replace all `str(Path.home() / "Desktop")` fallbacks in `app/api/job.py` with
`_get_desktop_path()` (video export, CSV/JSON export, intel-report — ~4 occurrences).

**`shell/main_window.py` — `_get_output_dir()`**:
```python
def _get_output_dir(self):
    try:
        job = requests.get(f"{self._base_url}/api/job", timeout=2).json()
        return job.get("output_dir") or _get_desktop_path()
    except Exception:
        return _get_desktop_path()
```

Add the same `_get_desktop_path()` helper at the top of `shell/main_window.py`.

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Principle II: OS detection (`sys.platform == "win32"`) for Desktop path | `pathlib.Path` has no API for Windows shell folder redirects; OneDrive remaps Desktop at the shell level, not the filesystem level | `Path.home() / "Desktop"` returns the wrong path on OneDrive machines — the core bug being fixed; the constitution's Principle II exemption for "opening a folder in the file manager" covers this case in spirit |
| Principle I nuance: `output_dir` not cleared by `session.reset()` | `output_dir` is a user-chosen output folder that should persist for the session; wiping it on every video load was unintended | Persisting to disk (config file) would be the alternative; in-memory `_PERSISTENT` keeps all job state in RAM, consistent with Principle I's no-disk guarantee; no key in `_DEFAULTS` is duplicated |

## Verification Plan

1. Browse race: click Browse twice quickly in < 500 ms → only one file dialog; second click
   cleanly cancels first poll chain.
2. Detection speed: run MOG2 → first `/api/job` status poll returns in < 1 s; all subsequent
   polls return in < 100 ms (no multi-second stall).
3. Ctrl+C: launch app from terminal, press Ctrl+C → process exits fully within 3 s.
4. Stop button: click Stop → app quits automatically after ~2 s.
5. Quick Report — no events: click Quick Report with no job → inline error, no PDF.
6. Quick Report — valid job: click → "Generating…" → "✅ Saved: filename" with correct path.
7. Quick Report — PDF fail: simulate path failure → "❌ PDF save failed".
8. Terminal noise: generate AI report → no MISSING-keys table, no FutureWarning lines.
9. OneDrive Desktop: export with no folder set → file appears on real visible Desktop.
10. output_dir persists: set folder → load new video → export → file in previously-set folder.
11. `python -m pytest tests/ -q` → all tests pass (136 baseline + new tests).
