/**
 * Processing page — live progress via SSE, Cancel button.
 * Phase 2: label bar chart + events/min counter (T036-T039).
 * Phase 7: timestamped severity-coloured log panel (T010).
 * SSE emits type:"log"/"keepalive"/"done" — no type:"event" exists.
 * Chart updates by detecting event_count delta, then fetching /api/job/events.
 */

const SEVERITY_COLOURS = {
  INFO:  "#9ca3af",  // grey
  EVENT: "#3b82f6",  // blue
  WARN:  "#f59e0b",  // amber
  ERROR: "#ef4444",  // red
};

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

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
      <div class="chart-wrap card" id="chart-wrap" style="display:none">
        <h4 style="margin-bottom:8px">Detection Activity</h4>
        <div id="label-chart"></div>
        <p class="eventsmin-counter">Events/min: <span id="evmin">—</span></p>
      </div>
      <div class="log-panel" id="log-panel" style="display:none">
        <div class="log-header">
          <span>Detection Log</span>
          <button id="log-copy-btn">Copy</button>
        </div>
        <div id="log-entries"></div>
      </div>
      <div class="processing-actions">
        <button class="btn btn-danger" id="cancel-btn">Cancel</button>
        <button class="btn" id="log-toggle-btn">Show Logs</button>
        <span class="muted" id="action-hint">Detection in progress…</span>
      </div>
    </div>
  `;

  const logPanel     = container.querySelector("#log-panel");
  const logEntries   = container.querySelector("#log-entries");
  const progressFill = container.querySelector("#progress-fill");
  let evtSource = null;
  let pollTimer = null;
  let detectionStart = Date.now();

  // ── Live chart state (T038/T039) ───────────────────────────────────────────
  let labelCounts    = {};
  let lastKnownCount = 0;
  let totalEvents    = 0;
  let chartStartTime = null;

  // ── Log panel functions (T010) ─────────────────────────────────────────────

  function toggleLogPanel() {
    const btn = container.querySelector("#log-toggle-btn");
    if (logPanel.style.display === "none") {
      logPanel.style.display = "block";
      btn.textContent = "Hide Logs";
    } else {
      logPanel.style.display = "none";
      btn.textContent = "Show Logs";
    }
  }

  function addLogEntry(severity, message) {
    const ts = new Date().toTimeString().slice(0, 8);
    const colour = SEVERITY_COLOURS[severity] || SEVERITY_COLOURS.INFO;
    const entry = document.createElement("div");
    entry.className = "log-entry";
    entry.innerHTML = `<span class="log-ts">${ts}</span> `
      + `<span class="log-sev" style="color:${colour}">[${severity}]</span> `
      + `<span class="log-msg">${escapeHtml(message)}</span>`;
    logEntries.appendChild(entry);
    logPanel.scrollTop = logPanel.scrollHeight;
  }

  function addStageSeparator(stageName) {
    const sep = document.createElement("div");
    sep.className = "log-stage-sep";
    sep.textContent = `── ${stageName} ──────────────────────────`;
    logEntries.appendChild(sep);
  }

  container.querySelector("#log-toggle-btn").addEventListener("click", toggleLogPanel);

  container.querySelector("#log-copy-btn").addEventListener("click", () => {
    const entries = container.querySelectorAll(".log-entry");
    const text = Array.from(entries).map(e => e.textContent).join("\n");
    navigator.clipboard.writeText(text);
  });

  // ── Insert initial stage separator ────────────────────────────────────────

  addStageSeparator("Starting detection");

  function updateStats(progress, eventCount, status) {
    container.querySelector("#stat-progress").textContent = Math.round(progress * 100) + "%";
    container.querySelector("#stat-status").textContent   = status;
    container.querySelector("#stat-events").textContent   = eventCount;
    progressFill.style.width = Math.round(progress * 100) + "%";

    if (progress > 0.01) {
      const elapsed = (Date.now() - detectionStart) / 1000;
      const eta = (elapsed / progress) * (1 - progress);
      container.querySelector("#stat-eta").textContent = formatEta(eta);
    }
  }

  // ── Chart rendering (T036/T038) ────────────────────────────────────────────

  function renderChart() {
    const chartEl = container.querySelector("#label-chart");
    const entries = Object.entries(labelCounts);
    if (!entries.length) return;
    const maxCount = Math.max(1, ...entries.map(([, n]) => n));
    chartEl.innerHTML = entries.map(([lbl, n]) => `
      <div class="chart-bar-row">
        <span class="chart-label">${lbl}</span>
        <div class="chart-bar" style="width:${Math.round((n / maxCount) * 200)}px"></div>
        <span style="font-size:11px;color:var(--text-dim)">${n}</span>
      </div>
    `).join('');
    container.querySelector("#chart-wrap").style.display = "";
  }

  async function onNewEvents(eventCount) {
    if (eventCount <= lastKnownCount) return;
    try {
      const events = await fetch("/api/job/events").then(r => r.json());
      labelCounts = {};
      events.forEach(e => {
        const lbl = e.zone_label || "Motion";
        labelCounts[lbl] = (labelCounts[lbl] || 0) + 1;
      });
      if (!chartStartTime) chartStartTime = Date.now();
      totalEvents    = eventCount;
      lastKnownCount = eventCount;
      renderChart();
    } catch { /* ignore fetch errors during detection */ }
  }

  function onDone(status) {
    if (evtSource) { evtSource.close(); evtSource = null; }
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    container.querySelector("#action-hint").textContent = "Complete!";
    container.querySelector("#cancel-btn").disabled = true;
    addLogEntry(status === "error" ? "ERROR" : "INFO", `[${status.toUpperCase()}] Navigation to timeline…`);
    setTimeout(() => window.go("/timeline"), 1200);
  }

  // ── SSE stream (T038) ──────────────────────────────────────────────────────

  try {
    evtSource = new EventSource("/api/stream");
    evtSource.onmessage = async (e) => {
      const msg = JSON.parse(e.data);

      // event_count delta detection — fetch events when count grows
      if (typeof msg.event_count === "number") {
        await onNewEvents(msg.event_count);
      }

      if (msg.type === "keepalive") {
        updateStats(msg.progress || 0, msg.event_count || 0, msg.status || "—");
        return;
      }
      if (msg.line) {
        const sev = msg.status === "error" ? "ERROR" : "INFO";
        addLogEntry(sev, msg.line);
      }
      updateStats(msg.progress || 0, msg.event_count || 0, msg.status || "—");
      if (msg.type === "done" || msg.status === "completed" || msg.status === "cancelled") {
        onDone(msg.status || "done");
      }
    };
    evtSource.onerror = () => {
      if (evtSource) { evtSource.close(); evtSource = null; }
      addLogEntry("WARN", "SSE connection lost — switching to polling");
      startPolling();
    };
  } catch {
    startPolling();
  }

  function startPolling() {
    pollTimer = setInterval(async () => {
      const job = await fetch("/api/job").then(r => r.json());
      if (typeof job.event_count === "number") await onNewEvents(job.event_count);
      updateStats(job.progress || 0, job.event_count || 0, job.status);
      if (job.status === "completed" || job.status === "cancelled" || job.status === "error") {
        onDone(job.status);
      }
    }, 2000);
  }

  // ── Events/min counter (T039) — sampled every 10s ─────────────────────────

  const evminTimer = setInterval(() => {
    if (!chartStartTime) return;
    const elapsed = (Date.now() - chartStartTime) / 60000;
    const evminEl = container.querySelector("#evmin");
    if (evminEl) evminEl.textContent = elapsed > 0 ? (totalEvents / elapsed).toFixed(1) : "—";
  }, 10000);

  // ── System stats polling ───────────────────────────────────────────────────

  const sysTimer = setInterval(async () => {
    try {
      const stats = await fetch("/api/system/stats").then(r => r.json());
      const cpuEl = container.querySelector("#stat-cpu");
      if (cpuEl) cpuEl.textContent = Math.round(stats.cpu_pct) + "%";
    } catch { /* ignore */ }
  }, 3000);

  // ── Cancel ─────────────────────────────────────────────────────────────────

  container.querySelector("#cancel-btn").addEventListener("click", async () => {
    await fetch("/api/job/cancel", { method: "POST" });
    container.querySelector("#action-hint").textContent = "Cancelling…";
    addLogEntry("WARN", "Cancellation requested");
  });

  // ── Cleanup on page nav away ───────────────────────────────────────────────

  container._cleanup = () => {
    if (evtSource)  { evtSource.close(); }
    if (pollTimer)  { clearInterval(pollTimer); }
    clearInterval(sysTimer);
    clearInterval(evminTimer);
  };
}

function formatEta(seconds) {
  if (seconds < 60)   return Math.round(seconds) + "s";
  if (seconds < 3600) return Math.round(seconds / 60) + "m";
  return Math.round(seconds / 3600) + "h";
}
