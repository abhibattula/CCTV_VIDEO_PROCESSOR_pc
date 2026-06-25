/**
 * Stop Application — gracefully stops the backend after a confirmation
 * dialog, then polls until it's actually confirmed dead before telling the
 * user it's safe to close the window. Never claims success on a timeout —
 * only on a genuine connection failure (see pollStopped).
 */

let installed = false;

export function installStopButton() {
  if (installed) return;
  installed = true;
  const navBar = document.getElementById("app-nav");
  if (!navBar) return;
  const btn = document.createElement("button");
  btn.className = "btn btn-danger stop-app-btn";
  btn.textContent = "Stop";
  btn.title = "Stop the application backend";
  btn.addEventListener("click", showConfirm);
  navBar.appendChild(btn);
}

function showConfirm() {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML = `
    <div class="modal">
      <h2>Stop application?</h2>
      <p>Any in-progress detection or export will be abandoned. This cannot be undone.</p>
      <div class="actions">
        <button class="btn" id="stop-cancel">Cancel</button>
        <button class="btn btn-danger" id="stop-confirm">Stop</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.querySelector("#stop-cancel").onclick = () => document.body.removeChild(overlay);
  overlay.querySelector("#stop-confirm").onclick = () => {
    overlay.querySelector(".modal").innerHTML = "<h2>Stopping…</h2><p>Please wait.</p>";
    fetch("/api/job/cancel", { method: "POST" }).catch(() => {}).finally(() => {
      window._cctvShutdown = true;
      pollStopped(overlay);
    });
  };
}

const MAX_ATTEMPTS = 30; // 30 * 500ms = 15s

function pollStopped(overlay, attempts = 0) {
  fetch("/api/health")
    .then(() => {
      if (attempts >= MAX_ATTEMPTS) {
        showTimeout(overlay);
        return;
      }
      setTimeout(() => pollStopped(overlay, attempts + 1), 500);
    })
    .catch(() => showStopped(overlay)); // network-level failure = server is genuinely gone
}

function showStopped(overlay) {
  overlay.querySelector(".modal").innerHTML =
    "<h2>✅ Application stopped</h2><p>You can close this window now.</p>";
}

function showTimeout(overlay) {
  // The backend is STILL responding after 15s of polling — never claim
  // success here. This is the path taken when this window's process reused
  // an already-running backend from a prior instance: stop_backend() is a
  // safe no-op in that case, so health checks keep succeeding indefinitely.
  overlay.querySelector(".modal").innerHTML =
    "<h2>Could not confirm the application stopped</h2>" +
    "<p>The backend is still responding after waiting 15 seconds. " +
    "It may be shared with another window of this application. " +
    "Closing this window directly is safe if you no longer need it.</p>";
}
