/**
 * Home page — single-column layout, no right pane.
 * FR-017: confirmation modal when a previous completed job has uncollected events.
 */

import { resetUiState } from "/static/js/session-state.js";

export function mount(container, params) {
  container.innerHTML = `
    <div class="home-layout">

      <!-- Drop zone -->
      <div class="drop-zone card" id="drop-zone">
        <div class="drop-zone__icon">&#x1F4F9;</div>
        <div class="drop-zone__text">Drop a video file here or browse to select one</div>
        <button class="btn btn-primary" id="browse-btn">Browse…</button>
        <div class="drop-zone__file hidden" id="file-display"></div>
      </div>

      <!-- Source info bar (shown after file loads) -->
      <div class="source-bar card hidden" id="source-info"></div>

      <!-- Detection settings -->
      <div class="settings-card card">

        <div class="settings-row">
          <div class="settings-group">
            <div class="settings-group__label">Detection Mode</div>
            <div class="seg-group">
              <button class="seg-btn active" data-mode="mog2">MOG2 (Fast)</button>
              <button class="seg-btn" data-mode="yolo">Object Detection</button>
            </div>
          </div>
          <div class="settings-group">
            <div class="settings-group__label">Sensitivity</div>
            <div class="seg-group">
              <button class="seg-btn" data-sens="low">Low</button>
              <button class="seg-btn active" data-sens="medium">Medium</button>
              <button class="seg-btn" data-sens="high">High</button>
            </div>
          </div>
          <div class="settings-group">
            <div class="settings-group__label">Recording Start <span style="text-transform:none;letter-spacing:0;font-weight:400">(optional)</span></div>
            <input type="text" id="recording-start" placeholder="HH:MM:SS" class="recording-start-input">
          </div>
        </div>

        <div class="settings-divider"></div>

        <div class="settings-row">
          <div class="settings-group" style="flex:1;min-width:200px">
            <div class="settings-group__label">Padding — <span id="padding-val" style="color:var(--accent);font-weight:700">2.0s</span></div>
            <div class="slider-row">
              <input type="range" id="padding-slider" min="0" max="10" step="0.5" value="2">
              <span class="slider-val" id="padding-val-display">2.0s</span>
            </div>
          </div>
          <div class="settings-group" style="flex:1;min-width:200px">
            <div class="settings-group__label">Min Event Duration — <span id="mindur-val" style="color:var(--accent);font-weight:700">2.0s</span></div>
            <div class="slider-row">
              <input type="range" id="mindur-slider" min="0.5" max="30" step="0.5" value="2">
              <span class="slider-val" id="mindur-val-display">2.0s</span>
            </div>
          </div>
        </div>

      </div>

      <!-- Start button -->
      <button class="btn btn-primary btn-lg" id="start-btn" disabled>Start Detection</button>

    </div>
  `;

  let selectedPath = null;
  let selectedMode = "mog2";
  let selectedSens = "medium";

  // Check if YOLO is available and disable button if not
  fetch("/api/system/capabilities").then(r => r.json()).then(caps => {
    if (!caps.yolo_available) {
      const yoloBtn = container.querySelector("[data-mode='yolo']");
      if (yoloBtn) {
        yoloBtn.disabled = true;
        yoloBtn.title = "Requires: pip install ultralytics";
        yoloBtn.style.opacity = "0.45";
        yoloBtn.style.cursor = "not-allowed";
        yoloBtn.textContent = "Object Detection (not installed)";
      }
    }
  }).catch(() => {});

  // Mode toggle
  container.querySelectorAll("[data-mode]").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      container.querySelectorAll("[data-mode]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      selectedMode = btn.dataset.mode;
    });
  });

  // Sensitivity toggle
  container.querySelectorAll("[data-sens]").forEach(btn => {
    btn.addEventListener("click", () => {
      container.querySelectorAll("[data-sens]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      selectedSens = btn.dataset.sens;
    });
  });

  // Sliders — dual display (label + side badge)
  const paddingSlider = container.querySelector("#padding-slider");
  const mindurSlider  = container.querySelector("#mindur-slider");

  function syncSlider(slider, labelId, displayId) {
    const v = parseFloat(slider.value).toFixed(1) + "s";
    container.querySelector(labelId).textContent  = v;
    container.querySelector(displayId).textContent = v;
  }

  paddingSlider.addEventListener("input", () => syncSlider(paddingSlider, "#padding-val", "#padding-val-display"));
  mindurSlider.addEventListener("input",  () => syncSlider(mindurSlider,  "#mindur-val",  "#mindur-val-display"));

  // Drop zone
  const dropZone = container.querySelector("#drop-zone");
  dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("drag-over"); });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
  dropZone.addEventListener("drop", e => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    const files = e.dataTransfer.files;
    if (files.length > 0) loadFile(files[0].path || files[0].name);
  });

  // Browse button
  container.querySelector("#browse-btn").addEventListener("click", () => {
    window.dispatchEvent(new CustomEvent("cctv:browse"));
    pollPendingPath();
  });

  function pollPendingPath(attempts = 0) {
    if (attempts > 60) return;
    fetch("/api/shell/pending-path")
      .then(r => r.json())
      .then(data => {
        if (data.path) loadFile(data.path);
        else setTimeout(() => pollPendingPath(attempts + 1), 200);
      });
  }

  // FR-017: check existing job before loading new file
  async function loadFile(path) {
    const job = await fetch("/api/job").then(r => r.json());
    if (job.status === "completed" && !job.output_path && job.events && job.events.length > 0) {
      showDiscardModal(path, job);
      return;
    }
    doLoadFile(path);
  }

  function showDiscardModal(path, job) {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal">
        <h2>Discard existing job?</h2>
        <p>You have ${job.events.length} event(s) from <strong>${job.source_path ? job.source_path.split(/[\\/]/).pop() : "previous file"}</strong>.
        Starting a new job will discard them.</p>
        <div class="actions">
          <button class="btn btn-primary" id="modal-export">Export First</button>
          <button class="btn btn-danger"  id="modal-continue">Continue Anyway</button>
          <button class="btn"             id="modal-cancel">Cancel</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector("#modal-export").onclick   = () => { document.body.removeChild(overlay); window.go("/export"); };
    overlay.querySelector("#modal-continue").onclick = () => { document.body.removeChild(overlay); doLoadFile(path); };
    overlay.querySelector("#modal-cancel").onclick   = () => document.body.removeChild(overlay);
  }

  async function doLoadFile(path) {
    selectedPath = path;
    const display = container.querySelector("#file-display");
    display.textContent = path.split(/[\\/]/).pop();
    display.classList.remove("hidden");

    const infoEl = container.querySelector("#source-info");
    infoEl.innerHTML = "<p class='muted' style='padding:4px 0'>Analysing file…</p>";
    infoEl.classList.remove("hidden");

    const resp = await fetch("/api/job/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_path: path }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      infoEl.innerHTML = `<p class="danger">${data.detail || "Failed to load file"}</p>`;
      container.querySelector("#start-btn").disabled = true;
      return;
    }
    resetUiState();

    const si = data.source_info || {};
    const stats = [
      { label: "Codec",      value: si.codec || "?" },
      { label: "Resolution", value: si.width ? `${si.width}×${si.height}` : "?" },
      { label: "FPS",        value: si.fps ? si.fps.toFixed(2) : "?" },
      { label: "Duration",   value: formatDur(si.duration_s) },
      { label: "Audio",      value: si.has_audio ? (si.audio_codec || "yes") : "none" },
      { label: "Export",     value: si.needs_reencode ? "Re-encode" : "Stream copy" },
    ];
    infoEl.innerHTML = `
      <div class="source-bar-inner">
        ${stats.map(s => `
          <div class="source-stat">
            <div class="source-stat__label">${s.label}</div>
            <div class="source-stat__value">${s.value}</div>
          </div>`).join('')}
      </div>
      ${data.warnings && data.warnings.length
        ? `<div class="source-warning">&#9888; ${data.warnings[0]}</div>`
        : ""}
    `;
    container.querySelector("#start-btn").disabled = false;
  }

  // Start detection
  container.querySelector("#start-btn").addEventListener("click", async () => {
    const recStart = container.querySelector("#recording-start").value.trim() || null;
    const body = {
      mode:            selectedMode,
      sensitivity:     selectedSens,
      frame_skip:      1,
      padding_s:       parseFloat(paddingSlider.value),
      min_gap_s:       parseFloat(paddingSlider.value),
      min_event_s:     parseFloat(mindurSlider.value),
      zones:           [],
      recording_start: recStart,
    };
    const resp = await fetch("/api/job/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (resp.ok) {
      // Show processing link in nav while detecting
      const navProc = document.getElementById("nav-processing");
      if (navProc) navProc.style.display = "";
      window.go("/processing");
    } else {
      const err = await resp.json();
      alert(err.detail || "Failed to start detection");
    }
  });
}

function formatDur(s) {
  if (!s) return "?";
  const t = Math.round(s);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const sc = t % 60;
  return `${h ? h + "h " : ""}${m ? m + "m " : ""}${sc}s`;
}
