/**
 * Export page — single-column, no right pane.
 * Phase 2: preset buttons, burn-in toggle, label scope selector.
 * FR-014: if ?quick=1 in URL, auto-start export with defaults on mount.
 * Phase 7 (T009): report format modal, 4-stage SSE progress, AI readiness badges.
 */
import { resetUiState } from "/static/js/session-state.js";

// ── Report Format Modal — module-level constants & helpers ────────────────────

const STORAGE_KEY = "intelReportFormat";

const STAGES = ["thumbnails", "ai_analysis", "markdown", "pdf"];
const STAGE_LABELS = {
  thumbnails:  "Thumbnails",
  ai_analysis: "AI Analysis",
  markdown:    "Writing Report",
  pdf:         "Generating PDF",
};

function loadFormatPrefs() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || { md: true, pdf: true };
  } catch { return { md: true, pdf: true }; }
}

function saveFormatPrefs(md, pdf) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ md, pdf }));
}

// Callback holder for the "Generate →" button — set each time the modal opens.
let _onGenerateCallback = null;

/**
 * Inject the format-chooser modal into <body> exactly once.
 * Re-entrant: safe to call on every mount().
 */
function ensureFormatModal() {
  if (document.getElementById("report-format-modal")) return;

  const wrapper = document.createElement("div");
  wrapper.innerHTML = `
<div id="report-format-modal" class="modal-overlay hidden">
  <div class="modal">
    <h3 style="margin-bottom:12px;font-size:14px">Generate Intelligence Report</h3>
    <div class="format-options" style="display:flex;flex-direction:column;gap:10px;margin-bottom:16px">
      <label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer">
        <input type="checkbox" id="fmt-md" checked> Markdown (.md)
      </label>
      <label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer">
        <input type="checkbox" id="fmt-pdf" checked> PDF
      </label>
    </div>
    <div class="actions">
      <button class="btn" id="fmt-cancel">Cancel</button>
      <button class="btn btn-primary" id="fmt-generate" disabled>Generate &#x2192;</button>
    </div>
  </div>
</div>`;
  document.body.appendChild(wrapper.firstElementChild);

  // Checkbox validation — at least one must be checked
  function _updateGenerateButton() {
    const anyChecked =
      document.getElementById("fmt-md").checked ||
      document.getElementById("fmt-pdf").checked;
    document.getElementById("fmt-generate").disabled = !anyChecked;
  }
  document.getElementById("fmt-md").addEventListener("change", _updateGenerateButton);
  document.getElementById("fmt-pdf").addEventListener("change", _updateGenerateButton);

  // Cancel button
  document.getElementById("fmt-cancel").addEventListener("click", () => {
    document.getElementById("report-format-modal").classList.add("hidden");
    // Re-enable the trigger button (caller is responsible for disabling it)
    const btn = document.querySelector("#intel-report-btn");
    if (btn) btn.disabled = false;
  });

  // Generate button
  document.getElementById("fmt-generate").addEventListener("click", () => {
    const md  = document.getElementById("fmt-md").checked;
    const pdf = document.getElementById("fmt-pdf").checked;
    saveFormatPrefs(md, pdf);
    document.getElementById("report-format-modal").classList.add("hidden");
    const formats = [];
    if (md)  formats.push("md");
    if (pdf) formats.push("pdf");
    if (_onGenerateCallback) _onGenerateCallback(formats);
  });
}

/** Open the modal, pre-filled from localStorage, and call onGenerate(formats) when confirmed. */
function openFormatModal(onGenerate) {
  _onGenerateCallback = onGenerate;
  const prefs = loadFormatPrefs();
  const fmtMd  = document.getElementById("fmt-md");
  const fmtPdf = document.getElementById("fmt-pdf");
  fmtMd.checked  = prefs.md;
  fmtPdf.checked = prefs.pdf;
  // Sync the button state with restored prefs
  document.getElementById("fmt-generate").disabled = !(prefs.md || prefs.pdf);
  document.getElementById("report-format-modal").classList.remove("hidden");
}


export function mount(container, params) {
  const quick = params && params.get("quick") === "1";

  // Inject modal once (persists across page navigations in the SPA)
  ensureFormatModal();

  container.innerHTML = `
    <div class="export-layout">

      <!-- Summary stats strip -->
      <div class="export-summary card" id="export-summary">
        <p class="muted" style="font-size:13px">Loading job summary…</p>
      </div>

      <!-- Quick presets -->
      <div class="card export-section">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <div class="section-label">Quick Presets</div>
          <button class="btn" id="save-preset-btn" style="font-size:12px;padding:6px 12px">Save as Preset</button>
        </div>
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

      <!-- Reports & Data Export -->
      <div class="card export-section">
        <div class="section-label">Reports &amp; Data Export</div>
        <div class="export-opts-row" style="display:flex;gap:10px">
          <button class="btn" id="report-pdf-btn">Generate PDF Report</button>
          <button class="btn" id="event-csv-btn">Event Log (CSV)</button>
          <button class="btn" id="event-json-btn">Event Log (JSON)</button>
        </div>
        <p class="muted" id="report-status-text" style="font-size:12px;margin-top:8px"></p>
      </div>

      <!-- Video Intelligence Report (Phase 6/7) -->
      <div class="card export-section" id="intel-report-section">
        <div class="section-label">Video Intelligence Report</div>
        <p class="muted" style="font-size:12px;margin:6px 0 10px">
          Natural language report describing what happened in the video — executive summary,
          timeline, object inventory, and PDF. Saved to your output folder.<br>
          <span style="margin-top:4px;display:inline-block">Tip: install <code>transformers</code> (<code>pip install transformers accelerate</code>) to add AI visual descriptions to the timeline. First use downloads the model (~900 MB, one-time, fully offline).</span>
        </p>

        <!-- AI readiness badges — populated by loadAiBadges() -->
        <div id="ai-badges" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px"></div>

        <button class="btn" id="intel-report-btn">Generate Intelligence Report&#x2026;</button>
        <p class="muted" id="intel-report-status" style="font-size:12px;margin-top:8px"></p>

        <!-- 4-stage SSE progress (hidden until generation starts) -->
        <div id="intel-report-progress" class="hidden" style="margin-top:12px">
          <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--text-dim);margin-bottom:8px">Generation Progress</div>
          <div id="stage-row-thumbnails"  class="stage-row"><span class="stage-row__icon" id="stage-icon-thumbnails">&#x23F3;</span><span class="stage-row__label">Thumbnails</span><span class="stage-row__progress" id="stage-prog-thumbnails"></span></div>
          <div id="stage-row-ai_analysis" class="stage-row"><span class="stage-row__icon" id="stage-icon-ai_analysis">&#x23F3;</span><span class="stage-row__label">AI Analysis</span><span class="stage-row__progress" id="stage-prog-ai_analysis"></span></div>
          <div id="stage-row-markdown"    class="stage-row"><span class="stage-row__icon" id="stage-icon-markdown">&#x23F3;</span><span class="stage-row__label">Writing Report</span><span class="stage-row__progress" id="stage-prog-markdown"></span></div>
          <div id="stage-row-pdf"         class="stage-row"><span class="stage-row__icon" id="stage-icon-pdf">&#x23F3;</span><span class="stage-row__label">Generating PDF</span><span class="stage-row__progress" id="stage-prog-pdf"></span></div>
        </div>

        <!-- Success card (hidden until report_done SSE event) -->
        <div id="intel-report-done" class="hidden" style="margin-top:12px;padding:12px 16px;border:1px solid var(--success);border-radius:var(--radius);background:rgba(62,207,142,0.07)">
          <div style="font-weight:600;color:var(--success);margin-bottom:6px">&#x2705; Report Generated</div>
          <p id="intel-report-done-md"     class="muted" style="font-size:12px;margin:2px 0;word-break:break-all"></p>
          <p id="intel-report-done-pdf"    class="muted" style="font-size:12px;margin:2px 0;word-break:break-all"></p>
          <p id="intel-report-done-notice" class="muted" style="font-size:11px;font-style:italic;margin:6px 0 0"></p>
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
          <button class="btn" id="new-job-btn">New Job</button>
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

  // ── Load Custom Presets (T005) ──────────────────────────────────────────────

  async function loadCustomPresets() {
    try {
      const customPresets = await fetch("/api/presets").then(r => r.json());
      const presetRow = container.querySelector(".preset-row");

      // Remove any existing custom preset buttons AND their wrapper divs (but
      // keep the 3 built-in ones) — removing only the inner button would leave
      // an empty, ownerless wrapper <div> behind on every re-render.
      const customBtns = presetRow.querySelectorAll(".preset-btn[data-custom]");
      customBtns.forEach(btn => btn.closest("div")?.remove());

      // Add a custom preset button for each returned preset
      customPresets.forEach(preset => {
        const btn = document.createElement("button");
        btn.className = "btn preset-btn";
        btn.dataset.preset = preset.name;
        btn.dataset.custom = "true";
        btn.textContent = preset.name;

        // Create a wrapper div to hold the button and delete control
        const wrapper = document.createElement("div");
        wrapper.style.position = "relative";
        wrapper.style.display = "inline-block";

        btn.addEventListener("click", async () => {
          container.querySelectorAll(".preset-btn").forEach(b => b.classList.remove("active"));
          btn.classList.add("active");

          // Apply the preset settings
          setType(preset.output_type || "merged");
          setQuality(preset.quality || "original");
          burnIn = preset.burn_in || false;
          labelFilter = preset.label_filter || [];

          // Update the DOM elements. #label-scope is a single-value <select>
          // by design (this page's UI can only ever produce a 1-label
          // filter), so only the first label is shown here even though
          // `labelFilter` itself (used by the actual export request) keeps
          // the full array from the preset.
          container.querySelector("#burn-in-check").checked = burnIn;
          container.querySelector("#label-scope").value = labelFilter.length > 0 ? labelFilter[0] : "";
        });

        wrapper.appendChild(btn);

        // T007: Add delete control for custom presets
        const deleteBtn = document.createElement("button");
        deleteBtn.className = "btn";
        deleteBtn.style.position = "absolute";
        deleteBtn.style.top = "-8px";
        deleteBtn.style.right = "-8px";
        deleteBtn.style.width = "24px";
        deleteBtn.style.height = "24px";
        deleteBtn.style.padding = "0";
        deleteBtn.style.display = "flex";
        deleteBtn.style.alignItems = "center";
        deleteBtn.style.justifyContent = "center";
        deleteBtn.style.fontSize = "16px";
        deleteBtn.style.backgroundColor = "var(--danger)";
        deleteBtn.style.color = "white";
        deleteBtn.style.border = "none";
        deleteBtn.style.borderRadius = "50%";
        deleteBtn.style.cursor = "pointer";
        deleteBtn.textContent = "×";
        deleteBtn.title = "Delete this preset";

        deleteBtn.addEventListener("click", async (e) => {
          e.stopPropagation();
          try {
            const resp = await fetch(`/api/presets/${encodeURIComponent(preset.name)}`, {
              method: "DELETE",
            });
            if (resp.ok) {
              await loadCustomPresets();
            } else {
              const err = await resp.json();
              alert(err.detail || "Failed to delete preset");
            }
          } catch (err) {
            alert("Error deleting preset: " + err.message);
          }
        });

        wrapper.appendChild(deleteBtn);
        presetRow.appendChild(wrapper);
      });
    } catch (err) {
      console.error("Error loading custom presets:", err);
    }
  }

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

    // MOG2 mode (no zone_label on any event) — Security Report needs a
    // label to filter on, so disable it instead of letting it fail export
    // with "No events match the label filter."
    if (labels.length === 0) {
      const securityBtn = container.querySelector('[data-preset="security"]');
      securityBtn.disabled = true;
      securityBtn.title = "Requires Object Detection mode";
      securityBtn.style.opacity = "0.45";
      securityBtn.style.cursor = "not-allowed";
    }

    // AI readiness badges — read florence_available / llm_available from
    // /api/job/status (Phase 7 addition). Gracefully degrade if endpoint is
    // unavailable or fields are absent.
    loadAiBadges();

    return job;
  }

  // ── AI Readiness Badges ──────────────────────────────────────────────────────

  async function loadAiBadges() {
    const badgeEl = container.querySelector("#ai-badges");
    if (!badgeEl) return;
    try {
      const resp = await fetch("/api/job/status");
      const status = resp.ok ? await resp.json() : {};

      let html = "";
      if (status.florence_available) {
        html += '<span class="badge badge-green">Florence-2 ready</span>';
      } else {
        html += '<span class="badge badge-grey">AI analysis unavailable</span>';
      }
      if (status.llm_available) {
        html += '<span class="badge badge-blue">LLM synthesis on</span>';
      }
      badgeEl.innerHTML = html;
    } catch (_e) {
      // Endpoint may not exist yet — show default state
      badgeEl.innerHTML = '<span class="badge badge-grey">AI analysis unavailable</span>';
    }
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
    container.querySelector("#new-job-btn").onclick = () => {
      resetUiState();
      window.go("/");
    };
  }

  container.querySelector("#export-btn").addEventListener("click", startExport);

  // ── Save as Preset (T006) ──────────────────────────────────────────────────

  container.querySelector("#save-preset-btn").addEventListener("click", async () => {
    const name = prompt("Enter a name for this preset:");
    if (name === null) return; // User cancelled

    try {
      const resp = await fetch("/api/presets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name,
          output_type: selectedType,
          quality: selectedQuality,
          burn_in: burnIn,
          label_filter: labelFilter,
        }),
      });

      if (!resp.ok) {
        const err = await resp.json();
        alert(err.detail || "Failed to save preset");
      } else {
        // Reload custom presets to show the new one
        await loadCustomPresets();
      }
    } catch (err) {
      alert("Error saving preset: " + err.message);
    }
  });

  // ── Reports & Data Export (T012) ────────────────────────────────────────────

  container.querySelector("#report-pdf-btn").addEventListener("click", () => {
    const btn = container.querySelector("#report-pdf-btn");
    const status = container.querySelector("#report-status-text");
    btn.disabled = true;
    status.textContent = "Generating PDF report…";
    window.dispatchEvent(new CustomEvent("cctv:save-report-pdf"));
    setTimeout(() => {
      status.textContent = "Report saved to your output folder.";
      btn.disabled = false;
    }, 3000);
  });

  // ── Event Log Export (T025) ─────────────────────────────────────────────────

  async function downloadEventLog(fmt) {
    const btn = container.querySelector(fmt === "csv" ? "#event-csv-btn" : "#event-json-btn");
    const status = container.querySelector("#report-status-text");
    btn.disabled = true;
    status.textContent = `Generating ${fmt.toUpperCase()} event log…`;
    try {
      const resp = await fetch(`/api/job/export/${fmt}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ output_dir: outputDir || null, label_filter: labelFilter }),
      });
      const data = await resp.json();
      status.textContent = resp.ok ? `Saved: ${data.output_path}` : (data.detail || "Export failed");
    } catch (err) {
      status.textContent = "Export failed: " + err.message;
    } finally {
      btn.disabled = false;
    }
  }

  container.querySelector("#event-csv-btn").addEventListener("click", () => downloadEventLog("csv"));
  container.querySelector("#event-json-btn").addEventListener("click", () => downloadEventLog("json"));

  // ── Video Intelligence Report (T009) ────────────────────────────────────────

  /**
   * Reset the 4-stage progress rows back to their initial pending state.
   */
  function resetStageRows() {
    STAGES.forEach(stage => {
      const icon = container.querySelector(`#stage-icon-${stage}`);
      const prog = container.querySelector(`#stage-prog-${stage}`);
      if (icon) icon.textContent = "⏳"; // ⏳
      if (prog) prog.textContent = "";
    });
  }

  /**
   * Mark a stage row as active (Running…) or complete (✔).
   * @param {string} stage - stage key
   * @param {"active"|"done"} state
   * @param {string} [progressText] - e.g. "3/12"
   */
  function updateStageRow(stage, state, progressText = "") {
    const icon = container.querySelector(`#stage-icon-${stage}`);
    const prog = container.querySelector(`#stage-prog-${stage}`);
    if (!icon) return;
    if (state === "done") {
      icon.textContent = "✔"; // ✔
      if (prog) prog.textContent = "Done";
    } else {
      icon.textContent = "▶"; // ▶
      if (prog) prog.textContent = progressText || "Running…";
    }
  }

  /**
   * Open SSE stream and listen for report_stage / report_done events.
   * Returns an EventSource that the caller should close on error.
   * @param {function} onStage - called with (stageEvent)
   * @param {function} onDone  - called with (doneEvent)
   * @param {function} onError - called with no args
   */
  function openReportSse(onStage, onDone, onError) {
    const es = new EventSource("/api/stream");
    es.onmessage = (evt) => {
      let data;
      try { data = JSON.parse(evt.data); } catch { return; }
      if (data.type === "report_stage") {
        onStage(data);
      } else if (data.type === "report_done") {
        es.close();
        onDone(data);
      }
    };
    es.onerror = () => {
      es.close();
      onError();
    };
    return es;
  }

  /**
   * Post to intel-report/export with the chosen formats, listen to SSE for
   * stage progress, and update the UI accordingly.
   * @param {string[]} formats - e.g. ["md", "pdf"]
   */
  async function generateReport(formats) {
    const btn       = container.querySelector("#intel-report-btn");
    const statusEl  = container.querySelector("#intel-report-status");
    const progressEl = container.querySelector("#intel-report-progress");
    const doneEl    = container.querySelector("#intel-report-done");

    btn.disabled = true;
    statusEl.textContent = "";
    doneEl.classList.add("hidden");
    progressEl.classList.remove("hidden");
    resetStageRows();

    // Track which stages have been seen so we can mark earlier ones complete
    const completedStages = new Set();
    // Store llm_notice from POST response to show in done card
    let _llmNotice = "";

    // Open SSE before POSTing so we don't miss early stage events
    let sseError = false;
    const es = openReportSse(
      // onStage
      (data) => {
        const currentIdx = STAGES.indexOf(data.stage);
        // Mark all prior stages done
        for (let i = 0; i < currentIdx; i++) {
          const s = STAGES[i];
          if (!completedStages.has(s)) {
            completedStages.add(s);
            updateStageRow(s, "done");
          }
        }
        // Mark current stage active
        const prog = (data.total > 0)
          ? `${data.current}/${data.total}${data.ts ? " — " + data.ts : ""}`
          : "Running…";
        updateStageRow(data.stage, "active", prog);
      },
      // onDone
      (data) => {
        // Mark all stages done
        STAGES.forEach(s => updateStageRow(s, "done"));

        // Show success card
        progressEl.classList.add("hidden");
        doneEl.classList.remove("hidden");
        const mdPath  = data.md_path  || null;
        const pdfPath = data.pdf_path || null;
        container.querySelector("#intel-report-done-md").textContent =
          mdPath  ? "Markdown: " + mdPath  : "";
        container.querySelector("#intel-report-done-pdf").textContent =
          pdfPath ? "PDF: " + pdfPath : "";
        container.querySelector("#intel-report-done-notice").textContent =
          _llmNotice || "";

        statusEl.textContent = "";
        btn.disabled = false;
      },
      // onError
      () => {
        if (!sseError) {
          sseError = true;
          progressEl.classList.add("hidden");
          statusEl.textContent = "SSE connection lost — check server logs.";
          btn.disabled = false;
        }
      },
    );

    // POST the generate request
    try {
      const resp = await fetch("/api/job/intel-report/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ formats }),
      });
      const data = await resp.json();

      if (!resp.ok) {
        es.close();
        progressEl.classList.add("hidden");
        statusEl.textContent = data.detail || "Generation failed.";
        btn.disabled = false;
        return;
      }

      // Store LLM notice to display in done card once SSE fires report_done
      _llmNotice = data.llm_notice || "";

      // Check if florence was unavailable and append a tip
      if (!data.florence_available) {
        _llmNotice = [_llmNotice, "Run 'pip install transformers accelerate' to enable AI visual descriptions."]
          .filter(Boolean).join(" ");
      }

      // The report_done SSE event will close the ES and update the UI.
      // If it never fires (edge case), the ES self-closes after ~5s idle.

    } catch (err) {
      es.close();
      progressEl.classList.add("hidden");
      statusEl.textContent = "Error: " + err.message;
      btn.disabled = false;
    }
  }

  // "Generate Intelligence Report…" button → show format modal
  container.querySelector("#intel-report-btn").addEventListener("click", () => {
    const btn = container.querySelector("#intel-report-btn");
    btn.disabled = true;
    openFormatModal((formats) => {
      // Modal confirmed — start generation
      generateReport(formats);
    });
    // If user cancels the modal, the cancel handler re-enables btn
  });

  loadSummary().then(() => {
    loadCustomPresets();
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
