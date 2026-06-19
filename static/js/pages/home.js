/**
 * Home page module.
 * Handles: drop zone, Browse button, detection settings, Start button.
 * FR-017: confirmation modal when a previous completed job has uncollected events.
 */

export function mount(container, params) {
  container.innerHTML = `
    <div class="home-layout">
      <div class="left-col">
        <div class="drop-zone card" id="drop-zone">
          <div class="drop-zone__icon">&#x1F4F9;</div>
          <div class="drop-zone__text">Drop a video file here or</div>
          <button class="btn btn-primary" id="browse-btn" style="margin-top:10px">Browse…</button>
          <div class="drop-zone__file hidden" id="file-display"></div>
        </div>
        <div class="source-info hidden card" id="source-info"></div>
      </div>
      <div class="settings-panel" id="settings-panel">
        <div class="card">
          <h3>Detection Mode</h3>
          <div class="seg-group">
            <button class="seg-btn active" data-mode="mog2">MOG2 (Fast)</button>
            <button class="seg-btn" data-mode="yolo">Object Detection</button>
          </div>
        </div>
        <div class="card">
          <h3>Sensitivity</h3>
          <div class="seg-group">
            <button class="seg-btn" data-sens="low">Low</button>
            <button class="seg-btn active" data-sens="medium">Medium</button>
            <button class="seg-btn" data-sens="high">High</button>
          </div>
        </div>
        <div class="card">
          <div class="field">
            <label>Padding (s)</label>
            <div class="slider-row">
              <input type="range" id="padding-slider" min="0" max="10" step="0.5" value="2">
              <span id="padding-val">2.0s</span>
            </div>
          </div>
          <div class="field" style="margin-top:10px">
            <label>Min Event Duration (s)</label>
            <div class="slider-row">
              <input type="range" id="mindur-slider" min="0.5" max="30" step="0.5" value="2">
              <span id="mindur-val">2.0s</span>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="field">
            <label>Recording Start (HH:MM:SS) — optional</label>
            <input type="text" id="recording-start" placeholder="e.g. 08:30:00">
          </div>
        </div>
        <div class="start-btn-row">
          <button class="btn btn-primary" id="start-btn" disabled>Start Detection</button>
        </div>
      </div>
    </div>
  `;

  let selectedPath = null;
  let selectedMode = "mog2";
  let selectedSens = "medium";

  // Mode toggle
  container.querySelectorAll("[data-mode]").forEach(btn => {
    btn.addEventListener("click", () => {
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

  // Sliders
  const paddingSlider = container.querySelector("#padding-slider");
  const paddingVal    = container.querySelector("#padding-val");
  paddingSlider.addEventListener("input", () => { paddingVal.textContent = paddingSlider.value + "s"; });

  const mindurSlider = container.querySelector("#mindur-slider");
  const mindurVal    = container.querySelector("#mindur-val");
  mindurSlider.addEventListener("input", () => { mindurVal.textContent = mindurSlider.value + "s"; });

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

  // Browse button — signal to PyQt6 shell via custom event
  const browseBtn = container.querySelector("#browse-btn");
  browseBtn.addEventListener("click", () => {
    window.dispatchEvent(new CustomEvent("cctv:browse"));
    pollPendingPath();
  });

  function pollPendingPath(attempts = 0) {
    if (attempts > 60) return;  // give up after 60 * 200ms = 12s
    fetch("/api/shell/pending-path")
      .then(r => r.json())
      .then(data => {
        if (data.path) {
          loadFile(data.path);
        } else {
          setTimeout(() => pollPendingPath(attempts + 1), 200);
        }
      });
  }

  // FR-017: check if existing job needs confirmation before loading new file
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
          <button class="btn btn-danger" id="modal-continue">Continue Anyway</button>
          <button class="btn" id="modal-cancel">Cancel</button>
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
    infoEl.innerHTML = "<p class='muted'>Loading…</p>";
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

    const si = data.source_info || {};
    infoEl.innerHTML = `
      <div class="source-info">
        <div class="source-info__item"><div class="source-info__label">Codec</div><div class="source-info__value">${si.codec || "?"}</div></div>
        <div class="source-info__item"><div class="source-info__label">FPS</div><div class="source-info__value">${(si.fps || 0).toFixed(2)}</div></div>
        <div class="source-info__item"><div class="source-info__label">Resolution</div><div class="source-info__value">${si.width || "?"}×${si.height || "?"}</div></div>
        <div class="source-info__item"><div class="source-info__label">Duration</div><div class="source-info__value">${formatDur(si.duration_s)}</div></div>
        <div class="source-info__item"><div class="source-info__label">Audio</div><div class="source-info__value">${si.has_audio ? (si.audio_codec || "yes") : "none"}</div></div>
        <div class="source-info__item"><div class="source-info__label">Re-encode</div><div class="source-info__value">${si.needs_reencode ? "yes" : "no"}</div></div>
      </div>
      ${data.warnings && data.warnings.length ? `<p class="warning" style="margin-top:8px">${data.warnings[0]}</p>` : ""}
    `;
    container.querySelector("#start-btn").disabled = false;
  }

  // Start button
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
