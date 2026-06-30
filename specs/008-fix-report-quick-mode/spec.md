# Feature Specification: Phase 8 — Report Fix + Quick Mode UI

**Feature Branch**: `008-fix-report-quick-mode`  
**Created**: 2026-06-29  
**Status**: Draft  

## User Scenarios & Testing *(mandatory)*

### User Story 1 — AI Report Produces Visible Descriptions (Priority: P1)

A user runs motion detection on a CCTV video, then clicks "Generate Intelligence Report". They expect the report to contain AI-generated scene descriptions for each detected event. Currently all description fields are blank because Florence-2 inference times out silently before producing output.

**Why this priority**: P1 because this is the core broken feature — the AI report is the main deliverable of Phase 7 and it produces no AI content at all.

**Independent Test**: Upload any video, run detection, open the export page, generate the Intelligence Report. At least one event card in the HTML report must contain non-empty text in the caption/description field.

**Acceptance Scenarios**:

1. **Given** a video with at least one detected event, **When** the user generates the Intelligence Report, **Then** the report displays a non-empty AI-generated description for at least the first event within 90 seconds of starting the AI Analysis stage.
2. **Given** Florence-2 inference takes longer than the per-task timeout, **When** the timeout fires, **Then** the report still completes; per-event captions for timed-out events are blank, but the executive summary uses rule-based synthesis.
3. **Given** the AI Analysis SSE stage is in progress, **When** the user's browser disconnects from the SSE stream, **Then** report generation continues to completion without crashing and no error traceback appears in the terminal.

---

### User Story 2 — SSE Progress Stream Is Stable (Priority: P2)

A user generates an Intelligence Report. The 4-stage SSE progress bar (Thumbnails → AI Analysis → Writing Report → Generating PDF) should display accurate, stable progress without showing misleading 100% states or crashing.

**Why this priority**: P2 — the progress bar is the user's only feedback during a long operation; misleading progress erodes trust and causes re-clicks.

**Independent Test**: Generate an Intelligence Report with at least 2 events. Observe all 4 progress stages. Thumbnails must not show 100% before thumbnails are actually generated. No `socket.send() raised exception` in the terminal.

**Acceptance Scenarios**:

1. **Given** an Intelligence Report generation is started, **When** the Thumbnails stage begins, **Then** progress advances from 0% to 100% only after thumbnails are actually written to disk.
2. **Given** the browser SSE connection drops mid-generation, **When** the server tries to send a progress event, **Then** the exception is caught silently, report generation completes, and no unhandled exception traceback appears in the terminal.

---

### User Story 3 — Quick Report PDF Without AI Wait (Priority: P3)

A user wants a PDF of their motion events immediately, without waiting for Florence-2 AI analysis. The Export page shows two clearly labelled buttons side-by-side: "Quick Report (PDF)" (instant, rule-based) and the existing "Intelligence Report" (AI-enhanced, slow).

**Why this priority**: P3 — the core fix (US1/US2) must land first; this is additive UX improvement.

**Independent Test**: Go to the Export page. Confirm two report buttons exist side-by-side. Click "Quick Report (PDF)". A PDF is generated immediately (< 5 seconds) with no SSE wait, using the existing motion-only Incident Report template.

**Acceptance Scenarios**:

1. **Given** the user is on the Export page with detected events, **When** they click "Quick Report (PDF)", **Then** a motion-only PDF is triggered immediately without any AI analysis delay.
2. **Given** the user clicks "Quick Report (PDF)", **When** the PDF is generated, **Then** the report contains event thumbnails, timestamps, confidence scores, and heatmap — the same content as the existing Incident Report.
3. **Given** both buttons are visible, **When** the user reads the page, **Then** "Quick Report" shows "Instant · rule-based synthesis" and "Intelligence Report" shows "~5–20 min · Florence-2" as visible subtitles.

---

### Edge Cases

- What happens when Florence-2 times out on every single event? → Report must complete with rule-based executive summary (NarrativeSynthesizer); per-event captions are blank / "N/A" in the timeline — this is expected, not an error.
- What happens when the browser reconnects to the SSE stream after a disconnect? → The stream resumes from current session state; no duplicate events are emitted.
- What happens when there are zero included events? → Both report buttons are disabled (existing guard); no change needed.
- What happens when `annotated_thumb_b64` is an empty string? → The `<img>` tag must not render at all (no broken image icon).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The AI Analysis stage of the Intelligence Report MUST complete within 90 seconds per event (per-task daemon-thread timeout reduced to 90s, max tokens reduced to 64).
- **FR-002**: When Florence-2 inference times out for an event, the report MUST still generate to completion; per-event captions for timed-out events will be blank, and the executive summary continues to use rule-based synthesis (NarrativeSynthesizer) to produce a coherent overall summary.
- **FR-003**: The Thumbnails progress stage MUST reflect actual thumbnail-generation progress, not advance to 100% before `thumbnail_gen.run()` completes.
- **FR-004**: The SSE stream MUST handle client disconnects gracefully — a `socket.send()` failure MUST be caught without crashing or logging an unhandled exception traceback.
- **FR-005**: The Intelligence Report HTML MUST NOT render a broken `<img>` element when `annotated_thumb_b64` is an empty string.
- **FR-006**: The Export page MUST display a "Quick Report (PDF)" button in the Intelligence Report section alongside the existing "Generate Intelligence Report" button.
- **FR-007**: The "Quick Report (PDF)" button MUST trigger the same motion-only PDF as the existing Incident Report flow (rule-based, no Florence-2 call), completing within 5 seconds.
- **FR-008**: Both buttons MUST have visible subtitle text: "Quick Report" shows "Instant · rule-based synthesis"; "Intelligence Report" shows "~5–20 min · Florence-2".

### Key Entities

- **IntelligenceReport**: AI-enhanced report with Florence-2 captions per event, executive summary, SVG timeline, scene breakdown. Generated by `GET /api/job/intel-report.html` and `POST /api/job/intel-report/export`.
- **IncidentReport**: Motion-only PDF report using rule-based synthesis. Generated by existing `cctv:save-report-pdf` Qt event.
- **SSE Progress Stream**: Server-Sent Events channel on `/api/stream` that pushes `report_stage` and `report_done` events to the export page.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An Intelligence Report generated from a video with 5 or fewer events completes the AI Analysis stage in under 23 minutes worst case (90s × 3 tasks × 5 events = 1,350s), and typically under 11 minutes on real CCTV footage where EOS fires early (vs current 75+ minutes with the 300s timeout).
- **SC-002**: At least one event in a generated Intelligence Report has a non-empty AI caption when Florence-2 is installed and a real CCTV video is used (EOS fires before the 64-token limit on real frames).
- **SC-003**: The Thumbnails SSE stage shows 0% at start and advances to 100% only after thumbnail files are confirmed written.
- **SC-004**: Zero `socket.send() raised exception` tracebacks appear in the terminal during a normal Intelligence Report generation session.
- **SC-005**: A "Quick Report PDF" is generated and opened within 5 seconds of button click.
- **SC-006**: All 128 existing tests continue to pass after the changes.

---

## Assumptions

- Florence-2 is installed and the model weights are cached locally (offline use). The fix targets inference speed, not installation.
- Real CCTV frames trigger EOS well before the 64-token limit; synthetic all-black images are the worst case (~180s per task at 64 tokens).
- The Qt PDF bridge (`cctv:save-report-pdf` custom event) already works for the Incident Report. The "Quick Report" button reuses this exact mechanism.
- No new backend API endpoints are needed for the Quick Report — it uses the existing Qt bridge.
- The SSE stream uses FastAPI's `StreamingResponse` or `EventSourceResponse`; the exact wrapper determines where the try/except goes.
- `thumbnail_gen.run()` is a synchronous blocking call; a simple post-call progress update is sufficient.
- The `annotated_thumb_b64` empty-string case only occurs when PIL is completely absent (extremely rare in practice) — the fix is a low-cost Jinja2 guard.
