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

let installed = false;

export function installDebugLog() {
  if (installed) return;
  installed = true;
  installConsolePatch();
  installFetchPatch();
  installGlobalErrorCapture();
  buildUI();
}
