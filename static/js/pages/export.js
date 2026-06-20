/**
 * Export page — single-column, no right pane.
 * Phase 2: preset buttons, burn-in toggle, label scope selector.
 * FR-014: if ?quick=1 in URL, auto-start export with defaults on mount.
 */

export function mount(container, params) {
  const quick = params && params.get("quick") === "1";

  container.innerHTML = `
    <div class="export-layout">

      <!-- Summary stats strip -->
      <div class="export-summary card" id="export-summary">
        <p class="muted" style="font-size:13px">Loading job summary…</p>
      </div>

      <!-- Quick presets -->
      <div class="card export-section">
        <div class="section-label">Quick Presets</div>
        <div class="preset-row">
          <button class="btn preset-btn" data-preset="security">Security Report</button>
          <button class="btn preset-btn" data-preset="evidence">Evidence Pack</button>
          <button class="btn preset-btn" data-preset="highlights">Quick Highlights</button>
        </div>
      </div>

      <!-- Main settings -->
      <div class="card export-section">
        <div class="export-opts-grid">
          <div class="export-opts-group">
            <div class="section-label">Output Type</div>
            <div class="seg-group">
              <button class="seg-btn active" data-type="merged">Merged MP4</button>
              <button class="seg-btn" data-type="individual">Individual Clips</button>
            </div>
          </div>
          <div class="export-opts-group">
            <div class="section-label">Quality</div>
            <div class="seg-group">
              <button class="seg-btn active" data-quality="original">Original</button>
              <button class="seg-btn" data-quality="720p">720p</button>
              <button class="seg-btn" data-quality="480p">480p</button>
            </div>
          </div>
        </div>

        <div class="export-opts-row" style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border)">
          <label class="burn-in-toggle">
            <input type="checkbox" id="burn-in-check"> Burn-in timestamp &amp; label
          </label>
          <div class="field">
            <label style="display:inline;text-transform:uppercase;font-size:10px;letter-spacing:.06em;color:var(--text-dim);font-weight:600">Label Scope</label>
            <select id="label-scope" style="margin-top:4px;width:160px">
              <option value="">All labels</option>
            </select>
          </div>
        </div>

        <div class="output-folder-row" style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border)">
          <div style="flex:1">
            <div class="section-label" style="margin-bottom:6px">Output Folder</div>
            <div style="display:flex;gap:8px">
              <input type="text" id="output-dir" placeholder="Default: Desktop" readonly style="flex:1">
              <button class="btn" id="browse-folder-btn">Browse…</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Export action -->
      <div id="export-action-row">
        <button class="btn btn-primary btn-lg" id="export-btn">Export Now</button>
      </div>

      <!-- Progress -->
      <div class="card export-progress-wrap hidden" id="progress-wrap">
        <div class="section-label">Exporting…</div>
        <div class="progress-bar" style="margin:8px 0"><div class="progress-bar__fill" id="export-progress-fill"></div></div>
        <p class="muted" id="export-status-text" style="font-size:13px">Starting…</p>
      </div>

      <!-- Done -->
      <div class="done-state hidden" id="done-state">
        <div class="checkmark">&#x2705;</div>
        <h2>Export Complete</h2>
        <p id="done-path" class="done-path"></p>
        <div class="done-actions">
          <button class="btn btn-success" id="open-folder-btn">Open Folder</button>
          <button class="btn" onclick="window.go('/')">New Job</button>
        </div>
      </div>

    </div>
  `;

  let selectedType    = "merged";
  let selectedQuality = "original";
  let outputDir       = null;
  let burnIn          = false;
  let labelFilter     = [];

  // ── Toggle helpers ──────────────────────────────────────────────────────────

  function setType(t) {
    selectedType = t;
    container.querySelectorAll("[data-type]").forEach(b =>
      b.classList.toggle("active", b.dataset.type === t));
  }
  function setQuality(q) {
    selectedQuality = q;
    container.querySelectorAll("[data-quality]").forEach(b =>
      b.classList.toggle("active", b.dataset.quality === q));
  }

  container.querySelectorAll("[data-type]").forEach(btn =>
    btn.addEventListener("click", () => setType(btn.dataset.type)));
  container.querySelectorAll("[data-quality]").forEach(btn =>
    btn.addEventListener("click", () => setQuality(btn.dataset.quality)));

  // ── Options ─────────────────────────────────────────────────────────────────

  container.querySelector("#burn-in-check").addEventListener("change", e => {
    burnIn = e.target.checked;
  });
  container.querySelector("#label-scope").addEventListener("change", e => {
    labelFilter = e.target.value ? [e.target.value] : [];
  });

  // ── Presets ─────────────────────────────────────────────────────────────────

  container.querySelectorAll(".preset-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      container.querySelectorAll(".preset-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const preset = btn.dataset.preset;
      if (preset === "security") {
        setType("merged"); setQuality("original");
        burnIn = true; labelFilter = ["Person"];
        container.querySelector("#burn-in-check").checked = true;
        container.querySelector("#label-scope").value = "Person";
      } else if (preset === "evidence") {
        setType("individual"); setQuality("original");
        burnIn = false; labelFilter = [];
        container.querySelector("#burn-in-check").checked = false;
        container.querySelector("#label-scope").value = "";
      } else if (preset === "highlights") {
        setType("merged"); setQuality("720p");
        burnIn = false; labelFilter = [];
        container.querySelector("#burn-in-check").checked = false;
        container.querySelector("#label-scope").value = "";
        await applyQuickHighlights();
      }
    });
  });

  // ── Folder browse ───────────────────────────────────────────────────────────

  container.querySelector("#browse-folder-btn").addEventListener("click", () => {
    window.dispatchEvent(new CustomEvent("cctv:browse-folder"));
    pollOutputDir();
  });

  function pollOutputDir(attempts = 0) {
    if (attempts > 60) return;
    fetch("/api/shell/pending-path")
      .then(r => r.json())
      .then(data => {
        if (data.path) {
          outputDir = data.path;
          container.querySelector("#output-dir").value = data.path;
          fetch("/api/shell/set-output-dir", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ output_dir: data.path }),
          });
        } else {
          setTimeout(() => pollOutputDir(attempts + 1), 200);
        }
      });
  }

  // ── Quick Highlights preset ──────────────────────────────────────────────────

  async function applyQuickHighlights() {
    const events = await fetch("/api/job/events").then(r => r.json());
    const sorted = [...events.keys()].sort((a, b) =>
      (events[b].peak_motion_score || 0) - (events[a].peak_motion_score || 0));
    const top10 = sorted.slice(0, 10);
    const rest  = sorted.slice(10);
    if (top10.length) {
      await fetch("/api/job/events/bulk", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ indices: top10, include: true }),
      });
    }
    if (rest.length) {
      await fetch("/api/job/events/bulk", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ indices: rest, include: false }),
      });
    }
  }

  // ── Load summary ─────────────────────────────────────────────────────────────

  async function loadSummary() {
    const [job, events] = await Promise.all([
      fetch("/api/job").then(r => r.json()),
      fetch("/api/job/events").then(r => r.json()),
    ]);
    const included  = events.filter(e => e.included);
    const totalDur  = included.reduce((s, e) => s + (e.end_s - e.start_s), 0);
    const si        = job.source_info || {};

    const summaryEl = container.querySelector("#export-summary");
    const strip = [
      { value: `${included.length}`, sub: `/${events.length}`, label: "Events" },
      { value: fmt(totalDur),                                    label: "Duration" },
      { value: si.width ? `${si.width}×${si.height}` : "—",     label: "Resolution" },
      { value: si.codec || "—",                                  label: "Codec" },
      { value: si.has_audio ? (si.audio_codec || "yes") : "none", label: "Audio" },
      { value: si.needs_reencode ? "Re-encode" : "Copy",         label: "Export mode" },
    ];
    summaryEl.innerHTML = `
      <div class="stat-strip">
        ${strip.map(s => `
          <div class="stat-strip-item">
            <div class="stat-strip-item__value">${s.value}${s.sub ? `<sub>${s.sub}</sub>` : ""}</div>
            <div class="stat-strip-item__label">${s.label}</div>
          </div>`).join("")}
      </div>
    `;

    // Populate label scope dropdown
    const labels = [...new Set(events.map(e => e.zone_label).filter(Boolean))];
    const scopeEl = container.querySelector("#label-scope");
    labels.forEach(lbl => {
      const opt = document.createElement("option");
      opt.value = lbl; opt.textContent = lbl;
      scopeEl.appendChild(opt);
    });

    return job;
  }

  // ── Export ───────────────────────────────────────────────────────────────────

  async function startExport() {
    container.querySelector("#export-action-row").classList.add("hidden");
    container.querySelector("#progress-wrap").classList.remove("hidden");

    const resp = await fetch("/api/job/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        output_type:  selectedType,
        quality:      selectedQuality,
        output_dir:   outputDir || null,
        burn_in:      burnIn,
        label_filter: labelFilter,
      }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      alert(err.detail || "Export failed");
      container.querySelector("#export-action-row").classList.remove("hidden");
      container.querySelector("#progress-wrap").classList.add("hidden");
      return;
    }

    const poll = setInterval(async () => {
      const job = await fetch("/api/job").then(r => r.json());
      const pct = Math.round((job.progress || 0) * 100);
      container.querySelector("#export-progress-fill").style.width = pct + "%";
      container.querySelector("#export-status-text").textContent   = `${pct}% — ${job.status}`;
      if (job.status === "export_done") {
        clearInterval(poll);
        showDone(job.output_path);
      } else if (job.status === "export_error") {
        clearInterval(poll);
        alert("Export error: " + (job.error_msg || "unknown"));
        container.querySelector("#export-action-row").classList.remove("hidden");
        container.querySelector("#progress-wrap").classList.add("hidden");
      }
    }, 800);
  }

  function showDone(path) {
    container.querySelector("#progress-wrap").classList.add("hidden");
    const doneEl = container.querySelector("#done-state");
    doneEl.classList.remove("hidden");
    container.querySelector("#done-path").textContent = path || "";
    container.querySelector("#open-folder-btn").onclick = () => {
      fetch("/api/shell/open-folder", { method: "POST" });
    };
  }

  container.querySelector("#export-btn").addEventListener("click", startExport);

  loadSummary().then(() => {
    if (quick) startExport();
  });
}

function fmt(s) {
  if (s == null) return "—";
  const t = Math.round(s);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const sc = t % 60;
  return [h ? h + "h" : null, m ? m + "m" : null, sc + "s"].filter(Boolean).join(" ");
}
