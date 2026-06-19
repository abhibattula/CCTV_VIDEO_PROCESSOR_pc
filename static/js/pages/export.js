/**
 * Export page — output type, quality, folder picker, progress, done state.
 * FR-014: if ?quick=1 in URL, auto-start export with defaults on mount.
 */

export function mount(container, params) {
  const quick = params && params.get("quick") === "1";

  container.innerHTML = `
    <div class="export-layout">
      <div class="export-left">
        <div class="card">
          <h2>Export</h2>
        </div>
        <div class="card export-section">
          <h3>Output Type</h3>
          <div class="seg-group">
            <button class="seg-btn active" data-type="merged">Merged MP4</button>
            <button class="seg-btn" data-type="individual">Individual Clips</button>
          </div>
        </div>
        <div class="card export-section">
          <h3>Quality</h3>
          <div class="seg-group">
            <button class="seg-btn active" data-quality="original">Original</button>
            <button class="seg-btn" data-quality="720p">720p</button>
            <button class="seg-btn" data-quality="480p">480p</button>
          </div>
        </div>
        <div class="card export-section">
          <h3>Output Folder</h3>
          <div class="output-folder-row">
            <input type="text" id="output-dir" placeholder="Default: Desktop" readonly>
            <button class="btn" id="browse-folder-btn">Browse…</button>
          </div>
        </div>
        <div class="card export-progress-wrap hidden" id="progress-wrap">
          <h3>Exporting…</h3>
          <div class="progress-bar"><div class="progress-bar__fill" id="export-progress-fill"></div></div>
          <p class="muted" id="export-status-text" style="margin-top:8px">Starting…</p>
        </div>
        <div class="done-state hidden" id="done-state">
          <div class="checkmark">✅</div>
          <h2>Export Complete</h2>
          <p id="done-path" class="muted"></p>
          <button class="btn btn-success" id="open-folder-btn">Open Folder</button>
          <button class="btn" onclick="window.go('/')">New Job</button>
        </div>
        <div id="export-action-row" style="margin-top:auto">
          <button class="btn btn-primary" id="export-btn" style="width:100%;justify-content:center">Export Now</button>
        </div>
      </div>
      <div class="export-summary card" id="export-summary">
        <h3 style="margin-bottom:12px">Summary</h3>
        <p class="muted">Loading…</p>
      </div>
    </div>
  `;

  let selectedType    = "merged";
  let selectedQuality = "original";
  let outputDir       = null;

  // Type toggle
  container.querySelectorAll("[data-type]").forEach(btn => {
    btn.addEventListener("click", () => {
      container.querySelectorAll("[data-type]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      selectedType = btn.dataset.type;
    });
  });

  // Quality toggle
  container.querySelectorAll("[data-quality]").forEach(btn => {
    btn.addEventListener("click", () => {
      container.querySelectorAll("[data-quality]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      selectedQuality = btn.dataset.quality;
    });
  });

  // Folder browse
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

  // Load summary
  async function loadSummary() {
    const [job, events] = await Promise.all([
      fetch("/api/job").then(r => r.json()),
      fetch("/api/job/events").then(r => r.json()),
    ]);
    const included = events.filter(e => e.included);
    const totalDur = included.reduce((s, e) => s + (e.end_s - e.start_s), 0);
    const si = job.source_info || {};
    const summary = container.querySelector("#export-summary");
    summary.innerHTML = `
      <h3 style="margin-bottom:12px">Summary</h3>
      ${row("Events", `${included.length} / ${events.length} selected`)}
      ${row("Total Duration", fmt(totalDur))}
      ${row("Codec", si.codec || "—")}
      ${row("Resolution", si.width ? `${si.width}×${si.height}` : "—")}
      ${row("Audio", si.has_audio ? (si.audio_codec || "yes") : "none")}
      ${row("Mode", si.needs_reencode ? "Re-encode" : "Stream copy")}
    `;
    return job;
  }

  function row(k, v) {
    return `<div class="summary-row"><span class="key">${k}</span><span class="value">${v}</span></div>`;
  }

  async function startExport() {
    container.querySelector("#export-action-row").classList.add("hidden");
    container.querySelector("#progress-wrap").classList.remove("hidden");

    const resp = await fetch("/api/job/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        output_type: selectedType,
        quality:     selectedQuality,
        output_dir:  outputDir || null,
      }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      alert(err.detail || "Export failed");
      container.querySelector("#export-action-row").classList.remove("hidden");
      container.querySelector("#progress-wrap").classList.add("hidden");
      return;
    }

    // Poll for completion
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
    // FR-014: auto-start if ?quick=1
    if (quick) startExport();
  });
}

function fmt(s) {
  if (s == null) return "?";
  const t = Math.round(s);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const sc = t % 60;
  return [h ? h + "h" : null, m ? m + "m" : null, sc + "s"].filter(Boolean).join(" ");
}
