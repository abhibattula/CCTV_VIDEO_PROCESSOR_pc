/**
 * New Project — reachable from every page via the nav bar. Warns before
 * discarding an actively-running job or unexported completed results;
 * otherwise returns to the upload screen immediately with no warning.
 */
import { resetUiState, markJustReset } from "/static/js/session-state.js";

let installed = false;

export function installNewProjectButton() {
  if (installed) return;
  installed = true;
  const navBar = document.getElementById("app-nav");
  if (!navBar) return;
  const btn = document.createElement("button");
  btn.className = "btn new-project-btn";
  btn.textContent = "New Project";
  btn.addEventListener("click", onClick);
  navBar.appendChild(btn);
}

async function onClick() {
  const job = await fetch("/api/job").then(r => r.json());
  if (job.status === "detecting" || job.status === "exporting") {
    showModal(
      "Cancel in-progress work?",
      `A ${job.status === "detecting" ? "detection" : "export"} is currently running. Starting a new project will cancel it.`,
      proceed
    );
  } else if ((job.status === "completed" || job.status === "export_error")
      && job.events && job.events.length > 0 && !job.output_path) {
    showModal(
      "Discard uncollected events?",
      `You have ${job.events.length} event(s) that have not been exported. Starting a new project will discard them.`,
      proceed
    );
  } else {
    proceed();
  }
}

async function proceed() {
  await fetch("/api/job/cancel", { method: "POST" }).catch(() => {});
  resetUiState();
  // The backend has no "fully clear to idle" endpoint without a new
  // source_path — /api/job/cancel just flips status to "cancelled" and
  // leaves the stale job_id/source_path in place. Tell Home's mount-time
  // restore check to ignore that stale job rather than resurrecting it.
  markJustReset();
  window.go("/");
}

function showModal(title, body, onConfirm) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.innerHTML = `
    <div class="modal">
      <h2>${title}</h2><p>${body}</p>
      <div class="actions">
        <button class="btn" id="np-cancel">Cancel</button>
        <button class="btn btn-danger" id="np-confirm">Continue</button>
      </div>
    </div>`;
  document.body.appendChild(overlay);
  overlay.querySelector("#np-cancel").onclick = () => document.body.removeChild(overlay);
  overlay.querySelector("#np-confirm").onclick = () => { document.body.removeChild(overlay); onConfirm(); };
}
