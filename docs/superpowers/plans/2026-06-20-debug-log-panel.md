# Debug Log Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hidden-by-default, nav-bar-toggled debug log drawer that captures console output, fetch/network activity, uncaught JS errors, and `<video>` element lifecycle events, so the user can self-diagnose client-side issues without browser DevTools (which `QWebEngineView` does not expose).

**Architecture:** A single new ES module, `static/js/debug-log.js`, monkey-patches `console.*`/`window.fetch`, registers global error listeners, and renders its UI (nav toggle + bottom drawer) directly into `#app-nav`/`document.body` — outside the SPA router's `#app` container — so the log buffer and UI survive page navigation untouched. `app.js` installs it once at startup; `timeline.js` opts its preview `<video>` element into capture via one explicit call.

**Tech Stack:** Vanilla ES modules (no build step, no npm/Node in this project), FastAPI backend (unchanged), PyQt6 `QWebEngineView` as the runtime.

## Global Constraints

- Ring buffer caps at 500 entries (oldest dropped) — exact value from the approved spec (`docs/superpowers/specs/2026-06-20-debug-log-panel-design.md`).
- Drawer is `position: fixed`, `height: 240px` — exact value from the spec.
- No JS test runner exists in this project (no `package.json`, pytest only covers the FastAPI backend). Per the approved spec, verification is via temporary, throwaway Python scripts that drive a real `QWebEngineView` instance and read state back via `runJavaScript` — not added to the permanent `tests/` suite. Delete each diagnostic script at the end of its task.
- ES module imports in this codebase use **absolute** paths (`/static/js/...`), matching `session-state.js`'s existing import style in `timeline.js`/`home.js` — follow this convention, not relative `../` imports.
- CSS additions must reuse existing design tokens from `static/css/base.css` (`--surface`, `--border`, `--text-dim`, `--accent`, `--success`, `--warning`, `--danger`, `--radius`) — do not introduce new color literals.
- The existing pytest suite (`tests/`) must remain fully passing (`python -m pytest tests/ -q` → currently `60 passed, 2 skipped`) after every task, since this feature touches no Python files but must not be assumed risk-free without checking.
- **Git policy:** this project's standing rule is to commit only when the user explicitly asks. Each task below ends with a `git add` + `git commit` step as the writing-plans template requires — **do not run it automatically; confirm with the user first** (or batch all commits at the end of the plan, per the user's preference at execution time).

---

### Task 1: Core capture engine (console, fetch, global errors)

**Files:**
- Create: `static/js/debug-log.js`
- Test (temporary, delete after this task): `_diag_debug_log_core.py` (repo root)

**Interfaces:**
- Produces: `installDebugLog()`, `getDebugEntries()`, `clearDebugEntries()` — all exported from `/static/js/debug-log.js`. Task 2 extends `installDebugLog()`'s body (adds one `buildUI();` call) and adds new module-level state; Task 3 adds `logVideoEvents(videoEl, label)` to the same file. Entry shape produced by `getDebugEntries()`: `{ ts: string (ISO), type: "log"|"warn"|"error"|"fetch"|"video", text: string }`.

**Prerequisite:** the backend must be reachable at `http://127.0.0.1:5151` (the diagnostic loads the real module over HTTP from the static file mount, since ES module imports need a real origin — `file://`/`data:` URLs can't resolve them). Start it if needed:
```bash
python launcher.py &
sleep 5
curl -s http://127.0.0.1:5151/api/system/stats
```
Expected: a JSON line like `{"cpu_pct":...,"ram_pct":...,"cpu_temp":...}`. If you instead get a connection error, wait a few seconds and retry — the backend takes a moment to bind.

- [ ] **Step 1: Write the failing test**

Create `_diag_debug_log_core.py`:

```python
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QTimer

app = QApplication(sys.argv)
view = QWebEngineView()

html = """
<html><body>
<script type="module">
  window.__result = "PENDING";
  import { installDebugLog, getDebugEntries, clearDebugEntries } from "/static/js/debug-log.js";
  installDebugLog();
  clearDebugEntries();
  console.log("hello", 42);
  console.warn("a warning");
  console.error("an error");
  fetch("/api/system/stats").then(() => {
    setTimeout(() => {
      const entries = getDebugEntries();
      const has = (type, substr) => entries.some(e => e.type === type && e.text.includes(substr));
      const ok = has("log", "hello 42") && has("warn", "a warning") && has("error", "an error")
               && has("fetch", "GET /api/system/stats")
               && entries.some(e => e.type === "fetch" && e.text.includes("200"));
      window.__result = ok ? "PASS" : "FAIL:" + JSON.stringify(entries);
    }, 400);
  }).catch(err => { window.__result = "FAIL:fetch threw " + err; });
</script>
</body></html>
"""
view.setHtml(html, QUrl("http://127.0.0.1:5151/"))

def check():
    view.page().runJavaScript("window.__result", lambda r: (print("RESULT:", r), app.quit()))

QTimer.singleShot(2000, check)
sys.exit(app.exec())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python _diag_debug_log_core.py`
Expected: `RESULT: PENDING` (the module import 404s since `static/js/debug-log.js` doesn't exist yet, so the `<script type="module">` block throws and never reaches the `console.log` calls).

- [ ] **Step 3: Write minimal implementation**

Create `static/js/debug-log.js`:

```js
/**
 * In-app debug log — captures console output, fetch activity, and uncaught
 * errors into an in-memory ring buffer, since QWebEngineView exposes no
 * DevTools console/network tab to the end user.
 */

const MAX_ENTRIES = 500;
let buffer = [];
let onAppend = null; // set by buildUI() once the drawer exists (Task 2)

function push(type, text) {
  buffer.push({ ts: new Date().toISOString(), type, text });
  if (buffer.length > MAX_ENTRIES) buffer.shift();
  if (onAppend) onAppend();
}

export function getDebugEntries() {
  return buffer.slice();
}

export function clearDebugEntries() {
  buffer = [];
  if (onAppend) onAppend();
}

function formatArgs(args) {
  try {
    return args.map(a => (typeof a === "string" ? a : JSON.stringify(a))).join(" ");
  } catch {
    return "[unformattable log args]";
  }
}

function installConsolePatch() {
  ["log", "warn", "error"].forEach(level => {
    const original = console[level].bind(console);
    console[level] = (...args) => {
      original(...args);
      push(level, formatArgs(args));
    };
  });
}

function installFetchPatch() {
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const url = typeof args[0] === "string" ? args[0] : (args[0] && args[0].url) || String(args[0]);
    const method = (args[1] && args[1].method) ? args[1].method.toUpperCase() : "GET";
    const start = performance.now();
    push("fetch", `→ ${method} ${url}`);
    try {
      const resp = await originalFetch(...args);
      push("fetch", `← ${resp.status} ${url} (${Math.round(performance.now() - start)}ms)`);
      return resp;
    } catch (err) {
      push("fetch", `✗ ${url}: ${err.message}`);
      throw err;
    }
  };
}

function installGlobalErrorCapture() {
  window.addEventListener("error", (e) => {
    push("error", `Uncaught: ${e.message} (${e.filename}:${e.lineno})`);
  });
  window.addEventListener("unhandledrejection", (e) => {
    push("error", `Unhandled rejection: ${e.reason}`);
  });
}

let installed = false;

export function installDebugLog() {
  if (installed) return;
  installed = true;
  installConsolePatch();
  installFetchPatch();
  installGlobalErrorCapture();
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python _diag_debug_log_core.py`
Expected: `RESULT: PASS`

If it prints `RESULT: FAIL:...`, the failure message includes the actual buffer contents — compare against the five expected entries (`log`, `warn`, `error`, and two `fetch` lines) to see which is missing or malformed before changing anything else.

- [ ] **Step 5: Delete the diagnostic script**

```bash
rm _diag_debug_log_core.py
```

- [ ] **Step 6: Run full backend test suite (confirm no regression)**

Run: `python -m pytest tests/ -q --tb=short`
Expected: `60 passed, 2 skipped` (unchanged — this task touches no Python files).

- [ ] **Step 7: Commit (confirm with user first — see Global Constraints)**

```bash
git add static/js/debug-log.js
git commit -m "feat: add debug log capture engine (console/fetch/errors)"
```

---

### Task 2: Drawer UI, nav toggle, Copy/Clear/Close

**Files:**
- Modify: `static/js/debug-log.js` (add UI-building code; extend `installDebugLog()`)
- Modify: `static/css/base.css` (append debug drawer styles)
- Modify: `static/js/app.js:1-7` (import and call `installDebugLog()`)
- Modify: `shell/main_window.py:32-39` (grant clipboard JS access)
- Test (temporary, delete after this task): `_diag_debug_log_ui.py` (repo root)

**Interfaces:**
- Consumes: `push()` (internal), `buffer` (internal), `getDebugEntries()`/`clearDebugEntries()` from Task 1.
- Produces: drawer DOM with `id="debug-body"`/`id="debug-count"`, button `class="debug-toggle"`, drawer `class="debug-drawer"` (toggles `.open`). Task 3 relies on none of this directly — `logVideoEvents()` only calls the existing `push()`.

**Prerequisite:** same as Task 1 — backend reachable at `http://127.0.0.1:5151`.

- [ ] **Step 1: Write the failing test**

Create `_diag_debug_log_ui.py`:

```python
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QTimer

app = QApplication(sys.argv)
view = QWebEngineView()

html = """
<html><body>
  <nav class="app-nav" id="app-nav">
    <div class="app-nav__links"></div>
  </nav>
<script type="module">
  window.__result = "PENDING";
  import { installDebugLog, clearDebugEntries } from "/static/js/debug-log.js";
  installDebugLog();
  clearDebugEntries();

  const toggle = document.querySelector(".debug-toggle");
  const drawer = document.querySelector(".debug-drawer");
  if (!toggle || !drawer) {
    window.__result = "FAIL:missing toggle or drawer element";
  } else {
    toggle.click();
    console.log("row-check-marker");
    setTimeout(() => {
      const isOpen = drawer.classList.contains("open");
      const body = document.getElementById("debug-body");
      const hasRow = body && body.innerHTML.includes("row-check-marker")
                          && body.innerHTML.includes("debug-drawer__row--log");
      window.__result = (isOpen && hasRow) ? "PASS" : `FAIL:open=${isOpen} html=${body ? body.innerHTML : "NO_BODY"}`;
    }, 200);
  }
</script>
</body></html>
"""
view.setHtml(html, QUrl("http://127.0.0.1:5151/"))

def check():
    view.page().runJavaScript("window.__result", lambda r: (print("RESULT:", r), app.quit()))

QTimer.singleShot(1500, check)
sys.exit(app.exec())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python _diag_debug_log_ui.py`
Expected: `RESULT: FAIL:missing toggle or drawer element` (no UI exists yet — `installDebugLog()` from Task 1 only installs capture patches).

- [ ] **Step 3: Write minimal implementation**

In `static/js/debug-log.js`, add the following **above** the `let installed = false;` line:

```js
let drawerEl = null;
let bodyEl   = null;
let countEl  = null;

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderRows() {
  if (countEl) countEl.textContent = `${buffer.length} entries`;
  if (!bodyEl) return;
  bodyEl.innerHTML = buffer.map(e =>
    `<div class="debug-drawer__row debug-drawer__row--${e.type}">[${e.ts.slice(11, 19)}] ${e.type.toUpperCase()}: ${escapeHtml(e.text)}</div>`
  ).join("");
  bodyEl.scrollTop = bodyEl.scrollHeight;
}

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Fallback for embedded WebViews where the async Clipboard API's
    // permission model rejects the call even with a real user gesture —
    // confirmed against this project's QtWebEngine build during planning.
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
}

function buildUI() {
  const navBar = document.getElementById("app-nav");
  if (!navBar) return; // no nav bar on this page — capture still active, just no UI

  const toggle = document.createElement("button");
  toggle.className   = "debug-toggle";
  toggle.textContent = "🐛 Debug";
  navBar.appendChild(toggle);

  drawerEl = document.createElement("div");
  drawerEl.className = "debug-drawer";
  drawerEl.innerHTML = `
    <div class="debug-drawer__header">
      <h4>Debug Log</h4>
      <span class="debug-drawer__count" id="debug-count">0 entries</span>
      <button class="btn" id="debug-copy" style="padding:3px 10px;font-size:11px">Copy</button>
      <button class="btn" id="debug-clear" style="padding:3px 10px;font-size:11px">Clear</button>
      <button class="btn" id="debug-close" style="padding:3px 10px;font-size:11px">✕</button>
    </div>
    <div class="debug-drawer__body" id="debug-body"></div>
  `;
  document.body.appendChild(drawerEl);

  bodyEl  = drawerEl.querySelector("#debug-body");
  countEl = drawerEl.querySelector("#debug-count");

  toggle.addEventListener("click", () => {
    drawerEl.classList.toggle("open");
    if (drawerEl.classList.contains("open")) renderRows();
  });
  drawerEl.querySelector("#debug-close").addEventListener("click", () => {
    drawerEl.classList.remove("open");
  });
  drawerEl.querySelector("#debug-clear").addEventListener("click", clearDebugEntries);
  drawerEl.querySelector("#debug-copy").addEventListener("click", async () => {
    const text = buffer.map(e => `[${e.ts}] ${e.type.toUpperCase()}: ${e.text}`).join("\n");
    const ok = await copyToClipboard(text);
    countEl.textContent = ok ? `${buffer.length} entries (copied)` : "Copy failed — select text manually";
  });

  onAppend = renderRows;
  renderRows();
}
```

Then change `installDebugLog()` (written in Task 1) to call it:

```js
export function installDebugLog() {
  if (installed) return;
  installed = true;
  installConsolePatch();
  installFetchPatch();
  installGlobalErrorCapture();
  buildUI();
}
```

Append to the end of `static/css/base.css`:

```css
/* ── Debug log panel ─────────────────────────────────────────────────────── */
.debug-toggle {
  margin-left: 12px;
  padding: 5px 10px;
  border-radius: var(--radius);
  font-size: 12px;
  color: var(--text-dim);
  background: transparent;
  border: 1px solid var(--border);
  cursor: pointer;
}
.debug-toggle:hover { background: var(--surface2); color: var(--text); }

.debug-drawer {
  position: fixed;
  left: 0; right: 0; bottom: 0;
  height: 240px;
  background: var(--surface);
  border-top: 1px solid var(--border);
  z-index: 2000;
  display: none;
  flex-direction: column;
}
.debug-drawer.open { display: flex; }

.debug-drawer__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.debug-drawer__header h4 { font-size: 12px; flex: 1; }
.debug-drawer__count { font-size: 11px; color: var(--text-dim); white-space: nowrap; }

.debug-drawer__body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  font-family: Consolas, "Courier New", monospace;
  font-size: 11.5px;
}
.debug-drawer__row { padding: 2px 0; white-space: pre-wrap; word-break: break-all; }
.debug-drawer__row--log   { color: var(--text-dim); }
.debug-drawer__row--warn  { color: var(--warning); }
.debug-drawer__row--error { color: var(--danger); }
.debug-drawer__row--fetch { color: var(--accent); }
.debug-drawer__row--video { color: var(--success); }
```

In `static/js/app.js`, change the top of the file from:

```js
/**
 * Client-side SPA router.
 * Pages register themselves via window._cctvPages[path] = { mount(container) }.
 * navigate(path) loads the page module if needed, then calls mount().
 */

const routes = {
```

to:

```js
/**
 * Client-side SPA router.
 * Pages register themselves via window._cctvPages[path] = { mount(container) }.
 * navigate(path) loads the page module if needed, then calls mount().
 */
import { installDebugLog } from "/static/js/debug-log.js";
installDebugLog();

const routes = {
```

In `shell/main_window.py`, change lines 32-38 from:

```python
        self._view = QWebEngineView()
        # Allow video autoplay without requiring a user gesture — needed so that
        # preview clips can play automatically after the async POST completes.
        from PyQt6.QtWebEngineCore import QWebEngineSettings
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False
        )
```

to:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python _diag_debug_log_ui.py`
Expected: `RESULT: PASS`

- [ ] **Step 5: Delete the diagnostic script**

```bash
rm _diag_debug_log_ui.py
```

- [ ] **Step 6: Run full backend test suite (confirm no regression)**

Run: `python -m pytest tests/ -q --tb=short`
Expected: `60 passed, 2 skipped`

- [ ] **Step 7: Commit (confirm with user first — see Global Constraints)**

```bash
git add static/js/debug-log.js static/css/base.css static/js/app.js shell/main_window.py
git commit -m "feat: add debug log drawer UI with nav toggle and copy/clear"
```

---

### Task 3: Video element lifecycle capture, wired into the preview modal

**Files:**
- Modify: `static/js/debug-log.js` (add `logVideoEvents` export)
- Modify: `static/js/pages/timeline.js:7` and `:370` (import + call `logVideoEvents`)
- Test (temporary, delete after this task): `_diag_debug_log_video.py` (repo root)

**Interfaces:**
- Produces: `logVideoEvents(videoEl: HTMLVideoElement, label: string)` exported from `/static/js/debug-log.js`. Calls the existing `push()` from Task 1 with `type: "video"`.
- Consumes: nothing new from Task 2 — only `push()` from Task 1.

**Prerequisite:** same as Task 1 — backend reachable at `http://127.0.0.1:5151`.

- [ ] **Step 1: Write the failing test**

This test exercises both the success path (a real generated preview clip, reusing the already-fixed VP8/Opus `generate_preview()`) and the failure path (a 404 URL), to confirm `logVideoEvents` correctly logs both `loadedmetadata` and `error` cases.

Create `_diag_debug_log_video.py`:

```python
import sys
from app.core.export_engine import generate_preview
from app.utils.ffmpeg_path import get_ffmpeg
import subprocess

# Build a tiny synthetic source clip and a real preview from it, exactly like
# the manual verification used to confirm the VP8/Opus codec fix.
SRC = r"C:\Users\User\AppData\Local\Temp\_diag_video_src.mp4"
subprocess.run([
    get_ffmpeg(), "-hide_banner", "-loglevel", "error",
    "-f", "lavfi", "-i", "testsrc=duration=10:size=320x180:rate=10",
    "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-y", SRC,
], check=True)

out_path = generate_preview(source_path=SRC, start_s=2.0, end_s=5.0, token="aaaaaaaaaaaaaaaa")
print("Generated preview at:", out_path)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QTimer

app = QApplication(sys.argv)
view = QWebEngineView()

html = """
<html><body>
<video id="good" muted preload="auto"></video>
<video id="bad" muted preload="auto"></video>
<script type="module">
  window.__result = "PENDING";
  import { installDebugLog, getDebugEntries, clearDebugEntries, logVideoEvents } from "/static/js/debug-log.js";
  installDebugLog();
  clearDebugEntries();

  const good = document.getElementById("good");
  const bad  = document.getElementById("bad");
  logVideoEvents(good, "good-test");
  logVideoEvents(bad, "bad-test");

  good.src = "/api/preview/aaaaaaaaaaaaaaaa.webm";
  good.load();
  bad.src = "/api/preview/doesnotexist0000.webm";
  bad.load();

  setTimeout(() => {
    const entries = getDebugEntries();
    const hasGood = entries.some(e => e.type === "video" && e.text.includes("[good-test] loadedmetadata"));
    const hasBad  = entries.some(e => e.type === "video" && e.text.includes("[bad-test] ERROR code="));
    window.__result = (hasGood && hasBad) ? "PASS" : "FAIL:" + JSON.stringify(entries);
  }, 1500);
</script>
</body></html>
"""
view.setHtml(html, QUrl("http://127.0.0.1:5151/"))

def check():
    view.page().runJavaScript("window.__result", lambda r: (print("RESULT:", r), app.quit()))

QTimer.singleShot(3000, check)
sys.exit(app.exec())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python _diag_debug_log_video.py`
Expected: `RESULT: FAIL:...` (the import of `logVideoEvents` fails since it doesn't exist yet — `<script type="module">` throws, `window.__result` stays `"PENDING"`, which fails the `PASS` check). You may instead see `RESULT: PENDING` printed if the import error prevents `__result` from ever being reassigned — either output confirms the expected pre-implementation failure.

- [ ] **Step 3: Write minimal implementation**

In `static/js/debug-log.js`, add at the end of the file:

```js
const MEDIA_ERR_NAMES = { 1: "ABORTED", 2: "NETWORK", 3: "DECODE", 4: "SRC_NOT_SUPPORTED" };

export function logVideoEvents(videoEl, label) {
  ["loadstart", "loadedmetadata", "play", "stalled"].forEach(evt => {
    videoEl.addEventListener(evt, () => {
      const extra = evt === "loadedmetadata" ? ` duration=${videoEl.duration.toFixed(2)}` : "";
      push("video", `[${label}] ${evt}${extra}`);
    });
  });
  videoEl.addEventListener("error", () => {
    const code = videoEl.error ? videoEl.error.code : "?";
    push("video", `[${label}] ERROR code=${code} (${MEDIA_ERR_NAMES[code] || "?"})`);
  });
}
```

In `static/js/pages/timeline.js`, change line 7 from:

```js
import { uiState, resetUiState } from '/static/js/session-state.js';
```

to:

```js
import { uiState, resetUiState } from '/static/js/session-state.js';
import { logVideoEvents } from '/static/js/debug-log.js';
```

Then in `showPreview()`, change:

```js
    const loadingEl = overlay.querySelector('#preview-loading');
    const playerEl  = overlay.querySelector('#preview-player');
    const errorEl   = overlay.querySelector('#preview-error');
    const statusEl  = overlay.querySelector('#preview-status');
    const video     = overlay.querySelector('#preview-video');

    function showError(msg) {
```

to:

```js
    const loadingEl = overlay.querySelector('#preview-loading');
    const playerEl  = overlay.querySelector('#preview-player');
    const errorEl   = overlay.querySelector('#preview-error');
    const statusEl  = overlay.querySelector('#preview-status');
    const video     = overlay.querySelector('#preview-video');

    logVideoEvents(video, 'preview');

    function showError(msg) {
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python _diag_debug_log_video.py`
Expected: `RESULT: PASS`

- [ ] **Step 5: Clean up diagnostic script and generated test artifacts**

```bash
rm _diag_debug_log_video.py
rm -f "$TEMP/_diag_video_src.mp4"
rm -f "C:\Users\User\.cctv_processor\previews\aaaaaaaaaaaaaaaa.webm"
```

- [ ] **Step 6: Run full backend test suite (confirm no regression)**

Run: `python -m pytest tests/ -q --tb=short`
Expected: `60 passed, 2 skipped`

- [ ] **Step 7: Commit (confirm with user first — see Global Constraints)**

```bash
git add static/js/debug-log.js static/js/pages/timeline.js
git commit -m "feat: capture video element lifecycle/errors into debug log"
```

---

### Task 4: Full end-to-end verification and cleanup

**Files:** none created or modified — this task only runs and verifies.

**Interfaces:** none new.

- [ ] **Step 1: Restart the real app**

```bash
taskkill //IM python.exe //F 2>/dev/null || true
sleep 1
(python launcher.py > /tmp/launcher_out.log 2>&1 &)
sleep 6
curl -s http://127.0.0.1:5151/api/system/stats
```
Expected: a JSON stats line, confirming the app relaunched cleanly with all three tasks' changes active.

- [ ] **Step 2: Manual walkthrough (do this yourself in the live window)**

1. Click the new "🐛 Debug" button in the nav bar on any page — confirm the drawer opens from the bottom.
2. Navigate to a different page (e.g. Home → Timeline) — confirm the drawer/toggle are still present and any earlier log entries are still in the list (persistence across navigation).
3. Load a video and open an event's Preview — confirm `video` entries appear (`loadstart`, `loadedmetadata duration=...`, `play`) and the clip actually plays (this also re-confirms the earlier VP8/Opus codec fix still works).
4. Click Copy, then paste into any text field — confirm the pasted text matches the visible log lines. If the async clipboard path is denied in this build, the `execCommand` fallback (Task 2, Step 3) should still produce a successful copy.
5. Click Clear — confirm the drawer empties and the entry count resets to `0 entries`.

- [ ] **Step 3: Confirm full backend suite one final time**

Run: `python -m pytest tests/ -q --tb=short`
Expected: `60 passed, 2 skipped`

- [ ] **Step 4: Ask the user about commits**

If Tasks 1-3's commits were deferred per the Global Constraints note, ask the user now whether to commit everything as one batch or as the three separate commits already drafted in each task, before considering the feature done.
