# Phase 0 Research: ROI Selection, Stop Application, New Project

## 1. ROI masking — reuse vs. new detection logic

**Decision**: Reuse `app/core/detection_engine.py:37-49`'s existing
`_build_zone_mask(zones: list)` and `StartJobRequest.zones` (`app/api/job.py:38`)
verbatim. Zero changes to `detection_engine.py`.

**Rationale**: Direct code reading confirmed `_build_zone_mask` already takes
normalized `[0-1]` `{"points": [[x,y], ...]}` polygon dicts, builds a
`cv2.fillPoly` mask at `DETECT_WIDTH x DETECT_HEIGHT`, and is already
bitwise-ANDed with the foreground mask in the main detection loop (lines
~268, ~324-325). `settings = req.model_dump()` (`job.py:123`) already passes
`zones` straight through to `detector.run(settings=...)`. This was built
proactively in a prior phase and never wired to a UI — the only gap is
producing the right shape from the frontend.

**Alternatives considered**: A parallel, frontend-only "clip to bounding box"
approach using CSS clipping was rejected — it wouldn't restrict what the
detector itself analyzes, only what's displayed, which doesn't satisfy
FR-P4-004 (no false positives are actually suppressed). Adding a new
backend masking code path was rejected as needless duplication of working
code (Principle V).

## 2. Pre-detection frame preview

**Decision**: New `GET /api/job/preview-frame` endpoint, extracting one JPEG
via the same ffmpeg subprocess pattern `app/core/thumbnail_gen.py:37-47`
already uses for post-detection thumbnails (`-ss <timestamp> -i <path>
-frames:v 1 -q:v 5 -y <out>`), extracting at native resolution (no `-vf
scale=...`) and caching to `_job_dir(job_id)/preview_frame.jpg`.

**Rationale**: No pre-detection preview mechanism exists today (Home page
shows only ffprobe metadata). The thumbnail-generation pattern is proven,
already imports `get_ffmpeg()` correctly (Principle II), and caching by
`job_id` (a fresh UUID per job) means no cross-job staleness is possible.
Native resolution avoids forcing a particular display size — ROI coordinates
are normalized `[0,1]` so the preview's actual pixel dimensions don't matter,
only its aspect ratio matching what `cv2.VideoCapture` decodes during
detection.

**Alternatives considered**: Extracting at `DETECT_WIDTH x DETECT_HEIGHT` (the
detector's own working resolution) was considered, to make preview and
detection frames pixel-identical, but rejected as unnecessary — normalized
coordinates already make this a non-issue, and native resolution gives the
user a sharper preview to draw against. Extracting client-side via the
`<video>` element's first frame (canvas `drawImage` from a hidden `<video>`)
was rejected because `QWebEngineView`'s bundled Chromium lacks H.264/AAC
decode support for many CCTV source codecs (the same codec gap documented in
this project's preview-clip work) — ffmpeg server-side extraction has no such
limitation.

## 3. Polygon-drawing UI

**Decision**: A `<canvas>` absolutely positioned over an `<img>`, following
this project's only existing 2D-rendering precedent
(`static/js/pages/timeline.js:252-277`'s canvas usage, even though that's a 1D
timeline bar) rather than introducing SVG.

**Rationale**: Canvas keeps the implementation in the same rendering paradigm
already used elsewhere in this codebase, with no new DOM-manipulation pattern
to learn. Vertex placement, polygon closing (click within ~10px of the first
point), and redraw are all straightforward `CanvasRenderingContext2D` calls.

**Alternatives considered**: SVG `<polygon>` + per-vertex `<circle>` elements
would make vertex dragging easier (native hit-testing via DOM events instead
of manual distance math) but was rejected as introducing a second rendering
paradigm into a codebase that has exactly one today — not justified for a
single feature (Principle V).

## 4. Stopping the backend gracefully

**Decision**: Refactor `launcher.py:58-65`'s `uvicorn.run()` convenience call
to the lower-level `uvicorn.Config` + `uvicorn.Server` pattern, storing the
`Server` instance at module level and calling `server.should_exit = True` to
trigger uvicorn's own documented graceful-shutdown path.

**Rationale**: `uvicorn.run()` gives no handle to stop the server it starts.
`should_exit` is uvicorn's standard, documented mechanism for exactly this —
checked once per loop iteration in `Server.serve()`. No process-killing,
signal-sending, or `os._exit()` needed.

**Alternatives considered**: Sending `SIGTERM`/`SIGINT` to the current process
was rejected — that would also tear down the Qt event loop and close the
window immediately, which conflicts with the spec's explicit requirement
(FR-P4-009) that the window stay open afterward showing a confirmation
message. Running uvicorn in a separate OS process (instead of a thread) so it
could be killed independently was rejected as a much larger architecture
change for no added benefit — `should_exit` solves this within the existing
single-process, two-thread design.

## 5. Triggering the stop from the web UI

**Decision**: Extend the existing JS-flag-polling bridge
(`shell/main_window.py:94-120`'s `_handle_browse_flags`, already polling
`window._cctvBrowse` every 200ms on the Qt main thread) with a third flag,
`window._cctvShutdown`, rather than adding a new backend HTTP endpoint.

**Rationale**: `app/main.py:78-111`'s `create_app()` has zero PyQt imports by
design — the backend is unit-testable headless via `TestClient`. A new HTTP
endpoint that calls into Qt (e.g. `QApplication.quit()`) would need to import
PyQt6 somewhere reachable from `app/`, breaking that boundary. The existing
bridge mechanism already solves "JS wants to trigger a Qt-side action" for
file browsing, runs on the Qt main thread (no cross-thread Qt-safety
concerns), and needs no new infrastructure — just one more polled boolean.

**Alternatives considered**: A new `POST /api/shell/shutdown` endpoint
(matching `app/api/shell_bridge.py`'s existing style) was considered since
that file already brokers PyQt6 ↔ FastAPI IPC, but it only brokers it in the
*other* direction (Qt calling into the backend via `session.update`, not the
backend reaching back into Qt) — making it call `QApplication.quit()` would
still require a PyQt import somewhere under `app/`. Rejected in favor of the
zero-new-import bridge-flag approach.

## 6. New Project — confirming the real gap

**Decision**: A one-line fix (`_cancel_event.set()` added before
`session.reset()` in `create_job()`, `app/api/job.py:83`) plus a new,
page-independent nav-bar button — no new backend "reset" endpoint.

**Rationale**: Direct code reading confirmed `session.reset()` is *already*
called on every `job/create` (`app/api/job.py:83`), and the frontend already
resets UI state on a successful load (`home.js:204`'s `resetUiState()`) with
an existing discard-warning modal for completed-but-unexported jobs
(`home.js:152-181`). The only real correctness gap is a race: if a detection
thread is still running (status `"detecting"`) when a new file loads, that
orphaned thread can keep calling `session.append_event` into the
freshly-reset session. Setting `_cancel_event` first closes this, reusing the
same event `detection_engine.py`'s loop already checks
(`if cancel_event.is_set(): break`). The remaining gap is pure discoverability
— there's no way to trigger this from Timeline/Export/Processing without
first navigating to Home.

**Alternatives considered**: A dedicated `POST /api/job/reset` endpoint was
considered for symmetry with "New Project" as a named action, but rejected —
it would duplicate logic that `job/cancel` (already exists) plus the existing
`job/create` reset path already provide together; adding a third overlapping
endpoint violates Principle V for no behavioral gain.
