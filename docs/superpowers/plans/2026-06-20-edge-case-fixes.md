# Edge Case Follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close 3 confirmed coverage gaps from the `/speckit.analyze` report on `specs/002-ui-tag-filter/` — each is an explicit `spec.md` Edge Case with zero task coverage in `tasks.md` and confirmed absent from the shipped code via direct grep against `timeline.js`/`export.js`.

**Architecture:** Three independent, small UI-logic additions to the already-shipped Phase 2 frontend — no new files, no backend changes. Each fix mirrors an existing, working pattern already present in the same file (e.g. the new empty-state branch sits right next to the existing `events.length === 0` branch it's modeled on).

**Tech Stack:** Vanilla ES modules (no build step), same as the rest of this codebase.

## Global Constraints

- These are UI-only fixes for `specs/002-ui-tag-filter/tasks.md` Phase 9 (T044-T046); see that file for the one-line task descriptions this plan elaborates with full code.
- No JS test runner exists in this project. Verification is via temporary, throwaway Python scripts driving a real `QWebEngineView` instance, deleted after use — same convention already established in `docs/superpowers/specs/2026-06-20-debug-log-panel-design.md`.
- The existing pytest suite (`tests/`) must remain passing (`python -m pytest tests/ -q`) after every task, since none of these changes touch Python files.
- Reuse exact wording from `spec.md`'s Edge Cases section verbatim: "No events match this filter" (L124), "No events selected for export — adjust filters or include more events" (L125), "Requires Object Detection mode" (L130).
- Match existing code style exactly: disabled/tooltip pattern for buttons already exists in `static/js/pages/home.js` (capability-detection fix) — `btn.disabled = true; btn.title = "..."; btn.style.opacity = "0.45"; btn.style.cursor = "not-allowed";` — reuse this exact pattern for T3's preset button, don't invent a new one.
- Git policy: this project's standing rule is to commit only when the user explicitly asks. If the user has authorized commits for this work, each task's commit step may run as written; otherwise hold commits and ask before running them.

---

### Task 1: Empty filter-state message in the timeline event list

**Files:**
- Modify: `static/js/pages/timeline.js:145-156` (inside `renderCards()`)
- Test (temporary, delete after this task): `_diag_edge_empty_filter.py` (repo root)

**Interfaces:**
- Consumes: `getVisibleEvents()`, `renderFiltered()`, `uiState` (from `/static/js/session-state.js`) — all already defined in this file; no signature changes.
- Produces: nothing new exported — this is a rendering branch inside the existing, unexported `renderCards(visible)` function.

**Prerequisite:** backend reachable at `http://127.0.0.1:5151` (`python launcher.py` if not already running; verify with `curl -s http://127.0.0.1:5151/api/system/stats`).

- [ ] **Step 1: Write the failing test**

Create `_diag_edge_empty_filter.py`:

```python
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QTimer

app = QApplication(sys.argv)
view = QWebEngineView()

html = """
<html><body>
<div id="app"></div>
<script type="module">
  window.__result = "PENDING";

  const FAKE_JOB = { status: "completed", source_info: { duration_s: 10 } };
  const FAKE_EVENTS = [
    { start_s: 0, end_s: 1, peak_motion_score: 0.9, included: true, zone_label: null },
    { start_s: 2, end_s: 3, peak_motion_score: 0.9, included: true, zone_label: null }
  ];
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (url, opts) => {
    if (url === "/api/job") return new Response(JSON.stringify(FAKE_JOB), { status: 200 });
    if (url === "/api/job/events") return new Response(JSON.stringify(FAKE_EVENTS), { status: 200 });
    return originalFetch(url, opts);
  };

  const { mount } = await import("/static/js/pages/timeline.js");
  mount(document.getElementById("app"));

  setTimeout(() => {
    const slider = document.getElementById("score-threshold");
    slider.value = "1";
    slider.dispatchEvent(new Event("input"));

    setTimeout(() => {
      const list = document.getElementById("events-list");
      const hasMessage = list.innerHTML.includes("No events match this filter");
      const hasButton  = !!list.querySelector("button");
      window.__result = (hasMessage && hasButton) ? "PASS" : "FAIL:" + list.innerHTML.slice(0, 400);
    }, 300);
  }, 600);
</script>
</body></html>
"""
view.setHtml(html, QUrl("http://127.0.0.1:5151/"))

def check():
    view.page().runJavaScript("window.__result", lambda r: (print("RESULT:", r), app.quit()))

QTimer.singleShot(2000, check)
sys.exit(app.exec())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python _diag_edge_empty_filter.py`
Expected: `RESULT: FAIL:...` — the slider drag sets `uiState.scoreThreshold = 1.0`, filtering out both fake events (`peak_motion_score: 0.9 < 1.0`), but `renderCards()` currently has no branch for "events exist but none are visible," so it falls through to `list.innerHTML = ''` (empty list, no message).

- [ ] **Step 3: Write minimal implementation**

In `static/js/pages/timeline.js`, change:

```js
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

    list.innerHTML = '';
```

to:

```js
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python _diag_edge_empty_filter.py`
Expected: `RESULT: PASS`

- [ ] **Step 5: Delete the diagnostic script**

```bash
rm _diag_edge_empty_filter.py
```

- [ ] **Step 6: Run full backend test suite (confirm no regression)**

Run: `python -m pytest tests/ -q --tb=short`
Expected: `60 passed, 2 skipped`

- [ ] **Step 7: Commit (confirm with user first — see Global Constraints)**

```bash
git add static/js/pages/timeline.js
git commit -m "fix: show empty-state message when label/score filter matches no events"
```

---

### Task 2: Zero-included warning after a bulk exclude

**Files:**
- Modify: `static/js/pages/timeline.js:46-54` (toolbar HTML, add warning element)
- Modify: `static/js/pages/timeline.js:275-320` (`bulkToggle()` and `undoBulk()`)
- Test (temporary, delete after this task): `_diag_edge_zero_included.py` (repo root)

**Interfaces:**
- Consumes: `events` (module-scoped array), `uiState.selectedIndices` — already defined, no signature changes.
- Produces: a new unexported `checkZeroIncludedWarning()` function in the same file, called from `bulkToggle()` and `undoBulk()`.

**Prerequisite:** same as Task 1.

- [ ] **Step 1: Write the failing test**

Create `_diag_edge_zero_included.py`:

```python
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QTimer

app = QApplication(sys.argv)
view = QWebEngineView()

html = """
<html><body>
<div id="app"></div>
<script type="module">
  window.__result = "PENDING";

  const FAKE_JOB = { status: "completed", source_info: { duration_s: 10 } };
  const FAKE_EVENTS = [
    { start_s: 0, end_s: 1, peak_motion_score: 0.9, included: true, zone_label: null },
    { start_s: 2, end_s: 3, peak_motion_score: 0.9, included: true, zone_label: null }
  ];
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (url, opts) => {
    if (url === "/api/job") return new Response(JSON.stringify(FAKE_JOB), { status: 200 });
    if (url === "/api/job/events") return new Response(JSON.stringify(FAKE_EVENTS), { status: 200 });
    if (url === "/api/job/events/bulk") {
      const body = JSON.parse(opts.body);
      const updated = FAKE_EVENTS.map((e, i) => body.indices.includes(i) ? { ...e, included: body.include } : e);
      body.indices.forEach(i => { FAKE_EVENTS[i] = updated[i]; });
      return new Response(JSON.stringify({ updated: body.indices.length, events: FAKE_EVENTS }), { status: 200 });
    }
    return originalFetch(url, opts);
  };

  const { mount } = await import("/static/js/pages/timeline.js");
  mount(document.getElementById("app"));

  setTimeout(() => {
    // Select both event cards via the same Ctrl+click path the UI uses.
    // Re-query by data-idx between clicks: each click handler re-renders
    // and replaces the card DOM nodes, so a single cached NodeList would
    // go stale after the first click.
    document.querySelector(".event-card[data-idx='0']")
      .dispatchEvent(new MouseEvent("click", { ctrlKey: true, bubbles: true }));
    setTimeout(() => {
      document.querySelector(".event-card[data-idx='1']")
        .dispatchEvent(new MouseEvent("click", { ctrlKey: true, bubbles: true }));
      setTimeout(() => {
        document.getElementById("btn-exclude").click();
        setTimeout(() => {
          const warning = document.getElementById("zero-included-warning");
          const visible = warning && !warning.classList.contains("hidden");
          const text = warning ? warning.textContent : "NO_ELEMENT";
          window.__result = (visible && text.includes("No events selected for export")) ? "PASS" : "FAIL:" + text;
        }, 400);
      }, 300);
    }, 300);
  }, 600);
</script>
</body></html>
"""
view.setHtml(html, QUrl("http://127.0.0.1:5151/"))

def check():
    view.page().runJavaScript("window.__result", lambda r: (print("RESULT:", r), app.quit()))

QTimer.singleShot(2500, check)
sys.exit(app.exec())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python _diag_edge_zero_included.py`
Expected: `RESULT: FAIL:NO_ELEMENT` — `#zero-included-warning` doesn't exist yet.

- [ ] **Step 3: Write minimal implementation**

In `static/js/pages/timeline.js`, change the toolbar HTML from:

```js
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
```

to:

```js
      <div class="bulk-toolbar hidden" id="bulk-toolbar">
        <span class="bulk-label" id="bulk-label">0 selected</span>
        <button class="btn" id="btn-include">Include</button>
        <button class="btn" id="btn-exclude">Exclude</button>
        <button class="btn" id="btn-invert-sel">Invert Selection</button>
        <button class="btn" id="btn-sel-visible">Select Visible</button>
        <button class="btn" id="btn-undo" disabled>Undo</button>
        <button class="btn" id="btn-clear-sel">Clear Selection</button>
      </div>
      <div class="warning hidden" id="zero-included-warning" style="padding:8px 12px;font-size:12px">
        No events selected for export — adjust filters or include more events
      </div>
      <div class="canvas-strip-wrap">
```

Then add this function near `updateBulkToolbar()` (right after its closing brace, i.e. after the existing block ending `listEl.classList.toggle('selecting', n > 0); }`):

```js
  function checkZeroIncludedWarning() {
    const banner = container.querySelector('#zero-included-warning');
    const allExcluded = events.length > 0 && events.every(ev => !ev.included);
    banner.classList.toggle('hidden', !allExcluded);
  }
```

Then in `bulkToggle()`, change:

```js
    if (resp.ok) {
      const data = await resp.json();
      data.events.forEach((ev, i) => { events[i] = ev; });
    }
    updateBulkToolbar();
    renderFiltered();
  }
```

to:

```js
    if (resp.ok) {
      const data = await resp.json();
      data.events.forEach((ev, i) => { events[i] = ev; });
    }
    updateBulkToolbar();
    checkZeroIncludedWarning();
    renderFiltered();
  }
```

Then in `undoBulk()`, change the final three lines from:

```js
    uiState.lastBulkOp = null;
    updateBulkToolbar();
    renderFiltered();
  }
```

to:

```js
    uiState.lastBulkOp = null;
    updateBulkToolbar();
    checkZeroIncludedWarning();
    renderFiltered();
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python _diag_edge_zero_included.py`
Expected: `RESULT: PASS`

- [ ] **Step 5: Delete the diagnostic script**

```bash
rm _diag_edge_zero_included.py
```

- [ ] **Step 6: Run full backend test suite (confirm no regression)**

Run: `python -m pytest tests/ -q --tb=short`
Expected: `60 passed, 2 skipped`

- [ ] **Step 7: Commit (confirm with user first — see Global Constraints)**

```bash
git add static/js/pages/timeline.js
git commit -m "fix: warn when a bulk exclude leaves zero events included for export"
```

---

### Task 3: Grey out label-dependent preset in MOG2 mode

**Files:**
- Modify: `static/js/pages/export.js:235-244` (inside `loadSummary()`)
- Test (temporary, delete after this task): `_diag_edge_preset_disable.py` (repo root)

**Interfaces:**
- Consumes: `labels` array already computed in `loadSummary()` — no signature changes.
- Produces: nothing new exported — disables an existing DOM button in place.

**Prerequisite:** same as Task 1.

- [ ] **Step 1: Write the failing test**

Create `_diag_edge_preset_disable.py`:

```python
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QTimer

app = QApplication(sys.argv)
view = QWebEngineView()

html = """
<html><body>
<div id="app"></div>
<script type="module">
  window.__result = "PENDING";

  // MOG2-mode fake data: every event has zone_label === null
  const FAKE_JOB = { status: "completed", source_info: {}, settings: {} };
  const FAKE_EVENTS = [
    { start_s: 0, end_s: 1, peak_motion_score: 0.9, included: true, zone_label: null },
    { start_s: 2, end_s: 3, peak_motion_score: 0.9, included: true, zone_label: null }
  ];
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (url, opts) => {
    if (url === "/api/job") return new Response(JSON.stringify(FAKE_JOB), { status: 200 });
    if (url === "/api/job/events") return new Response(JSON.stringify(FAKE_EVENTS), { status: 200 });
    return originalFetch(url, opts);
  };

  const { mount } = await import("/static/js/pages/export.js");
  mount(document.getElementById("app"), new URLSearchParams(""));

  setTimeout(() => {
    const btn = document.querySelector('[data-preset="security"]');
    const ok = btn && btn.disabled === true && btn.title === "Requires Object Detection mode";
    window.__result = ok ? "PASS" : "FAIL:" + (btn ? `disabled=${btn.disabled} title=${btn.title}` : "NO_BUTTON");
  }, 700);
</script>
</body></html>
"""
view.setHtml(html, QUrl("http://127.0.0.1:5151/"))

def check():
    view.page().runJavaScript("window.__result", lambda r: (print("RESULT:", r), app.quit()))

QTimer.singleShot(2000, check)
sys.exit(app.exec())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python _diag_edge_preset_disable.py`
Expected: `RESULT: FAIL:disabled=false title=`

- [ ] **Step 3: Write minimal implementation**

In `static/js/pages/export.js`, change:

```js
    // Populate label scope dropdown
    const labels = [...new Set(events.map(e => e.zone_label).filter(Boolean))];
    const scopeEl = container.querySelector("#label-scope");
    labels.forEach(lbl => {
      const opt = document.createElement("option");
      opt.value = lbl; opt.textContent = lbl;
      scopeEl.appendChild(opt);
    });

    return job;
```

to:

```js
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

    return job;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python _diag_edge_preset_disable.py`
Expected: `RESULT: PASS`

- [ ] **Step 5: Delete the diagnostic script**

```bash
rm _diag_edge_preset_disable.py
```

- [ ] **Step 6: Run full backend test suite (confirm no regression)**

Run: `python -m pytest tests/ -q --tb=short`
Expected: `60 passed, 2 skipped`

- [ ] **Step 7: Commit (confirm with user first — see Global Constraints)**

```bash
git add static/js/pages/export.js
git commit -m "fix: disable label-dependent export preset in MOG2 mode"
```

---

### Task 4: Full verification and tasks.md sign-off

**Files:** none created or modified except `specs/002-ui-tag-filter/tasks.md` (check off T044-T047).

**Interfaces:** none new.

- [ ] **Step 1: Restart the real app and confirm health**

```bash
taskkill //IM python.exe //F 2>/dev/null || true
sleep 1
(python launcher.py > /tmp/launcher_out.log 2>&1 &)
sleep 6
curl -s http://127.0.0.1:5151/api/system/stats
```
Expected: a JSON stats line.

- [ ] **Step 2: Manual walkthrough (do this yourself in the live window)**

1. Load a video, run MOG2 detection. On the Timeline page, drag the score slider to maximum — confirm "No events match this filter" + Clear Filters button appears; click it, confirm filters reset and events reappear.
2. Ctrl+click to select all visible events, click "Exclude" — confirm the "No events selected for export…" banner appears; click Undo — confirm the banner disappears.
3. Navigate to Export — confirm "Security Report" is greyed out with a "Requires Object Detection mode" tooltip on hover (since this was a MOG2-mode job with no labels).

- [ ] **Step 3: Run full suite one final time**

Run: `python -m pytest tests/ -q --tb=short`
Expected: `60 passed, 2 skipped`

- [ ] **Step 4: Mark T044-T047 complete in tasks.md**

In `specs/002-ui-tag-filter/tasks.md`, change `- [ ] T044`, `- [ ] T045`, `- [ ] T046`, `- [ ] T047` to `- [X] T044`, `- [X] T045`, `- [X] T046`, `- [X] T047`.

- [ ] **Step 5: Ask the user about commits**

If Tasks 1-3's commits were deferred per the Global Constraints note, ask the user now whether to commit everything as one batch or as the three separate commits already drafted in each task.
