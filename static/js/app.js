/**
 * Client-side SPA router.
 * Pages register themselves via window._cctvPages[path] = { mount(container) }.
 * navigate(path) loads the page module if needed, then calls mount().
 */
import { installDebugLog } from "/static/js/debug-log.js";
import { installTheme } from "/static/js/theme.js";
import { installStopButton } from "/static/js/stop-app.js";
installDebugLog();
installTheme();
installStopButton();

const routes = {
  "/":           "/static/js/pages/home.js",
  "/processing": "/static/js/pages/processing.js",
  "/timeline":   "/static/js/pages/timeline.js",
  "/export":     "/static/js/pages/export.js",
};

window._cctvPages = window._cctvPages || {};

const container = document.getElementById("app");

function _updateNav(path) {
  document.querySelectorAll(".nav-link").forEach(a => {
    a.classList.toggle("active", a.dataset.route === path);
  });
  // Show processing nav link only while on that page
  const procLink = document.getElementById("nav-processing");
  if (procLink) procLink.style.display = path === "/processing" ? "" : "none";
}

async function navigate(path) {
  const normalised = path.split("?")[0] || "/";
  _updateNav(normalised);

  const modulePath = routes[normalised];
  if (!modulePath) {
    container.innerHTML = `<div style="padding:2rem"><h2>404</h2><p>Page not found: ${path}</p></div>`;
    return;
  }

  // Clean up previous page (remove event listeners etc.)
  if (typeof container._cleanup === "function") {
    container._cleanup();
    container._cleanup = null;
  }

  if (!window._cctvPages[normalised]) {
    try {
      const mod = await import(modulePath);
      window._cctvPages[normalised] = mod;
    } catch (err) {
      container.innerHTML = `<div style="padding:2rem"><h2>Load error</h2><pre>${err}</pre></div>`;
      return;
    }
  }
  container.innerHTML = "";
  window._cctvPages[normalised].mount(container, new URLSearchParams(location.search));
}

export function go(path) {
  history.pushState(null, "", path);
  navigate(path);
}

window.go = go;

window.addEventListener("popstate", () => navigate(location.pathname + location.search));

document.addEventListener("DOMContentLoaded", () => {
  navigate(location.pathname + location.search);
});
