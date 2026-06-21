/**
 * Timeline page — Phase 2 rewrite.
 * Adds: label filter bar, score slider, canvas grey-out, confidence badges,
 * label pills, multi-select (Ctrl+click + checkboxes), bulk toolbar, undo,
 * keyboard navigation, CSS content-visibility virtual scroll.
 */
import { uiState, resetUiState } from '/static/js/session-state.js';
import { logVideoEvents } from '/static/js/debug-log.js';

const LABEL_COLOURS = {
  person:  'var(--label-person)',
  car:     'var(--label-car)',
  dog:     'var(--label-dog)',
  cat:     'var(--label-cat)',
  bus:     'var(--label-bus)',
  bicycle: 'var(--label-bicycle)',
};

function labelColour(label) {
  if (!label) return 'var(--label-default)';
  return LABEL_COLOURS[label.toLowerCase()] || 'var(--label-default)';
}

function badgeClass(score) {
  if (score >= 0.7) return 'badge--green';
  if (score >= 0.4) return 'badge--amber';
  return 'badge--red';
}

export function mount(container) {
  container.innerHTML = `
    <div class="timeline-layout">
      <div class="timeline-toolbar" id="tl-toolbar">
        <div class="filter-bar" id="filter-bar"></div>
        <div style="display:flex;align-items:center;gap:var(--gap);flex-wrap:wrap;padding:6px 0">
          <div class="score-slider-wrap">
            <label style="margin:0;text-transform:none;letter-spacing:0;font-size:12px">Score ≥</label>
            <input type="range" id="score-threshold" min="0" max="1" step="0.05" value="0">
            <span id="score-val">0.00</span>
          </div>
          <span class="summary-count" id="ev-count"></span>
          <button class="btn" id="clear-filters-btn" style="font-size:12px;padding:4px 10px">Clear Filters</button>
          <button class="btn btn-success" id="quick-export-btn">Quick Export</button>
        </div>
        <div class="label-summary hidden" id="label-summary"></div>
      </div>
      <div class="bulk-toolbar hidden" id="bulk-toolbar">
        <span class="bulk-label" id="bulk-label">0 selected</span>
        <button class="btn" id="btn-include">Include</button>
        <button class="btn" id="btn-exclude">Exclude</button>
        <button class="btn" id="btn-invert-sel">Invert Selection</button>
        <button class="btn" id="btn-sel-visible">Select Visible</button>
        <button class="btn" id="btn-undo" disabled>Undo</button>
        <button class="btn" id="btn-clear-sel">Clear Selection</button>
      </div>
      <div class="canvas-strip-wrap">
        <canvas id="timeline-canvas"></canvas>
      </div>
      <div class="events-list" id="events-list" tabindex="0"></div>
    </div>
  `;

  let events = [];
  let job    = {};
  let focusedIdx = null;

  // ── Data loading ───────────────────────────────────────────────────────────

  async function load() {
    [job, events] = await Promise.all([
      fetch('/api/job').then(r => r.json()),
      fetch('/api/job/events').then(r => r.json()),
    ]);
    buildFilterBar();
    renderFiltered();
    buildLabelSummary();
  }

  // ── Filter helpers ─────────────────────────────────────────────────────────

  function getVisibleEvents() {
    return events.filter(ev => {
      const score = ev.peak_motion_score || 0;
      if (score < uiState.scoreThreshold) return false;
      if (uiState.labelFilter.size === 0) return true;
      if (!ev.zone_label) return uiState.labelFilter.has('Unlabelled');
      return uiState.labelFilter.has(ev.zone_label);
    });
  }

  function buildFilterBar() {
    const bar = container.querySelector('#filter-bar');
    bar.innerHTML = '';
    const labels = new Set();
    let hasUnlabelled = false;
    events.forEach(ev => {
      if (ev.zone_label) labels.add(ev.zone_label);
      else hasUnlabelled = true;
    });
    if (labels.size === 0 && !hasUnlabelled) return;
    labels.forEach(lbl => bar.appendChild(makeChip(lbl)));
    if (hasUnlabelled) bar.appendChild(makeChip('Unlabelled'));
  }

  function makeChip(lbl) {
    const chip = document.createElement('button');
    chip.className = 'label-chip' + (uiState.labelFilter.has(lbl) ? ' active' : '');
    chip.textContent = lbl;
    chip.dataset.label = lbl;
    chip.addEventListener('click', () => {
      if (uiState.labelFilter.has(lbl)) uiState.labelFilter.delete(lbl);
      else uiState.labelFilter.add(lbl);
      chip.classList.toggle('active', uiState.labelFilter.has(lbl));
      renderFiltered();
    });
    return chip;
  }

  function buildLabelSummary() {
    const summaryEl = container.querySelector('#label-summary');
    // Only show when YOLO events exist (events with zone_label)
    if (!events.some(e => e.zone_label)) {
      summaryEl.classList.add('hidden');
      return;
    }
    const counts = {};
    events.forEach(ev => {
      if (ev.zone_label) counts[ev.zone_label] = (counts[ev.zone_label] || 0) + 1;
    });
    summaryEl.innerHTML = Object.entries(counts)
      .map(([lbl, n]) => `<span class="label-summary-chip" style="border-color:${labelColour(lbl)}">${lbl}×${n}</span>`)
      .join('');
    summaryEl.classList.remove('hidden');
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  function renderFiltered() {
    const visible = getVisibleEvents();
    container.querySelector('#ev-count').textContent =
      `${visible.length} shown / ${events.length} total`;
    drawCanvas();
    renderCards(visible);
  }

  function renderCards(visible) {
    const list = container.querySelector('#events-list');
    if (events.length === 0) {
      list.innerHTML = `
        <div class="no-events-diag">
          <h2>No motion detected</h2>
          <p>Try increasing the sensitivity to High, or verify the source video contains motion.</p>
          <button class="btn" style="margin-top:16px" onclick="window.go('/')">Try Again</button>
        </div>`;
      return;
    }

    if (visible.length === 0) {
      list.innerHTML = `
        <div class="no-events-diag">
          <h2>No events match this filter</h2>
          <p>Try a different label or lower the score threshold.</p>
          <button class="btn" id="empty-state-clear-btn" style="margin-top:16px">Clear Filters</button>
        </div>`;
      list.querySelector('#empty-state-clear-btn').addEventListener('click', () => {
        container.querySelector('#clear-filters-btn').click();
      });
      return;
    }

    list.innerHTML = '';
    visible.forEach((ev, visIdx) => {
      const idx = events.indexOf(ev);
      const score = ev.peak_motion_score || 0;
      const isSelected = uiState.selectedIndices.has(idx);
      const isFocused  = focusedIdx === idx;
      const hasClockTime = ev.start_clock && ev.end_clock;

      const card = document.createElement('div');
      card.className = 'event-card'
        + (ev.included ? '' : ' excluded')
        + (isSelected  ? ' selected' : '')
        + (isFocused   ? ' focused'  : '');
      card.dataset.idx = idx;

      card.innerHTML = `
        <input type="checkbox" class="card-checkbox" ${isSelected ? 'checked' : ''}>
        <div class="event-idx">#${idx + 1}</div>
        <div class="event-times">
          <div class="primary">${hasClockTime ? `${ev.start_clock} → ${ev.end_clock}` : `${fmt(ev.start_s)} → ${fmt(ev.end_s)}`}</div>
          <div class="secondary muted">
            ${hasClockTime ? `${fmt(ev.start_s)} → ${fmt(ev.end_s)} &nbsp;·&nbsp; ` : ''}${fmt(ev.end_s - ev.start_s)} &nbsp;·&nbsp; score ${score.toFixed(3)}
          </div>
        </div>
        <span class="confidence-badge ${badgeClass(score)}">${score.toFixed(2)}</span>
        ${ev.zone_label ? `<span class="event-label" style="background:${labelColour(ev.zone_label)}" data-label="${ev.zone_label}">${ev.zone_label}</span>` : ''}
        <button class="btn event-preview-btn" data-idx="${idx}">Preview</button>
      `;

      // Toggle include on card click (not on ctrl+click or preview)
      card.addEventListener('click', async (e) => {
        if (e.target.closest('.event-preview-btn')) return;
        if (e.ctrlKey || e.metaKey) {
          // Multi-select
          if (uiState.selectedIndices.has(idx)) uiState.selectedIndices.delete(idx);
          else uiState.selectedIndices.add(idx);
          updateBulkToolbar();
          renderFiltered();
          return;
        }
        const resp = await fetch(`/api/job/events/${idx}/toggle`, { method: 'PUT' });
        if (resp.ok) {
          events[idx] = await resp.json();
          renderFiltered();
        }
      });

      // Label pill quick-filter
      const pill = card.querySelector('.event-label');
      if (pill) {
        pill.addEventListener('click', (e) => {
          e.stopPropagation();
          const lbl = pill.dataset.label;
          uiState.labelFilter.add(lbl);
          container.querySelectorAll('.label-chip').forEach(c => {
            c.classList.toggle('active', uiState.labelFilter.has(c.dataset.label));
          });
          renderFiltered();
        });
      }

      // Preview button
      card.querySelector('.event-preview-btn').addEventListener('click', async (e) => {
        e.stopPropagation();
        await showPreview(idx);
      });

      list.appendChild(card);
    });

    // Update selecting class
    const listEl = container.querySelector('#events-list');
    listEl.classList.toggle('selecting', uiState.selectedIndices.size > 0);
  }

  // ── Canvas ─────────────────────────────────────────────────────────────────

  function drawCanvas() {
    const canvas = container.querySelector('#timeline-canvas');
    if (!canvas) return;
    canvas.width  = canvas.offsetWidth;
    canvas.height = 48;
    const ctx = canvas.getContext('2d');
    const dur = job.source_info ? job.source_info.duration_s : 1;
    const W = canvas.width, H = canvas.height;
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--surface2').trim();
    ctx.fillRect(0, 0, W, H);

    const activeFilter = uiState.labelFilter.size > 0;
    events.forEach(ev => {
      const x1 = (ev.start_s / dur) * W;
      const x2 = (ev.end_s   / dur) * W;
      const inFilter = !activeFilter ||
        (ev.zone_label ? uiState.labelFilter.has(ev.zone_label) : uiState.labelFilter.has('Unlabelled'));
      const belowThreshold = (ev.peak_motion_score || 0) < uiState.scoreThreshold;
      ctx.globalAlpha = (inFilter && !belowThreshold) ? 1.0 : 0.2;
      ctx.fillStyle = ev.included
        ? (labelColour(ev.zone_label) !== 'var(--label-default)' ? labelColour(ev.zone_label) : '#4f8ef7')
        : '#555';
      ctx.fillRect(x1, 4, Math.max(2, x2 - x1), H - 8);
    });
    ctx.globalAlpha = 1.0;
  }

  // ── Bulk toolbar (T018) ────────────────────────────────────────────────────

  function updateBulkToolbar() {
    const n = uiState.selectedIndices.size;
    const toolbar = container.querySelector('#bulk-toolbar');
    toolbar.classList.toggle('hidden', n === 0);
    container.querySelector('#bulk-label').textContent = `${n} selected`;
    container.querySelector('#btn-undo').disabled = !uiState.lastBulkOp;
    const listEl = container.querySelector('#events-list');
    listEl.classList.toggle('selecting', n > 0);
  }

  // ── Bulk actions (T019) ────────────────────────────────────────────────────

  async function bulkToggle(include) {
    const indices = [...uiState.selectedIndices];
    if (!indices.length) return;
    // Save undo state
    uiState.lastBulkOp = {
      indices,
      prevIncluded: indices.map(i => events[i].included),
    };
    const resp = await fetch('/api/job/events/bulk', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ indices, include }),
    });
    if (resp.ok) {
      const data = await resp.json();
      data.events.forEach((ev, i) => { events[i] = ev; });
    }
    updateBulkToolbar();
    renderFiltered();
  }

  // ── Undo (T020) ────────────────────────────────────────────────────────────

  async function undoBulk() {
    if (!uiState.lastBulkOp) return;
    const { indices, prevIncluded } = uiState.lastBulkOp;
    const trueIdx  = indices.filter((_, i) => prevIncluded[i] === true);
    const falseIdx = indices.filter((_, i) => prevIncluded[i] === false);
    if (trueIdx.length) {
      const r = await fetch('/api/job/events/bulk', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ indices: trueIdx, include: true }),
      });
      if (r.ok) { const d = await r.json(); d.events.forEach((ev, i) => { events[i] = ev; }); }
    }
    if (falseIdx.length) {
      const r = await fetch('/api/job/events/bulk', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ indices: falseIdx, include: false }),
      });
      if (r.ok) { const d = await r.json(); d.events.forEach((ev, i) => { events[i] = ev; }); }
    }
    uiState.lastBulkOp = null;
    updateBulkToolbar();
    renderFiltered();
  }

  // ── Selection clear / Escape handler (T021) — shared function reused by T025 ──

  function clearSelection() {
    uiState.selectedIndices.clear();
    uiState.lastBulkOp = null;
    updateBulkToolbar();
    renderFiltered();
  }

  // ── Preview ────────────────────────────────────────────────────────────────

  async function showPreview(idx) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal preview-modal" style="max-width:720px;padding:20px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
          <h3 style="margin:0">Event #${idx + 1} Preview</h3>
          <button class="btn" id="preview-close" style="padding:4px 12px;font-size:12px">✕ Close</button>
        </div>

        <!-- Loading -->
        <div id="preview-loading" style="text-align:center;padding:48px 0;color:var(--text-dim)">
          <div style="font-size:13px;margin-bottom:6px">Generating preview clip…</div>
          <div style="font-size:11px;opacity:.6">This may take a few seconds</div>
        </div>

        <!-- Player — rendered in DOM immediately but hidden until clip is ready -->
        <div id="preview-player" style="display:none">
          <video id="preview-video"
            controls playsinline muted
            preload="auto"
            style="width:100%;border-radius:8px;background:#000;max-height:420px;display:block">
          </video>
          <div id="preview-status" style="font-size:11px;color:var(--text-dim);margin-top:6px;text-align:center">
            Click play or use the controls to start
          </div>
        </div>

        <!-- Error -->
        <div id="preview-error" style="display:none;color:var(--danger);text-align:center;padding:32px 0;font-size:13px"></div>
      </div>`;
    document.body.appendChild(overlay);

    const loadingEl = overlay.querySelector('#preview-loading');
    const playerEl  = overlay.querySelector('#preview-player');
    const errorEl   = overlay.querySelector('#preview-error');
    const statusEl  = overlay.querySelector('#preview-status');
    const video     = overlay.querySelector('#preview-video');

    logVideoEvents(video, 'preview');

    function showError(msg) {
      loadingEl.style.display = 'none';
      playerEl.style.display  = 'none';
      errorEl.style.display   = '';
      errorEl.textContent     = msg;
    }

    function closePreview() {
      video.pause();
      video.removeAttribute('src');
      video.load();
      if (document.body.contains(overlay)) document.body.removeChild(overlay);
    }

    overlay.querySelector('#preview-close').addEventListener('click', closePreview);
    overlay.addEventListener('click', e => { if (e.target === overlay) closePreview(); });

    // Listen for video errors — must be attached before src is set
    video.addEventListener('error', () => {
      const code = video.error ? video.error.code : '?';
      const msgs = { 1: 'Aborted', 2: 'Network error', 3: 'Decode error', 4: 'Format not supported' };
      showError(`Video error (${msgs[code] || code}). Try a different event.`);
    });

    try {
      const resp = await fetch(`/api/job/preview/${idx}`, { method: 'POST' });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        showError(data.detail || 'Preview generation failed');
        return;
      }
      const { url } = await resp.json();

      // CRITICAL: show the player div BEFORE setting video.src.
      // Chromium defers loading for video elements inside display:none containers —
      // the element must be visible when src is assigned for metadata to load immediately.
      loadingEl.style.display = 'none';
      playerEl.style.display  = '';

      // Set src now that the element is visible
      video.src = url;
      video.load();

      // Once metadata is available, seek to event start (skip 2s pre-padding) and play
      video.addEventListener('loadedmetadata', () => {
        statusEl.style.display = 'none';
        // Seek past the 2s pre-padding to show the actual event content
        if (video.duration > 2) video.currentTime = 2;
        video.play().catch(() => {
          // If autoplay fails, show a hint; user can click the play button
          statusEl.style.display = '';
          statusEl.textContent   = 'Click ▶ to play';
        });
      }, { once: true });

    } catch (err) {
      showError('Network error: ' + err.message);
    }
  }

  // ── Wire bulk toolbar buttons ──────────────────────────────────────────────

  container.querySelector('#btn-include').addEventListener('click', () => bulkToggle(true));
  container.querySelector('#btn-exclude').addEventListener('click', () => bulkToggle(false));
  container.querySelector('#btn-undo').addEventListener('click', undoBulk);
  container.querySelector('#btn-clear-sel').addEventListener('click', clearSelection);

  container.querySelector('#btn-invert-sel').addEventListener('click', () => {
    // Invert SELECTION membership — swap which visible events are selected
    const visible = getVisibleEvents();
    const visibleIndices = new Set(visible.map(ev => events.indexOf(ev)));
    const newSelected = new Set();
    visibleIndices.forEach(idx => {
      if (!uiState.selectedIndices.has(idx)) newSelected.add(idx);
    });
    uiState.selectedIndices.clear();
    newSelected.forEach(idx => uiState.selectedIndices.add(idx));
    updateBulkToolbar();
    renderFiltered();
  });

  container.querySelector('#btn-sel-visible').addEventListener('click', () => {
    const visible = getVisibleEvents();
    visible.forEach(ev => uiState.selectedIndices.add(events.indexOf(ev)));
    updateBulkToolbar();
    renderFiltered();
  });

  // ── Score slider (T011) ────────────────────────────────────────────────────

  const scoreSlider = container.querySelector('#score-threshold');
  scoreSlider.value = uiState.scoreThreshold;
  container.querySelector('#score-val').textContent = uiState.scoreThreshold.toFixed(2);
  scoreSlider.addEventListener('input', () => {
    uiState.scoreThreshold = parseFloat(scoreSlider.value);
    container.querySelector('#score-val').textContent = uiState.scoreThreshold.toFixed(2);
    renderFiltered();
  });

  // ── Clear filters ──────────────────────────────────────────────────────────

  container.querySelector('#clear-filters-btn').addEventListener('click', () => {
    uiState.labelFilter.clear();
    uiState.scoreThreshold = 0.0;
    scoreSlider.value = 0;
    container.querySelector('#score-val').textContent = '0.00';
    container.querySelectorAll('.label-chip').forEach(c => c.classList.remove('active'));
    renderFiltered();
  });

  // ── Quick export ───────────────────────────────────────────────────────────

  container.querySelector('#quick-export-btn').addEventListener('click', () => window.go('/export'));

  // ── Events-list keyboard nav (T024) ───────────────────────────────────────

  const listEl = container.querySelector('#events-list');

  listEl.addEventListener('keydown', (e) => {
    const visible = getVisibleEvents();
    if (!visible.length) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      focusedIdx = (focusedIdx === null) ? events.indexOf(visible[0])
        : Math.min(events.length - 1, focusedIdx + 1);
      // Advance to next visible event
      const nextVis = visible.find(ev => events.indexOf(ev) >= focusedIdx);
      if (nextVis) focusedIdx = events.indexOf(nextVis);
      scrollFocused();
      renderFiltered();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (focusedIdx === null) return;
      const prevVis = [...visible].reverse().find(ev => events.indexOf(ev) < focusedIdx);
      if (prevVis) focusedIdx = events.indexOf(prevVis);
      scrollFocused();
      renderFiltered();
    } else if (e.key === ' ') {
      e.preventDefault();
      if (focusedIdx === null) return;
      fetch(`/api/job/events/${focusedIdx}/toggle`, { method: 'PUT' })
        .then(r => r.ok ? r.json() : null)
        .then(ev => { if (ev) { events[focusedIdx] = ev; renderFiltered(); } });
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (focusedIdx !== null) showPreview(focusedIdx);
    } else if (e.key === 'Escape') {
      clearSelection();
    }
  });

  function scrollFocused() {
    const card = container.querySelector(`.event-card[data-idx="${focusedIdx}"]`);
    if (card) card.scrollIntoView({ block: 'nearest' });
  }

  // ── Global keyboard shortcuts (T025) — reuses clearSelection from T021 ────

  function onWindowKey(e) {
    const tag = e.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (e.key === 'a' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      const visible = getVisibleEvents();
      visible.forEach(ev => uiState.selectedIndices.add(events.indexOf(ev)));
      updateBulkToolbar();
      renderFiltered();
    } else if (e.key === 'd' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      uiState.selectedIndices.clear();
      updateBulkToolbar();
      renderFiltered();
    } else if (e.key === 'e' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      window.go('/export');
    } else if (e.key === 'z' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      undoBulk();
    } else if (e.key === 'Escape') {
      clearSelection();  // reuse T021 logic — NOT a duplicate handler
    }
  }

  window.addEventListener('keydown', onWindowKey);

  // Click on events-list container background clears selection
  listEl.addEventListener('click', (e) => {
    if (e.target === listEl) clearSelection();
  });

  // ── Canvas resize ──────────────────────────────────────────────────────────

  window.addEventListener('resize', drawCanvas);

  container._cleanup = () => {
    window.removeEventListener('resize', drawCanvas);
    window.removeEventListener('keydown', onWindowKey);
  };

  load();
}

function fmt(s) {
  if (s == null) return '?';
  const t = Math.round(s);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const sc = t % 60;
  return [h ? String(h).padStart(2, '0') : null, String(m).padStart(2, '0'), String(sc).padStart(2, '0')]
    .filter(Boolean).join(':');
}
