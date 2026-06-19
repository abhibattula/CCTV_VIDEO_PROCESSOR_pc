# Shell Bridge Contract

**Date**: 2026-06-19

Defines the communication protocol between the web UI (JavaScript running in
QWebEngineView) and the PyQt6 shell (Python). The bridge is one-directional for
triggers (JS → Python) and uses HTTP polling for responses (JS polls `/api/shell/*`).

---

## JS → Shell Events (CustomEvent)

The web UI fires `window.dispatchEvent(new CustomEvent(...))` to request native OS
actions. The PyQt6 shell polls for these flags via `QWebEnginePage.runJavaScript()`.

### `cctv:browse`
**Trigger**: User clicks "Browse File…" on the Home page.
**Shell action**: Opens `QFileDialog.getOpenFileName()` with video format filter.
**Response path**: Shell POSTs result to `POST /api/shell/filepath`.
**Web UI polls**: `GET /api/shell/pending-path` every 300ms until path arrives or
30s timeout.

**JS dispatch**:
```javascript
window.dispatchEvent(new CustomEvent('cctv:browse'));
```

**Shell detection** (polled at 200ms interval via QTimer):
```javascript
// Injected by shell on page load:
window.addEventListener('cctv:browse', function() {
    window._cctvBrowse = true;
});
// Shell reads: window._cctvBrowse, resets to false after handling
```

---

### `cctv:browse-folder`
**Trigger**: User clicks "Browse…" next to the output folder field on the Export page.
**Shell action**: Opens `QFileDialog.getExistingDirectory()`.
**Response path**: Shell POSTs result to `POST /api/shell/filepath`.
**Web UI polls**: `GET /api/shell/pending-path`.

---

## Shell → Web Signals

The shell has no direct JS injection channel beyond page-load injection. All shell
state is communicated via the REST API. The shell does not call `runJavaScript()` to
push data — the web UI polls.

---

## Native Drag-and-Drop

**Trigger**: User drags a video file from OS file manager and drops on the app window.
**Shell action**: `QMainWindow.dropEvent()` intercepts the drop, extracts the file
path, and calls `POST /api/job/create` directly (bypassing the web UI browse flow).
**Shell then**: Navigates the QWebEngineView to `/processing` after starting detection.

**File types accepted** (enforced at OS level by `dragEnterEvent`):
- `.mp4`, `.mkv`, `.avi`, `.mov`, `.ts`, `.mts`, `.flv`, `.m4v`
- Any file with a MIME type starting with `video/`

---

## Browse Flag Lifecycle

```
Web UI fires cctv:browse
    │
    ▼
window._cctvBrowse = true
    │
QTimer polls runJavaScript("[window._cctvBrowse, window._cctvBrowseFolder]")
    │
Shell reads true → opens QFileDialog
    │
runJavaScript("window._cctvBrowse = false;")   ← reset immediately
    │
QFileDialog returns path
    │
POST /api/shell/filepath { "path": "..." }
    │
Web UI polls GET /api/shell/pending-path
    │
{ "path": "..." } returned → path consumed and cleared
    │
Web UI calls POST /api/job/create with the path
```

---

## Confirmation Dialog (FR-017)

When the web UI needs to ask "Discard existing session?" before loading a new file,
it renders an in-page modal overlay rather than using a native dialog. This keeps the
flow entirely within the web UI and avoids the complexity of a bidirectional shell
bridge call.

The modal offers:
- **Export first** → `window.go('/export')`
- **Continue (discard)** → proceed with `POST /api/job/create`
