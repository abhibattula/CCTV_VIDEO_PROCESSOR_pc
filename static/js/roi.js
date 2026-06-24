/**
 * ROI (region-of-interest) polygon editor — a canvas overlay on a preview
 * image. Regions are session-scoped only (never persisted); per-job-only
 * enforcement happens via reset(), called by the page that mounts this
 * before loading a new preview image.
 */

export function mountRoiEditor(container, { onChange }) {
  let regions = [];          // { id, label, points: [{x,y}, ...] }[]
  let inProgress = [];       // {x,y}[] — points of the polygon being drawn
  const CLOSE_RADIUS_PX = 10;

  container.innerHTML = `
    <div class="roi-editor">
      <div class="roi-editor__stage">
        <img class="roi-editor__img" />
        <img class="roi-editor__heatmap hidden" />
        <canvas class="roi-editor__canvas"></canvas>
      </div>
      <div class="roi-editor__toolbar">
        <button class="btn" id="roi-cancel" disabled>Cancel Shape</button>
        <button class="btn btn-danger" id="roi-clear">Clear All</button>
        <span class="roi-editor__heatmap-toggle">
          <input type="checkbox" id="roi-heatmap-toggle" />
          <label for="roi-heatmap-toggle">Show Activity Heatmap</label>
        </span>
      </div>
      <div class="roi-editor__list" id="roi-list"></div>
    </div>
  `;

  const img = container.querySelector(".roi-editor__img");
  const heatmapImg = container.querySelector(".roi-editor__heatmap");
  const heatmapToggle = container.querySelector("#roi-heatmap-toggle");
  let heatmapLoaded = false;
  const canvas = container.querySelector(".roi-editor__canvas");
  const ctx = canvas.getContext("2d");
  let cssWidth = 0, cssHeight = 0;

  function resizeCanvas() {
    const rect = img.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    cssWidth = rect.width;
    cssHeight = rect.height;
    canvas.style.width = rect.width + "px";
    canvas.style.height = rect.height + "px";
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    redraw();
  }
  img.addEventListener("load", resizeCanvas);
  window.addEventListener("resize", resizeCanvas);

  function emitChange() {
    onChange(regions.map(r => ({ label: r.label, points: r.points.map(p => [p.x, p.y]) })));
  }

  function redraw() {
    ctx.clearRect(0, 0, cssWidth, cssHeight);
    const drawPath = (pts, closed, color) => {
      if (!pts.length) return;
      ctx.beginPath();
      pts.forEach((p, i) => {
        const px = p.x * cssWidth, py = p.y * cssHeight;
        i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
      });
      if (closed) ctx.closePath();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();
      if (closed) {
        ctx.fillStyle = color + "33"; // ~20% alpha
        ctx.fill();
      }
      pts.forEach(p => {
        ctx.beginPath();
        ctx.arc(p.x * cssWidth, p.y * cssHeight, 4, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();
      });
    };
    regions.forEach(r => drawPath(r.points, true, "#4f8ef7"));
    drawPath(inProgress, false, "#e8a23a");
  }

  const cancelBtn = container.querySelector("#roi-cancel");

  canvas.addEventListener("click", (e) => {
    const rect = canvas.getBoundingClientRect();
    const nx = (e.clientX - rect.left) / rect.width;
    const ny = (e.clientY - rect.top) / rect.height;

    if (inProgress.length >= 3) {
      const first = inProgress[0];
      const dx = (nx - first.x) * rect.width;
      const dy = (ny - first.y) * rect.height;
      if (Math.hypot(dx, dy) <= CLOSE_RADIUS_PX) {
        regions.push({
          id: crypto.randomUUID(),
          label: `Region ${regions.length + 1}`,
          points: inProgress,
        });
        inProgress = [];
        cancelBtn.disabled = true;
        renderList();
        redraw();
        emitChange();
        return;
      }
    }
    inProgress.push({ x: nx, y: ny });
    cancelBtn.disabled = false;
    redraw();
  });

  cancelBtn.addEventListener("click", () => {
    inProgress = [];
    cancelBtn.disabled = true;
    redraw();
  });

  container.querySelector("#roi-clear").addEventListener("click", () => {
    regions = [];
    inProgress = [];
    cancelBtn.disabled = true;
    redraw();
    renderList();
    emitChange();
  });

  function updateHeatmapVisibility() {
    const show = heatmapLoaded && heatmapToggle.checked;
    heatmapImg.classList.toggle("hidden", !show);
  }

  heatmapToggle.addEventListener("change", updateHeatmapVisibility);

  function renderList() {
    const list = container.querySelector("#roi-list");
    list.innerHTML = regions.map((r, i) => `
      <div class="roi-chip" data-idx="${i}">
        <input class="roi-chip__label" value="${escapeAttr(r.label)}" />
        <button class="roi-chip__delete" data-idx="${i}">&times;</button>
      </div>`).join("");
    list.querySelectorAll(".roi-chip__label").forEach((inp) => {
      inp.addEventListener("input", (e) => {
        const idx = +e.target.closest(".roi-chip").dataset.idx;
        regions[idx].label = e.target.value;
        emitChange();
      });
    });
    list.querySelectorAll(".roi-chip__delete").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const idx = +e.target.dataset.idx;
        regions.splice(idx, 1);
        renderList();
        redraw();
        emitChange();
      });
    });
  }

  function escapeAttr(s) {
    return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
  }

  function setImageSrc(url) {
    img.src = url;
  }

  function setHeatmapSrc(url) {
    heatmapLoaded = false;
    heatmapImg.onload = () => {
      heatmapLoaded = true;
      updateHeatmapVisibility();
    };
    heatmapImg.onerror = () => {
      // Expected, non-error case: no detection run has completed yet for
      // this job, so no heatmap exists. Handle silently.
      heatmapLoaded = false;
      updateHeatmapVisibility();
    };
    heatmapImg.src = url;
  }

  function reset() {
    regions = [];
    inProgress = [];
    cancelBtn.disabled = true;
    heatmapLoaded = false;
    heatmapImg.src = "";
    heatmapToggle.checked = false;
    updateHeatmapVisibility();
    redraw();
    renderList();
    emitChange();
  }

  function destroy() {
    window.removeEventListener("resize", resizeCanvas);
  }

  renderList();

  return { setImageSrc, setHeatmapSrc, reset, destroy };
}
