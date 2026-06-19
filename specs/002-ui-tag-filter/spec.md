# Feature Specification: Phase 2 — UI Redesign, Tag Filtering & Smart Export

**Feature Branch**: `002-ui-tag-filter`
**Created**: 2026-06-19
**Status**: Draft
**Builds on**: Phase 1 (`001-cctv-pc-processor`) — detection engine, export engine, and SPA shell are complete and working

---

## Overview

Phase 1 produced a working CCTV processor with MOG2/YOLO detection, a timeline review page, and FFmpeg export. Phase 2 makes it significantly more powerful and pleasant to use by adding tag-based event filtering, a redesigned UI with confidence badges, smart export presets, video overlay burn-in, live detection analytics, and keyboard-driven power-user workflows.

The core loop (load → detect → review → export) stays the same. These features make each step faster, more informative, and more flexible for daily security review work.

---

## Clarifications

### Session 2026-06-19

- Q: When a label filter is active, how should non-matching event blocks appear on the canvas strip — hidden (gaps) or greyed out? → A: Grey out — non-matching blocks remain visible at ~20% opacity; matching blocks are full-opacity. This preserves event density context so users can see surrounding activity.
- Q: How should the event list handle large event counts (300+)? → A: Virtual scrolling — only render cards in the visible viewport; activate when event count exceeds 100 events to keep filter and scroll response fast.
- Q: Does the LabelFilter state persist when the user navigates away from the timeline page within the same session? → A: Yes — filter and score threshold survive navigation between pages (e.g., timeline → export → back to timeline) and reset only when a new job is loaded or "Clear Filters" is explicitly clicked.

---

## User Scenarios & Testing

### User Story 1 — Tag Filtering on the Timeline (Priority: P1)

A security operator has a 4-hour overnight recording. Detection found 312 events: mostly cars, a few pedestrians, one dog. They only care about pedestrian events. They click "Person" in the filter bar and instantly see only 17 pedestrian events. A score threshold slider at 0.6 hides the weak detections. They select all visible events and Quick Export — done in under a minute.

**Why P1**: Without filtering, a high-event-count timeline is unusable. Users scroll through hundreds of irrelevant events. Tag filtering is the single highest-impact usability improvement possible.

**Independent Test**: Load a job with events tagged with at least two different labels (requires YOLO mode). Apply a label filter. Verify only matching events appear, canvas strip updates, and toolbar count reflects filtered total. Clear filter — all events return.

**Acceptance Scenarios**:

1. **Given** a timeline with events labelled "Person", "Car", and "Dog", **When** the user clicks the "Person" chip, **Then** only Person events are visible in the event list; canvas strip renders Person event blocks at full opacity and all other blocks at ~20% opacity; toolbar shows "17 shown / 312 total"
2. **Given** a label filter is active, **When** "Select All" is clicked, **Then** only the currently visible (filtered) events are selected
3. **Given** multiple chips active (Person + Car), **When** the user clicks "Clear Filters", **Then** all events are visible again and all chips are deactivated
4. **Given** an event has no label (MOG2 mode), **When** the filter bar is opened, **Then** a "Unlabelled" chip allows filtering those events
5. **Given** the score threshold slider is at 0.6, **When** applied, **Then** only events with peak score ≥ 0.6 are visible; excluded events are not deleted, just hidden
6. **Given** a label tag on an event card, **When** the user clicks it, **Then** that label's filter chip activates immediately (one-click filter shortcut)

---

### User Story 2 — Multi-Select and Bulk Operations (Priority: P2)

An operator reviews 80 events after a long recording. They use label filter to show only Person events, then Ctrl+click to deselect two obvious false positives, then click "Exclude Selected" to remove them. Total time for 80 events: under 2 minutes.

**Why P2**: Single-toggle per card is too slow for large event sets. Bulk operations multiply review speed.

**Independent Test**: With ≥ 5 events, Ctrl+click 3 cards (multi-select mode activates). Click "Exclude Selected". All 3 toggle to excluded. Click Undo. All 3 revert.

**Acceptance Scenarios**:

1. **Given** a timeline, **When** the user Ctrl+clicks a card, **Then** multi-select mode activates; card shows a blue selection ring; toolbar shows "1 selected"
2. **Given** multi-select mode is active, **When** the user clicks a checkbox on another card, **Then** that card joins the selection
3. **Given** 3 events selected, **When** "Exclude Selected" is clicked, **Then** all 3 toggle to excluded in one operation; toolbar shows bulk-action confirmation
4. **Given** a bulk operation was just performed, **When** Ctrl+Z or the "Undo" button is pressed, **Then** all affected events revert to their pre-bulk state
5. **Given** a label filter is active, **When** "Select Visible" is clicked, **Then** only the currently visible filtered events are selected, not hidden ones

---

### User Story 3 — Redesigned UI with Confidence Badges and Keyboard Shortcuts (Priority: P3)

A daily user reviews 20–30 recordings per week. The redesigned card UI shows colour-coded confidence scores at a glance. They navigate entirely with keyboard: arrow keys to move between cards, Space to toggle, Ctrl+E to export. No mouse needed after initial detection.

**Why P3**: Confidence badges make triage instant (red = probably false positive). Keyboard nav removes hand-travel time for power users.

**Independent Test**: Open a timeline with keyboard only. Arrow Down moves focus card-to-card. Space toggles the focused card. Ctrl+E navigates to export. Entire review workflow completes without touching the mouse.

**Acceptance Scenarios**:

1. **Given** an event with peak score 0.85, **When** rendered, **Then** the card shows a green pill badge "0.85"
2. **Given** an event with peak score 0.50, **When** rendered, **Then** the badge is amber; below 0.4 it is red
3. **Given** focus on an event card, **When** Space is pressed, **Then** the event toggles included/excluded
4. **Given** focus on a card, **When** Arrow Down/Up is pressed, **Then** focus moves to next/previous card; page scrolls to keep focused card visible
5. **Given** the timeline page, **When** Ctrl+E is pressed, **Then** navigation goes to Export page
6. **Given** the timeline page, **When** Ctrl+A is pressed, **Then** all visible events are selected; Ctrl+D clears selection
7. **Given** the home page, **When** rendered, **Then** settings are laid out in two columns with grouped cards (Detection, Sensitivity, Advanced, Timestamp)

---

### User Story 4 — Smart Export Presets with Burn-In (Priority: P4)

A security manager wants an "Evidence Pack" for an incident — individual clips, full quality, with the timestamp and "Person" label burned visibly into each clip. They select "Evidence Pack" preset. One click configures everything. Export runs and produces individual H.264 clips each with a readable timestamp overlay.

**Why P4**: Repeating the same export configuration daily is tedious. Presets and burn-in automate the most common professional workflows.

**Independent Test**: Select "Security Report" preset. Verify export page auto-selects: merged output, Person-only filter, burn-in enabled. Export a real video clip and open it in a media player — confirm timestamp and label text are visible in the bottom-left corner.

**Acceptance Scenarios**:

1. **Given** the export page, **When** "Security Report" preset is selected, **Then** output type = Merged, label filter = Person, burn-in = on (timestamp + label)
2. **Given** "Evidence Pack" preset, **When** selected, **Then** output type = Individual Clips, quality = Original, burn-in = off
3. **Given** "Quick Highlights" preset, **When** selected, **Then** the top 10 events by score are auto-selected; output = Merged, quality = 720p
4. **Given** burn-in is enabled, **When** a clip is exported, **Then** each clip has a semi-transparent black bar in the bottom-left with white text: e.g., "08:35:12 • Person" (or "00:05:12" if no recording start set)
5. **Given** "Quick Highlights" with only 4 events, **When** preset is applied, **Then** all 4 events are selected (no minimum)

---

### User Story 5 — Live Detection Stats Dashboard (Priority: P5)

While a 2-hour recording processes, a user watches the processing page. A live mini bar chart shows: "Person: 12, Car: 47" incrementing in real time. An events-per-minute counter reads "5.3/min". This tells them detection is working correctly before it finishes.

**Why P5**: Operators can catch misconfigured sensitivity mid-run (e.g., 0 events after 20% of the video means sensitivity is wrong).

**Independent Test**: Run YOLO detection on a video with multiple object types. Watch the processing page. Confirm bar chart increments each time an event is found. Confirm events/min counter updates every 10 seconds.

**Acceptance Scenarios**:

1. **Given** YOLO detection is running, **When** a new event is found, **Then** the label bar chart on the processing page updates within 3 seconds
2. **Given** ≥ 1 minute of detection has elapsed, **When** the user views the processing page, **Then** "Events/min: N.N" is visible
3. **Given** MOG2 mode (no labels), **When** processing, **Then** the chart shows a single bar: "Motion: N"
4. **Given** detection completes and user navigates to timeline, **Then** compact label chips ("Person×12 Car×47") appear in the timeline toolbar

---

### Edge Cases

- No events match the active filter: show "No events match this filter" empty state with a "Clear Filters" button
- All visible events are bulk-excluded with the score filter active: warn "No events selected for export — adjust filters or include more events"
- Burn-in requested but source has no audio track: burn-in proceeds on video-only output (no error)
- Burn-in with no `recording_start` set: shows file-relative time (e.g., "00:05:12") not a blank field
- "Quick Highlights" preset applied but fewer than 10 events exist: selects all events (no truncation)
- Keyboard shortcut pressed when focus is on an input field: shortcut is suppressed (normal typing behaviour preserved)
- YOLO labels not present (MOG2 mode): label filter bar is hidden; preset options that require label filtering show a tooltip "Requires Object Detection mode" and are greyed out
- User navigates timeline → export → timeline within same session: active LabelFilter and ScoreThreshold are restored exactly as left; the event list re-renders with the same filter applied
- New job loaded while a filter is active: LabelFilter and ScoreThreshold reset to defaults (all events visible) before the new job's timeline is rendered

---

## Requirements

### Functional Requirements

**Tag Filtering (US1)**

- **FR-P2-001**: The timeline page MUST display a label filter bar showing one chip per distinct `zone_label` value found in the current job's events, plus an "Unlabelled" chip when unlabelled events exist
- **FR-P2-002**: Activating one or more label chips MUST restrict the visible event list to only events matching any active chip (OR logic between multiple active chips); the canvas strip MUST render matching event blocks at full opacity and non-matching blocks at ~20% opacity (greyed out, not hidden) so the user retains density context for the full recording
- **FR-P2-003**: The score threshold slider MUST hide (not exclude) events with `peak_motion_score` below the slider value; slider default is 0.0 (all events visible)
- **FR-P2-004**: The event count display MUST update to "N shown / M total" whenever any filter or threshold changes
- **FR-P2-005**: Clicking a label badge on an event card MUST instantly activate that label's filter chip

**Multi-Select & Bulk Ops (US2)**

- **FR-P2-006**: Each event card MUST display a checkbox; both Ctrl+click on the card body AND clicking the checkbox MUST enter/extend multi-select mode
- **FR-P2-007**: When events are selected, a bulk-action toolbar MUST appear with: "Include Selected", "Exclude Selected", "Invert Selection", "Select Visible", "Clear Selection"
- **FR-P2-008**: Bulk include/exclude operations MUST be reversible via a single Undo action (Ctrl+Z or on-screen Undo button); undo reverts all events changed in the last bulk operation
- **FR-P2-009**: Multi-select mode MUST be clearable by pressing Escape or clicking an empty area of the event list

**UI & Confidence Badges (US3)**

- **FR-P2-010**: Each event card MUST display a colour-coded confidence badge showing the `peak_motion_score` value: green for ≥ 0.7, amber for 0.4–0.69, red for < 0.4
- **FR-P2-011**: The timeline page MUST support keyboard navigation: Arrow Up/Down between cards, Space to toggle included/excluded, Enter to open preview, Ctrl+E to navigate to export, Ctrl+A to select all visible, Ctrl+D to deselect all, Escape to clear multi-select
- **FR-P2-012**: The home page settings panel MUST be redesigned with grouped cards in a two-column layout for screens wider than 900px
- **FR-P2-013**: Event cards MUST display the detected label as a coloured tag pill (e.g., "Person" in blue, "Car" in orange, "Dog" in green — consistent colour-to-label mapping)

**Smart Export Presets (US4)**

- **FR-P2-014**: The export page MUST offer three presets: "Security Report", "Evidence Pack", "Quick Highlights"; each MUST auto-configure output type, label scope, quality, and burn-in in a single click
- **FR-P2-015**: When burn-in is enabled, the export engine MUST render a semi-transparent overlay on each exported clip showing the timestamp and label using FFmpeg's drawtext filter
- **FR-P2-016**: "Quick Highlights" MUST auto-select the top 10 events by score (or all events if fewer than 10 exist) when the preset is applied, replacing whatever was previously selected

**Live Detection Dashboard (US5)**

- **FR-P2-017**: The processing page MUST display a live label breakdown bar chart that updates each time a new event arrives via the SSE stream
- **FR-P2-018**: The processing page MUST display an events-per-minute rate, calculated from event count and elapsed time, refreshed every 10 seconds
- **FR-P2-019**: After detection completes, the timeline toolbar MUST show a compact label summary row (e.g., "Person×12  Car×47  Dog×3")
- **FR-P2-020**: When the event list contains more than 100 events, the timeline page MUST use virtual scrolling — rendering only the cards in the visible viewport — so that scrolling and filter updates remain responsive regardless of total event count

### Key Entities

- **LabelFilter**: Active set of label strings selected for filtering; persists across page navigation within the same session (e.g., timeline → export → timeline retains the filter); resets to empty (all visible) when a new job is loaded or "Clear Filters" is clicked; not persisted between app launches
- **ScoreThreshold**: Float 0.0–1.0; events below this threshold are hidden from view but not toggled to excluded
- **SelectionSet**: Set of event indices the user has multi-selected; ephemeral UI state; cleared on navigation
- **ExportPreset**: Named configuration — fields: `output_type`, `label_filter`, `quality`, `burn_in_enabled`, `auto_top_n`
- **BurnInOverlay**: Text rendered into exported video via drawtext filter: `"{timestamp} • {label}"`, bottom-left position, white text on semi-transparent black background, 18px font

---

## Success Criteria

### Measurable Outcomes

- **SC-P2-001**: A user with 100+ events can filter to a specific label, review, and reach the export page in under 30 seconds
- **SC-P2-002**: Bulk-excluding 20 events requires 1 selection action + 1 button click (not 20 individual card clicks)
- **SC-P2-003**: A complete review workflow (filter → multi-select → export) is achievable entirely via keyboard with zero mouse interactions
- **SC-P2-004**: Exported clips with burn-in show legible timestamp and label text on any standard 1080p display when viewed at 100% zoom
- **SC-P2-005**: The live detection chart updates within 3 seconds of each new event being detected
- **SC-P2-006**: Selecting any export preset configures all associated settings in a single click with no additional required input
- **SC-P2-007**: Scrolling through a 300-event timeline and applying a label filter both complete without perceptible lag (under 100ms visual response) regardless of total event count

---

## Assumptions

- Phase 1 backend API is unchanged; Phase 2 adds new endpoints and extends existing ones without removing or breaking existing ones
- Tag labels come exclusively from `zone_label` on event objects; MOG2 events have `zone_label` as `null` or empty string
- Burn-in overlay uses FFmpeg's built-in `drawtext` filter with the font available to FFmpeg on the host system; no external font files are required
- Keyboard shortcuts are scoped to the timeline page container and are suppressed when an input field has focus
- Undo is single-level (one Ctrl+Z reverts the most recent bulk operation); full multi-level undo history is out of scope
- Export presets are read-only in Phase 2; custom preset creation is deferred to Phase 3
- The live chart is driven entirely by SSE events already emitted in Phase 1; no new backend SSE changes are needed
- Label-to-colour mapping is fixed in Phase 2 (Person=blue, Car=orange, Dog=green, Cat=purple, Bus=red, Bicycle=teal, default=grey)
- The redesigned UI supports the existing dark theme only; a light theme toggle is Phase 3 scope
- LabelFilter and ScoreThreshold state is held in the SPA's in-memory session store (not URL params, not localStorage); it survives client-side navigation but is lost on page reload or app restart
