# Feature Specification: Video Intelligence Export

**Feature Branch**: `006-video-intel-export`  
**Created**: 2026-06-25  
**Status**: Draft  

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Generate Intelligence Report (Priority: P1)

After running detection on a video, the user wants a single-click way to produce a
comprehensive document describing what happened — readable by anyone who was not present
during the review session. The report is exported as both a human-readable PDF and a
structured Markdown file, both saved to the user's output folder automatically.

The report covers: an executive summary, activity statistics (total events, active time
percentage, busiest period), an object inventory (YOLO: counts per class), a full
chronological timeline with timestamps and confidence scores, the top-3 "key moments",
the activity heatmap visualisation, the detection settings, and a machine-readable JSON
data appendix containing every included event.

**Why this priority**: Without this story nothing is exported at all. It delivers
standalone value even without vision descriptions and is the foundation for US2 and US3.

**Independent Test**: After a completed detection run, clicking "Generate Intelligence
Report" produces two files in the output folder. The user can open either file and
identify: when the first event occurred, how many events were detected, and whether the
activity heatmap section is present.

**Acceptance Scenarios**:

1. **Given** a completed detection run with ≥1 included event, **When** the user clicks
   "Generate Intelligence Report", **Then** a Markdown file and a PDF file appear in the
   configured output folder within 2 minutes (excluding first-run model download).

2. **Given** a completed YOLO-mode run, **When** the report is generated, **Then** the
   report contains an "Object Inventory" section listing each detected object class with
   its count and first/last appearance time.

3. **Given** a completed MOG2-mode run, **When** the report is generated, **Then** the
   report contains an "Activity Statistics" section with total event count, active
   duration, and the proportion of video time that was active.

4. **Given** a run where the user has toggled some events as "excluded", **When** the
   report is generated, **Then** only "included" events appear in every section —
   excluded events are completely absent.

5. **Given** zero included events, **When** the user attempts to generate a report,
   **Then** generation is refused with an informative message (no crash, no partial file).

6. **Given** detection is still in progress, **When** the user attempts to generate a
   report, **Then** generation is refused with an informative message.

---

### User Story 2 — Visual Frame Descriptions via Local Vision Model (Priority: P2)

When the user has installed the optional Moondream2 vision model, each event in the
report's timeline gains a natural language description of what the thumbnail shows —
for example "A person in dark clothing crossing from right to left in front of parked
vehicles." This makes the report useful for reviewers who were not involved in the
original detection run.

When the vision model is not installed, the report is still complete and valid — the
description column shows "N/A" and the frontend informs the user how to enable
visual descriptions.

On the very first report generation after installing the vision model, the model weights
(~2 GB) are downloaded automatically with a clear status message indicating this is a
one-time operation.

**Why this priority**: Visual descriptions significantly improve report quality but are
purely additive — the P1 story delivers a useful report without them.

**Independent Test**: With moondream installed and model cached: generate a report and
confirm every event in the timeline has a non-empty, human-readable description.
Without moondream: confirm the report generates cleanly, descriptions show "N/A",
and a frontend notice explains the optional install.

**Acceptance Scenarios**:

1. **Given** moondream is installed and the model is cached, **When** the report is
   generated for a run with 5 included events, **Then** the timeline table contains a
   non-empty description string for all 5 events.

2. **Given** moondream is NOT installed, **When** the report is generated, **Then**
   the report generates without error, all description cells show "N/A", and the export
   page shows "Install moondream to add visual descriptions."

3. **Given** moondream is installed but the model has never been downloaded, **When**
   the user generates a report, **Then** the status area shows "Downloading Moondream2
   model (~2 GB, one-time only)..." until the download completes, then proceeds normally.

4. **Given** a thumbnail is missing for one event, **When** vision descriptions are
   generated, **Then** that event shows "N/A" and generation continues for the rest
   without crashing.

---

### User Story 3 — Markdown Structured for AI Chatbot Context (Priority: P3)

The Markdown file produced in US1 is structured so that it can be loaded directly into
an LLM chatbot — either by pasting externally into Claude/ChatGPT, or automatically
by Phase 7's in-app chat feature — and the chatbot can accurately answer questions
about the video such as:

- "When was the first person detected?"
- "How many events involved vehicles?"
- "What was happening around 2:30 PM?"
- "Which event had the highest confidence score?"

This requires: timestamps in both elapsed-seconds and wall-clock formats, a
machine-parseable JSON data appendix, and a file size within typical LLM context limits.

**Why this priority**: US3 adds structural constraints on the Markdown format. Without
them the file works for human reading but may be ambiguous for LLM consumption. Phase 7
depends on these constraints being in place.

**Independent Test**: Load the Markdown as sole context in a chatbot session and ask
"When was the first event detected?" — chatbot answers correctly. Paste the JSON
appendix into a JSON validator — it passes without errors. Measure file size — under
100 KB.

**Acceptance Scenarios**:

1. **Given** a generated Markdown file, **When** its JSON appendix block is extracted
   and parsed, **Then** parsing succeeds and each object contains `event_index`,
   `start_s`, `start_clock`, `end_s`, `end_clock`, `peak_motion_score`, `zone_label`,
   `included`, and optionally `description`.

2. **Given** a generated Markdown file, **When** its file size is measured, **Then**
   the file is under 100 KB for any single video up to 60 minutes with up to 200
   included events.

3. **Given** a Markdown file used as chatbot context, **When** asked "When did the
   first event start?", **Then** the chatbot gives the correct time as shown in the
   file's timeline table.

---

### Edge Cases

- **Zero included events**: Generation refused with clear message; no partial file written.
- **Detection still running**: Generation refused; informative status shown.
- **No heatmap file** (run cancelled early): Heatmap section states "Heatmap not available for this run."
- **No thumbnail for an event**: That event's description shows "N/A"; generation continues.
- **Moondream first-run download** (~2 GB): Status message shown; endpoint blocks; subsequent runs reuse cached model.
- **All events excluded**: Treated as zero included events — generation refused.
- **Very long video** (60 min, 200+ events): Markdown stays under 100 KB; descriptions truncated if needed.
- **Output directory not set**: Falls back to user's Desktop (same as video export).

---

## Requirements *(mandatory)*

### Functional Requirements

**US1 — Intelligence Report Generation**

- **FR-P6-001**: The system MUST generate a report only when detection is NOT in progress. Any session status other than `"detecting"` is permitted (including `completed`, `cancelled`, `export_done`, `export_error`) — consistent with the existing CSV/JSON export behaviour.
- **FR-P6-002**: The report MUST include an executive summary in plain language, covering what was detected, when activity was highest, and the overall activity level.
- **FR-P6-003**: The report MUST include an activity statistics section: total included-event count, total active duration (seconds + percentage of video length), and the time range of peak activity. "Busiest period" is defined as the clock-formatted start and end times of the shortest continuous window that contains the highest number of included events, evaluated as a 60-second sliding window over the video timeline.
- **FR-P6-004**: When the detection mode is YOLO, the report MUST include an object inventory table: object class, count, first appearance time, last appearance time.
- **FR-P6-005**: The report MUST include a chronological timeline table with one row per included event: event number, start time (clock + seconds), end time, duration, label, confidence score, and description.
- **FR-P6-006**: The report MUST include a "Key Moments" section with the 3 highest-confidence included events (fewer if fewer exist), each with thumbnail (PDF: embedded image; Markdown: path) and description. Events are ranked by `peak_motion_score` descending; ties are broken by `event_index` ascending (earlier event wins).
- **FR-P6-007**: The report MUST include a heatmap section. If a heatmap file exists it MUST be embedded in the PDF and referenced in Markdown. If absent, the section MUST state "Heatmap not available for this run."
- **FR-P6-008**: The report MUST include a detection configuration section: mode, sensitivity, padding, minimum event duration, minimum gap, and configured zones.
- **FR-P6-009**: The Markdown version MUST include a JSON data appendix as a fenced code block containing all included events as a valid JSON array.
- **FR-P6-010**: The PDF version MUST embed all event thumbnails and the heatmap image directly (no external file references).
- **FR-P6-011**: The report MUST reflect only "included" events. Excluded events MUST NOT appear in any section.
- **FR-P6-012**: Both output files MUST be written to the configured output directory; Desktop is the fallback if no directory is set.
- **FR-P6-013**: Output filenames MUST follow the pattern `{source_stem}_intelligence_{YYYYMMDD_HHMMSS}.md` and `.pdf`.
- **FR-P6-014**: Report generation MUST be triggered by a single button on the Export page, with a status message showing progress or success.

**US2 — Visual Frame Descriptions**

- **FR-P6-015**: When the Moondream2 vision model is installed and cached, the system MUST generate a natural language description for the thumbnail of each included event.
- **FR-P6-016**: When the vision model is not installed, report generation MUST proceed normally; description fields MUST show "N/A" with no error surfaced to the user.
- **FR-P6-017**: When the vision model is installed but weights have never been downloaded, the system MUST download them automatically during the first report generation and MUST display a status message indicating this is a one-time operation.
- **FR-P6-018**: If generating a description for any single thumbnail fails, that event's description MUST default to "N/A" and generation MUST continue for all remaining events.
- **FR-P6-019**: When the vision model is not installed, the Export page MUST display an informational notice explaining how to enable visual descriptions.

**US3 — AI Chatbot Context Formatting**

- **FR-P6-020**: The Markdown file MUST include every event timestamp in both elapsed-seconds format and wall-clock format (or elapsed-only if no recording start time is set).
- **FR-P6-021**: The JSON data appendix MUST be valid JSON — parseable by a standard JSON library without modifications.
- **FR-P6-022**: Each event object in the JSON appendix MUST include an `event_index` integer matching the event's row in the timeline table.
- **FR-P6-023**: The generated Markdown file MUST be under 100 KB for any video up to 60 minutes with up to 200 included events. The file MUST be written with UTF-8 encoding. Event description strings in the timeline table MUST be truncated to at most 200 characters if they would cause the file to approach the 100 KB limit; descriptions in the JSON appendix are subject to the same 200-character cap.
- **FR-P6-024**: The output directory MUST be created automatically (including parent directories) if it does not already exist — consistent with the existing CSV/JSON export behaviour.

### Key Entities

- **Intelligence Report**: A structured document derived from a completed detection run. Exists in two forms (Markdown and PDF) with identical content. Scoped to one job and the current set of included events.
- **Event Description**: A natural language string describing the visual content of an event's thumbnail. Present when the vision model is available; "N/A" otherwise. Part of the report only — not stored back to the detection session.
- **JSON Data Appendix**: A machine-readable, embedded representation of all included events within the Markdown report, designed for AI chatbot consumption.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-P6-001**: A user who has not watched the source video can correctly identify the number of events, the time of the first event, and whether persons or vehicles were detected — using only the generated report — within 60 seconds of opening it.
- **SC-P6-002**: Report generation (Markdown + PDF) completes in under 2 minutes for a session with up to 50 events, with the vision model already cached or not installed. First-run model download time is excluded.
- **SC-P6-003**: The generated Markdown file, used as the sole context in a chatbot session, enables the chatbot to correctly answer at least 4 out of 5 factual questions about the video (e.g. first event time, event count, detected classes, peak confidence, busiest period).
- **SC-P6-004**: Toggling one event off and regenerating a report produces a report with exactly one fewer event across every section (timeline, stats, object inventory, JSON appendix).
- **SC-P6-005**: When the vision model is installed and its weights are cached, 100% of included events receive a non-empty visual description in the generated report.

---

## Assumptions

- Detection must be fully complete (or explicitly cancelled) before report generation. In-progress runs cannot generate a report.
- Thumbnails and heatmap are produced by the existing detection pipeline. If absent (e.g. run cancelled before any events), the report handles each gracefully.
- The vision model (Moondream2) is entirely optional — all US1 functionality works without it.
- The model weights are downloaded once and cached locally. Internet is required only for the initial download; all subsequent use is fully offline.
- Output folder defaults to Desktop if not configured — consistent with the existing video export behaviour.
- A "typical session" for performance sizing: a single video up to 60 minutes, up to 50 included events, 1080p resolution.
- The PDF is generated via the same rendering mechanism used by the existing Phase 5 incident report (no new PDF library required).
- Audio transcription is explicitly out of scope for this phase.
- Phase 7 (in-app chatbot) is out of scope. The Markdown file is the handoff artifact between Phase 6 and Phase 7.
