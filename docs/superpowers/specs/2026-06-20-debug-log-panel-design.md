# In-App Debug Log Panel — Design

## Background

While diagnosing a broken event-preview player (Timeline page), root cause analysis
showed PyQt6's bundled QtWebEngine (Chromium) lacks proprietary codec support:
`canPlayType()` returns `""` for H.264/AAC but `"probably"` for VP8/VP9 + Opus/Vorbis.
The preview pipeline was switched from MP4 (H.264/AAC) to WebM (VP8/Opus), verified
end-to-end via a real QtWebEngine instance (`loadedmetadata` fires, `duration` correct,
no `error` event).

That investigation needed a custom one-off diagnostic script because **the packaged
desktop app has no accessible browser DevTools** — `QWebEngineView` doesn't expose a
console or network tab to the end user. Any future client-side bug (JS error, failed
fetch, video codec/playback issue) would otherwise be invisible to the user and require
another round of guesswork or a new diagnostic script.

This spec covers a permanent, in-app debug log panel so the user can self-diagnose
client-side issues going forward without needing developer tooling.

## Goal

Add a hidden-by-default debug log panel, toggled from the nav bar, that captures
console output, fetch/network activity, uncaught JS errors, and `<video>` element
lifecycle events (load/error/play) into a single scrollable, copyable log.

## Architecture

A new module, `static/js/debug-log.js`, installs itself once when the app boots —
called from `static/js/app.js` before the router's first `navigate()`. It:

- Monkey-patches `console.log` / `console.warn` / `console.error` and `window.fetch`.
- Registers `window.onerror` and `unhandledrejection` listeners.
- Exposes `logVideoEvents(videoEl, label)` for any page to opt a `<video>` element into
  capture.
- Renders a toggle button into the nav bar and a drawer panel appended directly to
  `<body>`.

The toggle button and drawer live **outside** the router's `#app` container (the div
that `app.js` clears and replaces on every navigation). This means:
- The drawer is never destroyed/recreated by page navigation.
- The in-memory log buffer naturally persists across pages for the lifetime of the
  session, with no extra state-management code needed.

## Components

### 1. Ring buffer

```js
const MAX_ENTRIES = 500;
let buffer = [];

function push(type, text) {
  buffer.push({ ts: new Date().toISOString(), type, text });
  if (buffer.length > MAX_ENTRIES) buffer.shift();
  renderIfOpen();
}
```

Entry `type` is one of: `log`, `warn`, `error`, `fetch`, `video`. Each type maps to a
display color in the drawer (matching `base.css` tokens: `--text-dim`, `--warning`,
`--danger`, `--accent`, `--success`).

### 2. Console patch

```js
["log", "warn", "error"].forEach(level => {
  const original = console[level].bind(console);
  console[level] = (...args) => {
    original(...args);
    push(level === "log" ? "log" : level, args.map(String).join(" "));
  };
});
```

The original function is always invoked first — a bug in the logging path can never
suppress real console output.

### 3. Fetch patch

```js
const originalFetch = window.fetch.bind(window);
window.fetch = async (...args) => {
  const url = typeof args[0] === "string" ? args[0] : args[0]?.url;
  const method = (args[1]?.method || "GET").toUpperCase();
  const start = performance.now();
  push("fetch", `→ ${method} ${url}`);
  try {
    const resp = await originalFetch(...args);
    push("fetch", `← ${resp.status} ${url} (${Math.round(performance.now() - start)}ms)`);
    return resp;
  } catch (err) {
    push("fetch", `✕ ${url}: ${err.message}`);
    throw err;
  }
};
```

Arguments and return value/throw behavior are passed through unchanged — callers of
`fetch` cannot observe any difference besides the side-effect of logging.

### 4. Global error capture

```js
window.addEventListener("error", (e) => {
  push("error", `Uncaught: ${e.message} (${e.filename}:${e.lineno})`);
});
window.addEventListener("unhandledrejection", (e) => {
  push("error", `Unhandled rejection: ${e.reason}`);
});
```

### 5. Video event capture

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

`static/js/pages/timeline.js`'s `showPreview()` calls `logVideoEvents(video, "preview")`
immediately after creating the `<video>` element (before `src` is assigned), so the
full lifecycle — including the exact failure mode we just fixed — is captured for any
future regression.

### 6. UI

- Nav button: a small `🐛 Debug` link added next to the existing `.nav-link` items in
  `index.html`'s `.app-nav__links`, always visible regardless of route.
- Drawer: `position: fixed; bottom: 0; left: 0; right: 0; height: 240px;` panel,
  `display: none` until toggled, monospace font, scrollable, auto-scrolls to newest
  entry on append while open.
- Header row inside the drawer: title "Debug Log", entry count, **Copy** button
  (`navigator.clipboard.writeText` of all entries as `[ISO ts] TYPE: text` lines, one
  per line), **Clear** button (empties `buffer`), **✕** close button.
- New CSS rules added to `static/css/base.css` (`.debug-toggle`, `.debug-drawer`,
  `.debug-drawer__row--{log,warn,error,fetch,video}`), following the existing
  `--surface`/`--border`/`--text-dim` token conventions already used throughout the
  file.

## Data Flow

Console, fetch, and global-error capture are fully transparent: any code anywhere in
the app — current pages or any added later — is captured automatically with zero
per-call changes required. Video capture is the one opt-in integration point, currently
wired into the single place a `<video>` element is created (`timeline.js` preview
modal).

## Error Handling

- Every patch calls through to native behavior first, unconditionally. Formatting the
  log entry (e.g. `String(args)` on a circular object) happens in its own try/catch, so
  a malformed log line can never throw past the patch boundary or suppress the real
  `console`/`fetch` call.
- Copy-to-clipboard wrapped in try/catch; on failure (e.g. `navigator.clipboard`
  unavailable), the drawer shows an inline message: "Copy failed — select text manually."

## Testing / Verification Plan

No JS test runner exists in this project — `tests/` is pytest-only, covering the FastAPI
backend. This feature is pure frontend JS with no backend surface, so automated tests
are not applicable here. Verification will be manual, using the same direct
QtWebEngine-driven approach already used to confirm the codec fix:

1. Launch the real app (`python launcher.py`).
2. Trigger a mix of activity: navigate pages (console logs from page mounts), open a
   preview (fetch + video events), force a console.error from devtools-less context.
3. Open the debug drawer, confirm all four entry types appear, correctly color-coded,
   in chronological order, surviving a page navigation.
4. Click Copy, confirm clipboard contents match the visible log lines.
5. Confirm the existing test suite (`pytest tests/ -q`) still passes unchanged, since
   this feature touches no Python files.

## Out of Scope

- Server-side persistence of logs (Approach B, rejected — adds backend surface for a
  purely diagnostic feature; revisit only if logs need to survive an app crash).
- External Chromium DevTools via remote debugging port (Approach C, rejected — requires
  a separate browser and extra setup; doesn't match the requested in-app panel).
- Any change to the existing per-job log panel on the Processing page (`#log-panel` in
  `processing.js`) — that is a distinct, already-working feature (server-side detection
  job logs over SSE), not touched by this work.
