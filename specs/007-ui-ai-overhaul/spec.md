# Feature Specification: UI/UX Overhaul & Enhanced AI Analysis

**Feature Branch**: `007-ui-ai-overhaul`
**Created**: 2026-06-26
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Rich AI Frame Analysis with Florence-2 (Priority: P1)

A security analyst runs detection on a car park video and then generates an intelligence report. Instead of seeing generic captions like "a security camera showing a person", every event in the report now contains a full descriptive paragraph ("Two individuals are walking briskly toward the entrance. The person on the left is wearing a dark hoodie and carrying a backpack.") plus a crop-level description of the detected object. The report also stores machine-readable per-frame data for later chatbot use.

**Why this priority**: This is the primary pain point — the AI descriptions are currently so generic they add no value. Everything else in the report depends on having quality descriptions.

**Independent Test**: Install the AI description library, run detection on any video, generate the intelligence report, and verify that the timeline table contains descriptive multi-sentence entries different from each other and containing specific visual details.

**Acceptance Scenarios**:

1. **Given** a completed detection run with included events, **When** the user generates an intelligence report, **Then** each event's description is a unique, multi-sentence paragraph describing specific visual details visible in the thumbnail
2. **Given** a YOLO detection run, **When** the user generates an intelligence report, **Then** each event additionally contains a crop-level description specific to the detected object (person, car, etc.)
3. **Given** the AI library is not installed, **When** the user generates an intelligence report, **Then** the report generates successfully with empty descriptions and a clear notice that AI analysis is unavailable
4. **Given** the semantic indexing library is installed, **When** an intelligence report is generated, **Then** a small sidecar file is written next to each thumbnail for future chatbot use, without affecting report output or generation time visibly

---

### User Story 2 — Comprehensive Intelligence Report with User Control (Priority: P1)

Before generating the report, the user is shown a dialog where they choose their output format (Markdown file, PDF, or both). While the report generates, they see a clear multi-stage progress display showing exactly which stage is running and how far along it is (e.g. "Analysing frame 8 of 12 — 00:01:23"). The final report contains a visual activity timeline, a Scene Breakdown section with full paragraphs per top event, and — if an API key is configured — an analyst-quality executive summary written by an AI language model.

**Why this priority**: The report is the main deliverable of this feature set. The format choice, progress visibility, and report quality directly determine whether the tool is useful to someone who didn't watch the video.

**Independent Test**: Run detection, click "Generate Intelligence Report", verify the format modal appears, select Markdown-only, verify no PDF is created, verify the progress display shows all four stages updating, and verify the resulting Markdown contains the Scene Breakdown section.

**Acceptance Scenarios**:

1. **Given** a completed detection run, **When** the user clicks "Generate Intelligence Report", **Then** a format selection dialog appears before any generation begins
2. **Given** the format dialog is open, **When** the user selects "Markdown only" and clicks Generate, **Then** only a Markdown file is created — no PDF is generated
3. **Given** the format dialog is open, **When** the user selects "PDF only" and clicks Generate, **Then** only a PDF is created — no Markdown file is written
4. **Given** report generation is in progress, **When** the user watches the progress area, **Then** four named stages update in sequence (Thumbnails, AI Analysis, Markdown, PDF) each with a count or completion indicator
5. **Given** a completed detection run with 10+ events, **When** the user opens the generated report, **Then** the report contains a Scene Breakdown section with at least 3 top events described in full paragraphs with annotated thumbnails
6. **Given** an LLM API key is configured, **When** the user generates the report, **Then** the executive summary reads as a natural prose paragraph describing the video's content rather than a template sentence
7. **Given** no LLM API key is configured, **When** the user generates the report, **Then** the executive summary is generated from detection data using rule-based logic with trend and temporal analysis — no error occurs
8. **Given** the user previously chose "PDF only", **When** they open the format dialog again, **Then** the previous choice is pre-selected

---

### User Story 3 — Polished Progress & Log Visibility (Priority: P2)

During detection, the user can reveal a log panel that shows timestamped, colour-coded messages organised by stage (Starting, Detecting, Event Found, Complete). On the Export page, the summary strip tells the user upfront whether AI analysis is available. The debug drawer (accessible on all pages) is cleaner, with timing information on network calls and clear error highlighting.

**Why this priority**: This is quality-of-life polish that makes the app feel professional and trustworthy, but doesn't block core functionality.

**Independent Test**: Run detection, click "Show Logs", verify timestamped colour-coded log lines are visible, click "Copy", verify clipboard contains log text.

**Acceptance Scenarios**:

1. **Given** detection is running, **When** the user clicks "Show Logs", **Then** a log panel appears showing timestamped entries with colour-coded severity (info/event/warning/error)
2. **Given** the log panel is open, **When** a new detection stage begins, **Then** a visual separator heading appears in the log before the new stage's entries
3. **Given** the log panel is open and has entries, **When** the user clicks "Copy", **Then** all log text is copied to the clipboard
4. **Given** a completed detection run, **When** the user navigates to the Export page, **Then** the summary strip shows a badge indicating whether AI frame analysis is available
5. **Given** the debug drawer is open, **When** a network request completes, **Then** the entry shows the URL, response status, and duration in milliseconds

---

### Edge Cases

- What happens when the AI model is being downloaded for the first time during report generation? → Report generation should block, and the progress display should show "Downloading AI model (first time)…" rather than a frozen stage.
- What happens when fewer than 5 events exist for the Scene Breakdown section? → The Scene Breakdown shows all available events (minimum 1).
- What happens when a thumbnail file is missing at report generation time? → That event's description is empty; other events are unaffected; report generates without error.
- What happens when the user closes the format dialog without selecting? → No generation occurs; the button returns to its enabled state.
- What happens when PDF generation fails (Qt bridge unavailable)? → If Markdown was also requested, it is still written successfully; a warning is shown about PDF failure.

## Requirements *(mandatory)*

### Functional Requirements

**AI Frame Analysis**
- **FR-001**: The system MUST replace the current single-caption AI analysis with a multi-task analysis pipeline that produces a detailed description, an object-specific crop description (where applicable), and structured object detection data per event
- **FR-002**: The system MUST remove the 200-character truncation limit on AI-generated descriptions
- **FR-003**: The system MUST store a compact semantic embedding alongside each event thumbnail when the indexing library is available, without blocking report generation if unavailable
- **FR-004**: The system MUST fall back gracefully to empty descriptions when the AI analysis library is not installed, without errors or degraded report structure

**Intelligence Report**
- **FR-005**: The system MUST present a format selection dialog to the user before any report generation begins
- **FR-006**: The format dialog MUST offer three choices: Markdown only, PDF only, or both Markdown and PDF
- **FR-007**: The system MUST persist the user's last format choice and pre-select it on subsequent opens
- **FR-008**: The system MUST stream named stage progress during report generation: Thumbnails, AI Analysis, Writing Report, Generating PDF
- **FR-009**: The AI Analysis stage progress MUST display the current frame number, total frames, and that event's timestamp in the source video
- **FR-010**: The intelligence report MUST include a Scene Breakdown section presenting the top 5 highest-confidence events as individual cards with full descriptive paragraphs and annotated thumbnails
- **FR-011**: The intelligence report MUST include a visual activity timeline showing when events occurred across the video duration
- **FR-012**: The executive summary MUST incorporate temporal activity distribution (early/middle/late video thirds) and activity trend direction (rising/falling/sporadic/uniform)
- **FR-013**: When an LLM API key is available, the executive summary MUST be generated by the language model using the full event list as context; when unavailable, rule-based synthesis MUST be used with no error
- **FR-014**: Selecting "Markdown only" MUST result in no PDF file being created; selecting "PDF only" MUST result in no Markdown file being written

**UI Polish**
- **FR-015**: The Processing page log panel MUST be togglable (hidden by default) via a clearly labelled button
- **FR-016**: Each log entry MUST display a timestamp and a severity indicator; entries MUST be visually distinguishable by severity (informational, event detected, warning, error)
- **FR-017**: Log entries MUST be grouped under stage separator headings that appear when a new processing stage begins
- **FR-018**: The log panel MUST provide a button to copy all visible log entries to the clipboard
- **FR-019**: The Export page summary strip MUST display a badge showing whether AI frame analysis is currently available
- **FR-020**: The debug drawer MUST display response status and duration for each network request entry

### Key Entities

- **FrameAnalysis**: The structured output for one event thumbnail — contains full caption, object-specific caption, list of detected objects with bounding boxes, and path to optional semantic embedding file
- **ReportFormat**: User's choice of output formats for a single report generation — one or both of Markdown and PDF
- **ReportStageEvent**: A progress event streamed during report generation — contains stage name, current count, total count, and optional video timestamp
- **ActivityTimeline**: A visual representation of event density across the full video duration used within the report
- **SceneBreakdownEntry**: A single entry in the Scene Breakdown section — contains event timestamp, full AI description, crop description, and annotated thumbnail

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: AI-generated event descriptions contain at least 2 sentences and include at least one specific visual detail (clothing, action, object) — verified on a real detection run with a real video
- **SC-002**: Users can select their preferred report output format before generation begins — 100% of report generation attempts show the format dialog first
- **SC-003**: All four report generation stages are visually represented with progress indicators — users can see current stage and frame count without checking any other UI element
- **SC-004**: The Scene Breakdown section is present in every generated report with at least 1 entry — regardless of event count
- **SC-005**: Reports generated without AI analysis installed produce valid, complete documents — 0 errors, all structural sections present
- **SC-006**: The log panel on the Processing page displays entries with timestamps and colour-coded severity when revealed — verified by running detection and toggling the panel
- **SC-007**: Format choice persists across browser sessions — reopening the format dialog pre-selects the last chosen option

## Assumptions

- The AI frame analysis library (`transformers`) is already installed from Phase 6; only model weights change (BLIP → Florence-2)
- The semantic embedding library (`open-clip-torch`) is a new optional dependency — the system works fully without it
- The LLM API key is provided as an environment variable, not through the app UI — no key management UI is needed in this phase
- The existing SSE stream endpoint and event format are extended, not replaced — existing progress consumers continue to work without changes
- The PyQt6 PDF printing bridge from Phase 6 is reused unchanged — only the triggering logic changes based on user's format choice
- All new `app/core/` modules require TDD: failing tests must be written before implementation code
- The BLIP model cache can be safely removed from disk after Florence-2 is downloaded — the user should do this manually to reclaim ~900 MB
- The debug drawer toggle button and ring buffer from Phase 6 are preserved; only formatting is changed
