# Implementation Plan: Phase 4 — ROI Selection, Stop Application, New Project

**Branch**: `004-roi-app-controls` | **Date**: 2026-06-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-roi-app-controls/spec.md`

## Summary

Three independent, additive user stories. ROI selection adds one new backend
endpoint (`GET /api/job/preview-frame`) and a new frontend polygon-drawing canvas
wired into the Home page — no changes to `detection_engine.py` at all, since its
`_build_zone_mask()` helper and `StartJobRequest.zones` field already exist and
are already wired into the detection loop, just never fed by the frontend. Stop
Application refactors `launcher.py`'s uvicorn startup to a stoppable `Server`
object and extends the existing Qt JS-bridge-flag-polling mechanism (no new
backend HTTP surface, keeping `app/` PyQt-free). New Project is a one-line
backend race-condition fix plus a new nav-bar button that generalizes the
existing discard-confirmation pattern already used on the Home page.

## Technical Context

**Language/Version**: Python 3.11+ (backend), vanilla ES modules (frontend, no
build step, no npm)
**Primary Dependencies**: FastAPI, uvicorn, OpenCV (`cv2`), PyQt6 + QtWebEngine,
ffmpeg (via `imageio-ffmpeg`/`app/utils/ffmpeg_path.py`)
**Storage**: N/A — all three stories are in-memory/session-scoped or pure
UI/process-control; no new persisted state
**Testing**: pytest (backend, `tests/` mirrors `app/`); manual live-driving via
temporary scripts launching the real `MainWindow` (frontend/Qt — no JS test
runner in this stack, per constitution Principle III's frontend exemption)
**Target Platform**: Windows/macOS/Linux desktop (PyQt6 + QWebEngineView shell
wrapping a local FastAPI server)
**Project Type**: Desktop app (single-process, two-thread: Qt main thread + a
daemon-thread FastAPI/uvicorn server)
**Performance Goals**: Stop Application confirmed-dead within 15s of
confirmation (SC-P4-003); New Project round-trip under 5s (SC-P4-004); ROI
preview-frame extraction on the order of the existing ffprobe call (sub-second
for typical CCTV clips)
**Constraints**: No PyQt imports inside `app/` (backend stays headless-testable
via `TestClient`, per existing architecture); ROI coordinates must round-trip
through the existing normalized `[0,1]` `zones` schema with zero
`detection_engine.py` changes
**Scale/Scope**: Single user, single job at a time (unchanged from Phases 1-3);
no cap on regions drawn per job (consistent with Phase 3's uncapped custom-preset
precedent) — left as a UI/UX concern, not a spec requirement

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

1. **Principle I (Session-First, No Persistence)**: No new persisted storage.
   ROI regions live only in frontend JS state for the lifetime of the current
   job (never saved to disk, never reused across videos — per the spec's
   explicit per-job-only requirement, FR-P4-005); on the backend they pass
   through as part of the existing in-memory `settings` dict, identical in kind
   to `mode`/`sensitivity`/`padding_s` already there. Stop Application and New
   Project touch zero persisted state. **PASS — no exemption needed.**
2. **Principle II (Cross-Platform by Default)**: The new preview-frame endpoint
   uses `get_ffmpeg()` from `app/utils/ffmpeg_path.py` (never a bare `"ffmpeg"`
   string), and `_job_dir(job_id)` (already `pathlib.Path`-based). No new
   hardcoded paths anywhere in this plan. **PASS.**
3. **Principle III (Test-First)**: `GET /api/job/preview-frame` and the
   `create_job()` one-line cancel-guard fix are new `app/api/job.py` logic —
   tests MUST be written first, no exception. `launcher.py` and
   `shell/main_window.py` changes (Stop Application) touch no file under
   `app/` — same already-untested Qt/process-orchestration category as the
   rest of `shell/`, not subject to this principle. All `static/js/*` changes
   fall under the existing frontend exemption — verified via quickstart.md
   scenarios with a temporary live-driving script, not pytest. **PASS.**
4. **Principle IV (Callback-Driven Processing)**: `detection_engine.run()`'s
   signature and its `on_progress`/`on_event` callbacks are completely
   untouched — ROI regions ride through the pre-existing `zones` field with **zero
   changes to the engine itself**. **PASS.**
5. **Principle V (Simplicity & YAGNI)**: No new abstraction layers. ROI reuses
   the backend's existing (already-built, currently-dead) zone-mask code path
   instead of adding a parallel one. Stop Application reuses the existing
   JS-flag-polling bridge instead of adding a new IPC mechanism or a new HTTP
   endpoint. New Project reuses the existing `job/cancel` endpoint and
   `resetUiState()` instead of inventing new reset machinery. **PASS.**

**No constitution amendment required for this phase.**

## Project Structure

### Documentation (this feature)

```text
specs/004-roi-app-controls/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
app/
├── api/
│   └── job.py            # MODIFY: + GET /api/job/preview-frame, + one-line
│                          #   _cancel_event.set() guard in create_job()
└── core/
    └── detection_engine.py  # UNCHANGED — zone-mask logic already exists

launcher.py                # MODIFY: uvicorn.run() → Config+Server, + stop_backend()
shell/
└── main_window.py         # MODIFY: + on_stop_backend param, + shutdown bridge flag

static/
├── index.html              # MODIFY: link new roi.css
├── js/
│   ├── app.js               # MODIFY: + installStopButton(), + installNewProjectButton()
│   ├── roi.js                # CREATE: polygon-drawing canvas editor
│   ├── stop-app.js           # CREATE: Stop Application nav button + flow
│   ├── new-project.js        # CREATE: New Project nav button + flow
│   └── pages/
│       └── home.js           # MODIFY: mount ROI editor, wire zones into job/start
└── css/
    └── roi.css                # CREATE: ROI editor styling

tests/
└── test_api_job.py          # MODIFY: + preview-frame tests, + cancel-guard regression test
```

**Structure Decision**: No new top-level directories. ROI's backend half lives
in the existing `app/api/job.py` (alongside the other job-lifecycle endpoints,
matching how `StartJobRequest` already lives there) rather than a new file,
since it's a single small endpoint, not a new subsystem. All three stories'
frontend halves are new single-purpose files under `static/js/`, mirroring the
exact pattern Phase 3 established with `theme.js` (one file per nav-bar
feature, each exporting one `installX()` entry point called from `app.js`).

## Complexity Tracking

*No constitution violations — table not needed.*
