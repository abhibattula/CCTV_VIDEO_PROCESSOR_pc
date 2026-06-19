/**
 * Timeline page — event cards, canvas strip, toggle, preview, export nav.
 */

export function mount(container) {
  container.innerHTML = `
    <div class="timeline-layout">
      <div class="timeline-toolbar">
        <span class="summary" id="tl-summary">Loading…</span>
        <div class="actions">
          <button class="btn" id="sel-all">Select All</button>
          <button class="btn" id="sel-none">Select None</button>
          <button class="btn btn-success" id="quick-export-btn">Quick Export</button>
          <button class="btn btn-primary" id="export-selected-btn">Export Selected</button>
        </div>
      </div>
      <div class="canvas-strip-wrap">
        <canvas id="timeline-canvas"></canvas>
      </div>
      <div class="events-list" id="events-list"></div>
    </div>
  `;

  let events = [];
  let job    = {};

  async function load() {
    [job, events] = await Promise.all([
      fetch("/api/job").then(r => r.json()),
      fetch("/api/job/events").then(r => r.json()),
    ]);
    render();
  }

  function render() {
    const summary = container.querySelector("#tl-summary");
    const included = events.filter(e => e.included);
    const totalDur = events.reduce((s, e) => s + (e.end_s - e.start_s), 0);
    const inclDur  = included.reduce((s, e) => s + (e.end_s - e.start_s), 0);
    summary.textContent = `${events.length} events · ${included.length} selected · ${fmt(inclDur)} / ${fmt(totalDur)} total`;

    // Canvas strip
    drawCanvas();

    // Event list
    const list = container.querySelector("#events-list");
    if (events.length === 0) {
      list.innerHTML = `
        <div class="no-events-diag">
          <h2>No motion detected</h2>
          <p>Try increasing the sensitivity to High, or verify the source video contains motion.</p>
          <button class="btn" style="margin-top:16px" onclick="window.go('/')">Try Again</button>
        </div>`;
      return;
    }

    list.innerHTML = "";
    events.forEach((ev, idx) => {
      const card = document.createElement("div");
      card.className = "event-card" + (ev.included ? "" : " excluded");
      const hasClockTime = ev.start_clock && ev.end_clock;
      card.innerHTML = `
        <div class="event-idx">#${idx + 1}</div>
        <div class="event-times">
          <div class="primary">${hasClockTime ? `${ev.start_clock} → ${ev.end_clock}` : `${fmt(ev.start_s)} → ${fmt(ev.end_s)}`}</div>
          <div class="secondary muted">
            ${hasClockTime ? `${fmt(ev.start_s)} → ${fmt(ev.end_s)} &nbsp;·&nbsp; ` : ""}${fmt(ev.end_s - ev.start_s)} &nbsp;·&nbsp; score ${(ev.peak_motion_score || 0).toFixed(3)}
          </div>
        </div>
        ${ev.zone_label ? `<span class="event-label">${ev.zone_label}</span>` : ""}
        <button class="btn event-preview-btn" data-idx="${idx}">Preview</button>
      `;
      card.addEventListener("click", async (e) => {
        if (e.target.closest(".event-preview-btn")) return;
        const resp = await fetch(`/api/job/events/${idx}/toggle`, { method: "PUT" });
        if (resp.ok) {
          events[idx] = await resp.json();
          render();
        }
      });
      card.querySelector(".event-preview-btn").addEventListener("click", async (e) => {
        e.stopPropagation();
        showPreview(idx);
      });
      list.appendChild(card);
    });
  }

  function drawCanvas() {
    const canvas = container.querySelector("#timeline-canvas");
    if (!canvas) return;
    canvas.width  = canvas.offsetWidth;
    canvas.height = 48;
    const ctx   = canvas.getContext("2d");
    const dur   = job.source_info ? job.source_info.duration_s : 1;
    const W = canvas.width, H = canvas.height;
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue("--surface2").trim();
    ctx.fillRect(0, 0, W, H);
    events.forEach(ev => {
      const x1 = (ev.start_s / dur) * W;
      const x2 = (ev.end_s   / dur) * W;
      ctx.fillStyle = ev.included ? "#4f8ef7" : "#555";
      ctx.fillRect(x1, 4, Math.max(2, x2 - x1), H - 8);
    });
  }

  async function showPreview(idx) {
    const resp = await fetch(`/api/job/preview/${idx}`, { method: "POST" });
    if (!resp.ok) { alert("Could not generate preview"); return; }
    const { url } = await resp.json();

    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal preview-modal" style="max-width:640px">
        <video src="${url}" controls autoplay style="width:100%;border-radius:8px;background:#000"></video>
        <button class="btn close-btn" style="width:100%;margin-top:12px;justify-content:center">Close</button>
      </div>`;
    document.body.appendChild(overlay);
    overlay.querySelector(".close-btn").onclick = () => document.body.removeChild(overlay);
  }

  // Select all / none
  container.querySelector("#sel-all").onclick  = async () => {
    for (let i = 0; i < events.length; i++) {
      if (!events[i].included) {
        const r = await fetch(`/api/job/events/${i}/toggle`, { method: "PUT" });
        if (r.ok) events[i] = await r.json();
      }
    }
    render();
  };
  container.querySelector("#sel-none").onclick = async () => {
    for (let i = 0; i < events.length; i++) {
      if (events[i].included) {
        const r = await fetch(`/api/job/events/${i}/toggle`, { method: "PUT" });
        if (r.ok) events[i] = await r.json();
      }
    }
    render();
  };

  container.querySelector("#quick-export-btn").onclick    = () => window.go("/export?quick=1");
  container.querySelector("#export-selected-btn").onclick = () => window.go("/export");

  window.addEventListener("resize", drawCanvas);
  container._cleanup = () => window.removeEventListener("resize", drawCanvas);

  load();
}

function fmt(s) {
  if (s == null) return "?";
  const t = Math.round(s);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const sc = t % 60;
  return [h ? String(h).padStart(2,"0") : null, String(m).padStart(2,"0"), String(sc).padStart(2,"0")]
    .filter(Boolean).join(":");
}
