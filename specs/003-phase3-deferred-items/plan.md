# Implementation Plan: Phase 3 — Deferred Items Release

**Branch**: `003-phase3-deferred-items` | **Date**: 2026-06-21 | **Spec**: [specs/003-phase3-deferred-items/spec.md](spec.md)
**Input**: Feature specification from `/specs/003-phase3-deferred-items/spec.md`

---

## Summary

Phase 3 delivers the three features Phase 2 explicitly deferred: (1) custom export
presets the user can save/reuse/delete, persisted as user configuration; (2)
multi-level undo history on the Timeline page, replacing the single-slot undo from
Phase 2; (3) a light theme toggle, persisted client-side. The backend adds one new
small router (`app/api/presets.py`) and one config path
(`app/config.py:PRESETS_FILE`). The constitution was amended to v1.1.0 ahead of this
plan to add a narrow, already-ratified exemption to Principle I for user
configuration — this plan does not re-litigate that decision. All three features are
additive to existing Phase 2 files (`session-state.js`, `timeline.js`, `export.js`,
`base.css`) and one new file (`static/js/theme.js`); none require structural rework.

---

## Technical Context

**Language/Version**: Python 3.11+ (backend); Vanilla JS ES2022 modules (frontend — no build step)
**Primary Dependencies**: FastAPI (existing), no new dependencies required
**Storage**: N/A for job state (unchanged); ONE new flat JSON file
(`~/.cctv_processor/presets.json`) for user-configuration-only data, per the
Principle I exemption ratified in constitution v1.1.0 — job state remains
exclusively in-memory
**Testing**: `pytest tests/ -v` (backend); manual smoke test per quickstart.md
(frontend — no headless browser in this stack, unchanged from Phase 2)
**Target Platform**: Windows 10/11 primary; Linux ARM64 (Raspberry Pi 5) secondary
(unchanged — none of these 3 features touch detection/export engines or introduce
platform-specific code)
**Project Type**: Desktop app — PyQt6 shell wrapping a FastAPI SPA served on localhost
**Performance Goals**: Theme switch perceived as instant, <100ms (SC-P3-004); preset
save/list/delete round-trip <500ms (small flat-file JSON, no realistic risk of
missing this)
**Constraints**: No new Python packages; no npm/build step; no CDN resources;
`presets.json` MUST NOT store any key present in `app/session.py`'s `_DEFAULTS`
dict (constitution v1.1.0 boundary)
**Scale/Scope**: Single user; expect low tens of custom presets in realistic use,
not capped in this phase (per spec Assumptions)

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Session-First, No Persistence | ✅ COMPLIANT | Custom presets use the v1.1.0 user-configuration exemption — named, reusable, user-saved settings with no reference to any job, written only on explicit "Save as Preset" action, never automatically. Job state in `app/session.py` is completely untouched by this feature. Undo history and theme preference involve no persistence of job state either (undo is session-scoped client JS; theme is `localStorage`, never reaches the backend). |
| II. Cross-Platform | ✅ COMPLIANT | `PRESETS_FILE` derived via `Path.home() / ".cctv_processor"`, same pattern as existing `MODEL_DIR`/`JOBS_DIR`/`PREVIEW_DIR` in `app/config.py`. No OS-specific code introduced. |
| III. Test-First | ✅ COMPLIANT | New backend surface (`app/api/presets.py`) gets failing tests first (`tests/test_api_presets.py`), per Constitution Principle III. Frontend changes (undo, theme) have no test runner in this stack (established, unchanged Phase 2 precedent) — verified via direct app-driving instead, documented in quickstart.md. |
| IV. Callback-Driven | ✅ COMPLIANT | No detection/export engine changes at all in this feature — N/A. |
| V. Simplicity & YAGNI | ✅ COMPLIANT | No redo (not requested); no preset count cap (no evidence it's needed yet); no `app/core/` module for presets (it's ~55 lines of JSON read/write, same register as `app/api/system.py`); undo capped at a fixed constant rather than made configurable (no use case for configuring it). |

No constitution violations. No Complexity Tracking entries required.

---

## Project Structure

### Documentation (this feature)

```text
specs/003-phase3-deferred-items/
├── plan.md              ← this file
├── research.md          ← Phase 0 output (3 decisions documented)
├── data-model.md         ← Phase 1 output (entities and field definitions)
├── quickstart.md        ← Phase 1 output (3 integration scenarios, one per user story)
├── contracts/
│   └── api.md           ← Phase 1 output (new presets endpoints)
└── tasks.md             ← Phase 2 output (created by /speckit-tasks)
```

### Source Code (files modified or created by Phase 3)

```text
BACKEND (Python):
app/
├── api/
│   └── presets.py          CREATE — GET/POST/DELETE /api/presets; flat-file
│                                     JSON read/write/validate, no app/core/ module needed
├── config.py                MODIFY — add PRESETS_FILE = _APP_DIR / "presets.json"
└── main.py                  MODIFY — register presets_router

FRONTEND (JavaScript, no build step):
static/js/
├── session-state.js        MODIFY — replace single lastBulkOp slot with
│                                     undoStack: [] (capped array) + UNDO_STACK_CAP
├── theme.js                 CREATE — installTheme(), localStorage-backed,
│                                      injects toggle into #app-nav (mirrors
│                                      debug-log.js's buildUI() pattern)
├── app.js                   MODIFY — import + call installTheme()
└── pages/
    ├── timeline.js          MODIFY — bulkToggle()/undoBulk() use the stack;
    │                                  clearSelection() no longer clears undo history;
    │                                  updateBulkToolbar() reflects stack length
    └── export.js            MODIFY — loadCustomPresets(), "Save as Preset" control,
                                       per-preset delete affordance

CSS:
static/css/
└── base.css                MODIFY — add [data-theme="light"] override block;
                                      add .theme-toggle button styling

TESTS (Python):
tests/
└── test_api_presets.py     CREATE — create/list/duplicate-rejected (custom AND
                                      built-in names)/delete/404-on-missing,
                                      using tmp_path-monkeypatched PRESETS_FILE
```

**Structure Decision**: Single-project desktop app structure (unchanged from Phase
1/2) — no new top-level directories. The only new backend module
(`app/api/presets.py`) follows the existing flat `app/api/*.py` router pattern; no
new `app/core/` module since there is no domain logic here, only JSON
persistence — consistent with how `app/api/system.py` and `app/api/shell_bridge.py`
are sized and scoped.

---

## Complexity Tracking

No constitution violations. No entries required.

---

## Implementation Notes for Task Generation

### app/config.py addition

```python
PRESETS_FILE: Path = _APP_DIR / "presets.json"
```

### app/api/presets.py (new file, ~55 lines)

```python
"""
Custom export presets — user configuration, NOT job state.
Persisted to a flat JSON file under ~/.cctv_processor per the Principle I
exemption in constitution v1.1.0 (presets are reusable user config, unrelated
to any specific job).
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import PRESETS_FILE

router = APIRouter()

BUILTIN_PRESET_NAMES = {"Security Report", "Evidence Pack", "Quick Highlights"}


class PresetCreateRequest(BaseModel):
    name: str
    output_type: str = "merged"
    quality: str = "original"
    burn_in: bool = False
    label_filter: list[str] = []


def _load() -> list[dict]:
    if not PRESETS_FILE.exists():
        return []
    try:
        return json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []  # corrupt/missing file → empty, never crash the app


def _save(presets: list[dict]) -> None:
    PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PRESETS_FILE.write_text(json.dumps(presets, indent=2), encoding="utf-8")


@router.get("/presets")
async def list_presets():
    return JSONResponse(_load())


@router.post("/presets")
async def create_preset(req: PresetCreateRequest):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset name cannot be empty")
    if name in BUILTIN_PRESET_NAMES:
        raise HTTPException(status_code=400, detail=f"'{name}' is a built-in preset name")
    presets = _load()
    if any(p["name"] == name for p in presets):
        raise HTTPException(status_code=400, detail=f"Preset '{name}' already exists")
    new_preset = req.model_dump()
    new_preset["name"] = name
    presets.append(new_preset)
    _save(presets)
    return JSONResponse(new_preset)


@router.delete("/presets/{name}")
async def delete_preset(name: str):
    presets = _load()
    remaining = [p for p in presets if p["name"] != name]
    if len(remaining) == len(presets):
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    _save(remaining)
    return JSONResponse({"deleted": name})
```

Register in `app/main.py` exactly like the other five routers:
```python
from app.api.presets import router as presets_router
...
app.include_router(presets_router, prefix="/api")
```

### static/js/session-state.js change

```javascript
const _state = {
  labelFilter:     new Set(),
  scoreThreshold:  0.0,
  selectedIndices: new Set(),
  undoStack:       [],   // { indices, prevIncluded }[], newest at end, cap 20
};
export const UNDO_STACK_CAP = 20;
export const uiState = _state;
export function resetUiState() {
  _state.labelFilter     = new Set();
  _state.scoreThreshold  = 0.0;
  _state.selectedIndices = new Set();
  _state.undoStack       = [];
}
```

### static/js/pages/timeline.js changes

`bulkToggle(include)` — push instead of overwrite:
```javascript
uiState.undoStack.push({ indices, prevIncluded: indices.map(i => events[i].included) });
if (uiState.undoStack.length > UNDO_STACK_CAP) uiState.undoStack.shift();
```

`undoBulk()` — pop instead of read-then-null:
```javascript
async function undoBulk() {
  if (!uiState.undoStack.length) return;
  const { indices, prevIncluded } = uiState.undoStack.pop();
  // ...same trueIdx/falseIdx replay logic as Phase 2...
  updateBulkToolbar();
  renderFiltered();
}
```

`clearSelection()` — remove the line that nulls undo state; it must only clear
`uiState.selectedIndices`.

`updateBulkToolbar()` — `btn-undo.disabled = uiState.undoStack.length === 0;` plus
optionally render the count on the button label.

### static/js/theme.js (new file)

```javascript
const KEY = "cctv-theme";

export function installTheme() {
  const saved = localStorage.getItem(KEY) || "dark";
  applyTheme(saved);
  const navBar = document.getElementById("app-nav");
  if (!navBar) return;
  const toggle = document.createElement("button");
  toggle.className = "theme-toggle";
  toggle.textContent = saved === "light" ? "🌙" : "☀️";
  toggle.title = "Toggle theme";
  toggle.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    applyTheme(next);
    toggle.textContent = next === "light" ? "🌙" : "☀️";
  });
  navBar.appendChild(toggle);
}

function applyTheme(theme) {
  if (theme === "light") document.documentElement.dataset.theme = "light";
  else delete document.documentElement.dataset.theme;
  localStorage.setItem(KEY, theme);
}
```

Wired into `static/js/app.js` next to the existing `installDebugLog()` call.

### static/css/base.css addition

```css
:root[data-theme="light"], html[data-theme="light"] {
  --bg: #f5f6fa; --surface: #ffffff; --surface2: #ebedf3; --border: #d8dae3;
  --text: #1a1d27; --text-dim: #5b5f73;
  --accent: #4f8ef7; --success: #2eb872; --warning: #c97f0e; --danger: #d33c3c;
}
```
Label/badge colors are intentionally NOT overridden — they stay constant across
themes per spec FR-P3-010.

### static/js/pages/export.js changes

- `loadCustomPresets()` called from the existing `loadSummary().then(...)` chain:
  fetches `/api/presets`, renders one button per entry after the 3 built-ins, wired
  through the existing `setType`/`setQuality` helpers plus the existing
  `burnIn`/`labelFilter` closures
- "Save as Preset" control: captures current `selectedType`/`selectedQuality`/
  `burnIn`/`labelFilter`, prompts for a name, `POST /api/presets`, re-renders the
  custom preset row, surfaces the backend's 400 error message if rejected
- Per-custom-preset delete control → `DELETE /api/presets/{name}`, re-render
