/**
 * Processing page — live progress via SSE, Cancel button.
 */

export function mount(container) {
  container.innerHTML = `
    <div class="processing-layout">
      <div class="stats-row">
        <div class="stat-card"><div class="stat-card__label">Progress</div><div class="stat-card__value" id="stat-progress">0%</div></div>
        <div class="stat-card"><div class="stat-card__label">Status</div><div class="stat-card__value" id="stat-status">—</div></div>
        <div class="stat-card"><div class="stat-card__label">Events Found</div><div class="stat-card__value" id="stat-events">0</div></div>
        <div class="stat-card"><div class="stat-card__label">ETA</div><div class="stat-card__value" id="stat-eta">—</div></div>
        <div class="stat-card"><div class="stat-card__label">CPU</div><div class="stat-card__value" id="stat-cpu">—</div></div>
      </div>
      <div class="progress-section card">
        <h3>Detection Progress</h3>
        <div class="progress-bar"><div class="progress-bar__fill" id="progress-fill"></div></div>
      </div>
      <div class="log-panel" id="log-panel"></div>
      <div class="processing-actions">
        <button class="btn btn-danger" id="cancel-btn">Cancel</button>
        <span class="muted" id="action-hint">Detection in progress…</span>
      </div>
    </div>
  `;

  const logPanel    = container.querySelector("#log-panel");
  const progressFill = container.querySelector("#progress-fill");
  let evtSource = null;
  let pollTimer = null;
  let detectionStart = Date.now();

  function updateStats(progress, eventCount, status) {
    container.querySelector("#stat-progress").textContent = Math.round(progress * 100) + "%";
    container.querySelector("#stat-status").textContent   = status;
    container.querySelector("#stat-events").textContent   = eventCount;
    progressFill.style.width = Math.round(progress * 100) + "%";

    // Rough ETA based on elapsed time and progress
    if (progress > 0.01) {
      const elapsed = (Date.now() - detectionStart) / 1000;
      const eta = (elapsed / progress) * (1 - progress);
      container.querySelector("#stat-eta").textContent = formatEta(eta);
    }
  }

  function appendLog(line, cls = "") {
    const div = document.createElement("div");
    div.className = "log-line" + (cls ? " " + cls : "");
    div.textContent = line;
    logPanel.appendChild(div);
    logPanel.scrollTop = logPanel.scrollHeight;
  }

  function onDone(status) {
    if (evtSource) { evtSource.close(); evtSource = null; }
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    container.querySelector("#action-hint").textContent = "Complete!";
    container.querySelector("#cancel-btn").disabled = true;
    appendLog(`[${status.toUpperCase()}] Navigation to timeline…`, "done");
    setTimeout(() => window.go("/timeline"), 1200);
  }

  // Open SSE stream
  try {
    evtSource = new EventSource("/api/stream");
    evtSource.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === "keepalive") {
        updateStats(msg.progress || 0, msg.event_count || 0, msg.status || "—");
        return;
      }
      if (msg.line) appendLog(msg.line, msg.status === "error" ? "error" : "");
      updateStats(msg.progress || 0, msg.event_count || 0, msg.status || "—");
      if (msg.type === "done" || msg.status === "completed" || msg.status === "cancelled") {
        onDone(msg.status || "done");
      }
    };
    evtSource.onerror = () => {
      // SSE failed — fall back to polling
      if (evtSource) { evtSource.close(); evtSource = null; }
      startPolling();
    };
  } catch {
    startPolling();
  }

  function startPolling() {
    pollTimer = setInterval(async () => {
      const job = await fetch("/api/job").then(r => r.json());
      updateStats(job.progress || 0, job.event_count || 0, job.status);
      if (job.status === "completed" || job.status === "cancelled" || job.status === "error") {
        onDone(job.status);
      }
    }, 2000);
  }

  // Poll system stats every 3s (T073)
  const sysTimer = setInterval(async () => {
    try {
      const stats = await fetch("/api/system/stats").then(r => r.json());
      const cpuEl = container.querySelector("#stat-cpu");
      if (cpuEl) cpuEl.textContent = Math.round(stats.cpu_pct) + "%";
    } catch { /* ignore */ }
  }, 3000);

  // Cancel
  container.querySelector("#cancel-btn").addEventListener("click", async () => {
    await fetch("/api/job/cancel", { method: "POST" });
    container.querySelector("#action-hint").textContent = "Cancelling…";
  });

  // Cleanup on page nav away
  container._cleanup = () => {
    if (evtSource) { evtSource.close(); }
    if (pollTimer) { clearInterval(pollTimer); }
    clearInterval(sysTimer);
  };
}

function formatEta(seconds) {
  if (seconds < 60)  return Math.round(seconds) + "s";
  if (seconds < 3600) return Math.round(seconds / 60) + "m";
  return Math.round(seconds / 3600) + "h";
}
