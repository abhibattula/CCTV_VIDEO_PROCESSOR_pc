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
