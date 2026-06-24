# Implementation Plan: Phase 5 — Professional Reporting & Activity Insights

**Branch**: `005-reporting-and-heatmap` | **Date**: 2026-06-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-reporting-and-heatmap/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Three features that all derive from data the app already produces: (1) an
activity heatmap accumulated during detection (both MOG2 and YOLO modes) and
shown as an optional overlay on the ROI-drawing screen; (2) a one-click
PDF/HTML incident report (summary, heatmap, per-event thumbnail grid,
chain-of-custody SHA-256 hashes) rendered via Qt's own bundled Chromium
(`QWebEnginePage.printToPdf`) — zero new pip dependencies for PDF generation;
(3) one-click CSV/JSON event-log exports, pure backend, no Qt involvement.
The full technical design (exact code, function signatures, and independently
verified Qt-API feasibility) was already produced and approved in a prior
planning pass — see `C:\Users\User\.claude\plans\lazy-dazzling-rabbit.md` —
this plan formalizes that design into the project's standard artifacts.

## Technical Context

**Language/Version**: Python 3.11+ (backend, `app/`, `shell/`); vanilla JavaScript ES modules, no build step (frontend, `static/js/`)
**Primary Dependencies**: FastAPI 0.111.0, OpenCV (`opencv-python-headless` 4.9.0.80), NumPy 1.26.4, PyQt6 6.7.0 + PyQt6-WebEngine 6.7.0, Jinja2 3.1.6 (newly pinned explicitly — already installed transitively), `imageio-ffmpeg` 0.5.1 (bundled FFmpeg)
**Storage**: N/A — no database, no new persisted state. New artifacts (`heatmap.png`, `thumbnails/*.jpg`, the rendered report HTML) are job-scoped derived files under the existing `_job_dir(job_id)`, the same category as Phase 4's `preview_frame.jpg`; PDF/CSV/JSON outputs are written to the user's already-chosen `output_dir`, the same category as the existing video export
**Testing**: pytest (`tests/`, `TestClient`-based) for all `app/core/*.py`/`app/api/*.py` changes; temporary driving scripts (deleted after use) for `shell/main_window.py`'s Qt-only code and all `static/js/` changes, per this project's established pattern (no Qt/JS test harness exists)
**Target Platform**: Windows 10/11 desktop (primary target); engines remain platform-agnostic per Principle II
**Project Type**: Desktop app — FastAPI backend + PyQt6/QWebEngineView shell + vanilla-JS SPA (existing structure, no new top-level project)
**Performance Goals**: Full report generation in under 10s for a job with 50 included events or fewer (SC-P5-001; not guaranteed beyond that count, but expected to scale proportionally rather than fail or hang); heatmap accumulation adds negligible per-frame overhead next to MOG2/YOLO inference itself
**Constraints**: Zero new heavyweight dependencies — PDF rendering reuses Qt's already-bundled Chromium (`printToPdf`) rather than adding `reportlab`/`weasyprint`; SHA-256 hashing of multi-GB source videos must use chunked reads, never load a full file into memory; no new user-facing settings/toggles (heatmap is always computed, per YAGNI)
**Scale/Scope**: Single active job at a time (existing architecture, unchanged); SC-P5-001's performance target is defined for jobs with 50 included events or fewer; source videos can be multi-GB, driving the chunked-hash requirement above

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Check | Result |
|---|---|---|---|
| 1 | I. Session-First, No Persistence | Does this introduce persistent storage? | **Pass, no exemption needed.** `heatmap.png`/`thumbnails/*.jpg`/report HTML are job-scoped derived files under `_job_dir(job_id)` — same category Phase 4's `preview_frame.jpg` already established as compliant (vanishes with the job, never read back into `session.py`). CSV/JSON/PDF write to the user's chosen `output_dir`, same category as the existing video export. No new field is added to `session.py`'s `_DEFAULTS`. |
| 2 | II. Cross-Platform by Default | All paths via `pathlib.Path`? FFmpeg via the utility? | **Pass.** `thumbnail_gen.py` (being wired in, not modified) already uses `get_ffmpeg()`. All new code uses `Path` throughout (`_job_dir`, `output_dir` resolution mirrors `export_engine.py`'s existing pattern exactly). |
| 3 | III. Test-First (NON-NEGOTIABLE) | Failing test before implementation, for `app/core`/`app/api`? | **Pass, full TDD for all backend logic** (heatmap accumulation in both engines, `event_index` fix, `_sha256_file`, all four new `job.py` endpoints, new `tests/test_thumbnail_gen.py`). `shell/main_window.py`'s hidden-`QWebEnginePage` code and all `static/js/` changes follow the **established precedent** from Phase 1 and Phase 4 (Stop Application) — verified via a temporary driving script per `quickstart.md`, not pytest, since no Qt/JS test harness exists in this project. This is consistent application of existing practice, not a new exception. |
| 4 | IV. Callback-Driven Processing | Do engines receive callbacks rather than touching session directly? | **Pass.** Heatmap accumulation is a local `np.ndarray` inside each engine's `run()`, written to `job_dir` as a side effect at the end of the function — never passed through `on_event`/`on_progress`, never imports `app.session`. No signature change to `run()`. |
| 5 | V. Simplicity & YAGNI | Simplest implementation that satisfies the requirement? | **Pass.** No new settings toggle for the heatmap (always computed — the per-frame cost is negligible). `yolo_detector.py` reuses `detection_engine._write_heatmap` rather than duplicating colormap/resize logic. Two dedicated CSV/JSON endpoints (not one overloaded `?format=` endpoint), matching this codebase's existing single-purpose-endpoint convention. |

**No violations — Complexity Tracking table is not needed.**

## Project Structure

### Documentation (this feature)

```text
specs/005-reporting-and-heatmap/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── api.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

This feature extends the existing desktop-app structure (FastAPI backend +
PyQt6 shell + vanilla-JS SPA) — no new top-level project, no new directory
category beyond two small additions inside `app/`:

```text
app/
├── api/
│   └── job.py                  # +4 endpoints: heatmap, report.html, export/csv, export/json
│                                #  + _sha256_file, _b64_file helpers
├── core/
│   ├── detection_engine.py      # + heatmap accumulation, _write_heatmap()
│   ├── yolo_detector.py         # + heatmap accumulation (bbox-fill), event_index fix
│   ├── thumbnail_gen.py         # wired in (unmodified) — was dead code
│   └── report_renderer.py       # NEW — render(context) -> str, Jinja2 templating
└── templates/                   # NEW directory
    └── report.html              # NEW — standalone Jinja2 report template

shell/
└── main_window.py               # + hidden QWebEnginePage / printToPdf flow, new JS flag

static/
├── js/
│   ├── roi.js                   # + setHeatmapSrc(), heatmap overlay layer
│   ├── pages/
│   │   ├── home.js              # + loadRoiPreview() calls setHeatmapSrc()
│   │   └── export.js            # + Generate PDF Report / Event Log CSV / Event Log JSON buttons
└── css/
    └── roi.css                  # + .roi-editor__heatmap layer styles

tests/
├── test_detection_engine.py     # + heatmap tests
├── test_yolo_detector.py        # + heatmap + event_index regression tests
├── test_api_job.py              # + endpoint tests for all 4 new routes + hashing helper
└── test_thumbnail_gen.py        # NEW — closes a pre-existing test gap

requirements.txt                  # + Jinja2==3.1.6 (pinned; already installed transitively)
```

**Structure Decision**: Reuse the existing three-layer structure
(`app/`/`shell/`/`static/`) exactly as established in Phases 1-4. The only
new directories are `app/templates/` (Jinja2 templates, a natural sibling to
`app/core/`'s engines) and the new `app/core/report_renderer.py` module
(keeps `app/api/job.py` a thin endpoint layer that delegates, consistent
with how it already delegates to `export_engine.run()` rather than inlining
FFmpeg logic).

## Complexity Tracking

*Not applicable — the Constitution Check above recorded zero violations.*
