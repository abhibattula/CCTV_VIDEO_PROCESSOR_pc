# Feature Specification: Phase 5 — Professional Reporting & Activity Insights

**Feature Branch**: `005-reporting-and-heatmap`
**Created**: 2026-06-23
**Status**: Draft
**Input**: User description: "Phase 5 — Professional Reporting & Activity Insights, for the CCTV Video Processor PC desktop app. Three features, all building on data/code that already exists from Phases 1-4: (1) Activity Heatmap — a per-pixel visualization of where motion/activity occurred most across a processed video, shown as an optional overlay aid on the ROI-drawing screen and embedded in the PDF report, working in both MOG2 and YOLO detection modes; (2) PDF/HTML Incident Report — a one-click report with a summary, the activity heatmap, a thumbnail grid of included events with timestamps/labels/confidence, and a chain-of-custody section with SHA-256 hashes of the source and (if produced) exported files, saved automatically to the user's chosen output folder; (3) CSV/JSON Event Log Export — one-click plain-data exports of the same included-events data. All three are read-only/derived from existing per-job data, consistent with the app's session-first, no-persistence design."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate a Professional Incident Report (Priority: P1)

After reviewing and filtering detected events on the Timeline page, a user
wants a single polished document they can hand to a client, manager, or
insurance adjuster — instead of just a video file — summarizing what was
found, when, and with what confidence, plus enough integrity information to
support a chain-of-custody claim.

**Why this priority**: This is the feature most directly responsible for
making the app feel like a professional, out-of-the-box product rather than
a personal utility — and it requires no new capability the app doesn't
already have (events, thumbnails, hashes), just packaging it well.

**Independent Test**: Load a video, run detection, exclude a couple of
events on the Timeline page, go to the Export page, click "Generate PDF
Report," and verify the resulting document only shows the included events
and reflects the right counts/metadata, independent of whether a heatmap
exists or a video has been exported yet.

**Acceptance Scenarios**:

1. **Given** a completed detection run with some events excluded on the
   Timeline page, **When** the user clicks "Generate PDF Report," **Then**
   the report shows only the included events, each with its own thumbnail,
   time range, label, and confidence score, and a summary reflecting "N of M
   events included."
2. **Given** a job where no video has been exported yet, **When** the report
   is generated, **Then** the chain-of-custody section clearly states that no
   export has been produced yet, instead of showing a blank or broken field.
3. **Given** a job where a video has already been exported, **When** the
   report is generated, **Then** the chain-of-custody section shows a
   verification value (hash) for both the original source file and the
   exported file.
4. **Given** the user has already chosen an output folder for video export,
   **When** they generate a report, **Then** it saves automatically into that
   same folder with a recognizable, non-colliding filename, without being
   asked to choose a location again.
5. **Given** a job with zero included events (all excluded, or none
   detected), **When** the user attempts to generate a report, **Then** the
   system clearly indicates there is nothing to report rather than producing
   an empty or misleading document.
6. **Given** a report has already been generated once for this job, **When**
   the user clicks "Generate PDF Report" again without changing anything,
   **Then** a second, distinctly named file is produced rather than the
   first being overwritten or the request being rejected.

---

### User Story 2 - See Where Activity Concentrated (Priority: P2)

After a detection run finishes, a user wants to visually see where in the
frame motion/activity was concentrated — both to make sense of the results
and to help decide where to draw detection zones if they reprocess the same
camera angle again later.

**Why this priority**: A genuine, novel visual differentiator that serves
two purposes at once (a review aid and a report visual), but the app is
fully usable without it — it's an enhancement layered on top of detection,
not a blocking dependency for anything else.

**Independent Test**: Run detection on a video with motion concentrated in
one area, then return to the Home page's zone-drawing screen for that same
video and confirm a visual indicator shows where the activity was, without
it interfering with drawing new zones.

**Acceptance Scenarios**:

1. **Given** a completed detection run with some activity in the video,
   **When** the user views the zone-drawing screen for that job afterward,
   **Then** an optional, off-by-default visual aid is available showing
   where activity concentrated, layered over the existing preview without
   blocking the ability to draw zones.
2. **Given** a video processed in either of the two available detection
   modes, **When** the run completes, **Then** the visual aid is available
   in both cases — the user does not lose this capability by choosing one
   detection mode over the other.
3. **Given** a video with no detected activity at all, **When** the run
   completes, **Then** no visual aid is shown (rather than a meaningless
   blank or solid-colored image).
4. **Given** a freshly loaded video with no detection run yet for it, **When**
   the user views the zone-drawing screen, **Then** the visual aid option is
   simply unavailable/hidden, with no error shown.
5. **Given** the PDF report (User Story 1) is generated for a job that has
   this visual aid available, **When** the report is produced, **Then** the
   visual aid image is included in it.
6. **Given** the visual aid is currently showing, **When** the user turns it
   back off, **Then** the underlying zone-drawing canvas remains fully
   usable throughout — drawing, editing, and deleting zones work identically
   to when the aid was never shown.

---

### User Story 3 - Export the Event Data as Plain Data (Priority: P3)

A user who wants to load detected-event data into a spreadsheet or another
system, rather than just look at a video or read a PDF, wants a one-click
way to save that data in a common plain-data format.

**Why this priority**: Valuable for power users and integrations, but
narrower in audience than the report — most users will want the PDF, not the
raw data, so this is additive rather than essential.

**Independent Test**: After a completed detection run, click the
data-export action and verify a file is produced in the chosen output
folder containing exactly the included events' timestamps, labels, and
scores, openable in a common spreadsheet or text application.

**Acceptance Scenarios**:

1. **Given** a completed detection run with some events excluded, **When**
   the user requests the event-log data export, **Then** the saved file
   contains only the included events, matching what the report and video
   export would also include.
2. **Given** the user has already chosen an output folder, **When** they
   request the data export, **Then** the file saves there directly without
   an additional save-location prompt.
3. **Given** a job with zero included events, **When** the user requests the
   data export, **Then** the system indicates there's nothing to export
   rather than producing an empty file silently.

---

### Edge Cases

- What happens if the user requests a report or data export while detection
  is actively still running? These actions are unavailable during that
  window, since the event list is still incomplete (FR-P5-020). A video
  export running at the same time, by contrast, does not block these
  actions at all — video export only reads events and never changes them,
  so a report or data export proceeds normally even while a video export is
  in progress, acting on the same already-finalized event list either way.
- What happens if the user generates a report, keeps reviewing the Timeline
  page, changes which events are included, then generates the report again?
  The second report must reflect the updated inclusion set, not the first.
- What happens if the same data-export or report action is triggered twice
  in a row? Each must produce its own distinctly named file rather than
  silently overwriting the previous one or failing.
- What happens to this output when the user starts a New Project or stops
  the application? Consistent with this app's existing no-persistence
  design, none of these generated files are tracked or remembered by the
  app after the job ends — they exist only as ordinary files in the folder
  the user chose.
- What happens if the user starts a New Project while a report or data
  export is still being generated for the current job? The in-progress
  generation is abandoned along with the rest of the job's state, consistent
  with how New Project already abandons any other in-progress operation
  (FR-P5-020); any partially written file is simply left as an incomplete,
  ordinary file on disk — the application makes no attempt to clean it up,
  consistent with there being no tracked state to clean up in the first
  place.
- What happens if a job's detection run was cancelled partway through
  (rather than running to full completion)? These three actions still work
  on whatever events were recorded before cancellation — there is no
  distinction between "completed" and "cancelled-with-partial-results" for
  the purposes of this feature, since both leave behind a normal list of
  events to report on (FR-P5-020).
- What happens if the source video file no longer exists at its original
  location, the chosen output folder is no longer accessible, or (for
  chain-of-custody purposes) a previously exported file has been moved or
  deleted, at the moment one of these three actions runs? The system
  surfaces a clear error naming the specific file or location that's the
  problem, rather than failing silently or crashing (FR-P5-022).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-P5-001**: The system MUST provide a one-click action, available once
  a detection run has completed, that generates a single incident report
  document summarizing the job's results.
- **FR-P5-002**: The report MUST include a summary section: source video
  name, when the report was generated, how many events are included versus
  the total number detected, total duration of included events, and the
  video's resolution and codec.
- **FR-P5-003**: The report MUST include exactly the events currently marked
  "included" on the Timeline page — excluded events MUST NOT appear in the
  report.
- **FR-P5-004**: For each included event, the report MUST show a
  representative thumbnail image, its time range, its label (e.g. a detected
  object type, or a generic motion label), and its confidence score.
- **FR-P5-005**: The report MUST include a chain-of-custody section showing
  a verification value (cryptographic hash) for the original source video
  file, and, if a video has already been exported for this job, a
  verification value for that exported file as well. Computing these
  verification values is not subject to a specific time limit in this
  phase — larger source files naturally take longer, and no upper bound on
  source file size is assumed or enforced.
- **FR-P5-006**: If no video has been exported for the job yet at the time
  the report is generated, the chain-of-custody section MUST clearly state
  that, rather than showing a blank, broken, or misleading value.
- **FR-P5-007**: The report MUST save automatically into the same output
  folder already selected for video export, using an automatically
  generated filename that includes a timestamp precise enough that two
  reports generated for the same job cannot collide with each other, without
  requiring the user to choose a save location again.
- **FR-P5-008**: If there are zero included events at the time a report is
  requested, the system MUST inform the user there is nothing to report —
  via an explicit, visible message naming the reason, not merely a disabled
  control with no explanation — rather than generating an empty or
  misleading document.
- **FR-P5-009**: After a detection run completes, the system MUST make
  available an optional, off-by-default visual aid showing where activity
  was concentrated across the video, using a continuous color gradient
  (cooler colors for less activity, warmer colors for more), viewable at the
  source video's own resolution on the same screen used for drawing
  detection zones — the aid's clarity is therefore not reduced for
  higher-resolution source videos.
- **FR-P5-010**: This visual aid MUST be available regardless of which of
  the two detection modes produced the results — the user MUST NOT lose
  access to it solely because of which mode they chose.
- **FR-P5-011**: If a detection run found no activity at all, the system
  MUST NOT present this visual aid (rather than showing a meaningless or
  blank image).
- **FR-P5-012**: If no detection run has yet completed for the currently
  loaded video, the visual aid MUST simply be unavailable, with no error or
  broken-image state shown to the user.
- **FR-P5-013**: When available for the current job (i.e. not in the
  zero-activity case covered by FR-P5-011), the visual aid MUST also be
  included as an image within the incident report (FR-P5-001). When not
  available, the report MUST simply omit this section rather than showing a
  placeholder or broken image.
- **FR-P5-014**: The visual aid MUST reflect only the most recently
  completed detection run for the current job — running detection again for
  the same job replaces it entirely rather than accumulating across runs,
  and it is not retained or reused once a different video is loaded. This is
  the same per-job reset boundary already established by the New Project and
  file-loading behavior shipped in Phase 4 — no separate reset mechanism is
  introduced by this feature.
- **FR-P5-015**: The system MUST provide one-click actions, available once a
  detection run has completed, to export the included events' data (time
  ranges, labels, confidence scores) as a plain data file in each of two
  common formats, separate from the incident report.
- **FR-P5-016**: These data-export actions MUST include exactly the same set
  of events as FR-P5-003's "included" set — identically, not merely
  similarly, filtered — and MUST save into the already-selected output
  folder without an additional save-location prompt.
- **FR-P5-017**: If there are zero included events at the time a
  data-export action is requested, the system MUST inform the user there is
  nothing to export — via an explicit, visible message, not merely a
  disabled control — rather than silently producing an empty file.
- **FR-P5-018**: Repeated requests for the report or either data-export
  format MUST each produce a distinctly named file rather than overwriting a
  prior one or failing.
- **FR-P5-019**: None of the artifacts produced by this feature (report,
  visual aid, data-export files) introduce any new state that the
  application itself persists or remembers beyond the lifetime of the
  current job, consistent with the application's existing session-only
  design.
- **FR-P5-020**: All three actions (report, visual aid, data export) MUST be
  available whenever the current job has at least one recorded event,
  regardless of whether its detection run reached full completion or was
  cancelled partway through, and regardless of whether a video export has
  already run or is currently running for this job (video export only reads
  events, it never changes them, so it does not conflict with these three
  read-only actions). These actions MUST NOT be available only while
  detection itself is actively in progress for the current job, since the
  event list is still incomplete during that window.
- **FR-P5-021**: While a report or data-export request is being processed,
  the system MUST show a clear in-progress indication, and MUST prevent a
  second identical request from being submitted concurrently (e.g. by
  disabling the triggering control until the first request finishes); once
  finished, the system MUST show a clear completion (or failure) indication
  — the user MUST NOT be left unable to tell whether anything happened.
- **FR-P5-022**: If the source video file, the chosen output folder, or (for
  chain-of-custody purposes) a previously exported file is no longer
  accessible when one of these three actions runs, the system MUST surface a
  clear error identifying which specific file or location is the problem,
  rather than failing silently or crashing.
- **FR-P5-023**: The chain-of-custody section MUST identify each file by its
  filename only, not its full file-system path, so that sharing the report
  with an external party does not reveal local folder structure or user
  account names. The verification value (hash) still uniquely covers that
  specific file's exact content regardless of how it is labeled.
- **FR-P5-024**: The control that toggles the visual aid on and off MUST be
  a standard, keyboard-operable control, consistent with the rest of this
  application's keyboard-accessible review experience.

### Key Entities *(include if feature involves data)*

- **Incident Report**: A generated document for a single job, composed of a
  summary, an optional activity visual aid, a per-event thumbnail/label/
  confidence listing (limited to included events), and a chain-of-custody
  section with file verification values.
- **Activity Visual Aid (Heatmap)**: A derived, per-job visualization of
  where activity concentrated across a video, produced once per completed
  detection run, consumed by both the zone-drawing screen and the Incident
  Report.
- **Event Log Export**: A plain-data file (one of two formats) containing
  the included events' time ranges, labels, and confidence scores for a
  single job.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-P5-001**: A user can produce a complete incident report in a single
  click, with no additional prompts, in approximately 10 seconds for a job
  with 50 included events or fewer on the first generation for that job
  (repeat generations are faster, since thumbnails are cached). This is a
  best-effort target, not a hard guarantee: per-event thumbnail extraction
  cost is dominated by source-video decode characteristics (resolution,
  codec) that vary by hardware and by the source file itself — measured
  directly on the reference development machine across repeated trials,
  typical timing for 50 events ranged ~9-12 seconds. The system MUST NOT
  fail, hang, or time out attempting to meet this target — slower hardware
  or more demanding source codecs are expected to simply take longer, the
  same way larger event counts are expected to take proportionally longer.
- **SC-P5-002**: 100% of events excluded by the user on the Timeline page
  are absent from both the incident report and the data-export files, with
  no manual re-filtering needed.
- **SC-P5-003**: The activity visual aid is available after a completed run
  regardless of which detection mode was used, verified across both modes
  with zero difference in user-facing availability.
- **SC-P5-004**: A user can obtain the same event data in a plain data
  format in a single click, with the resulting file's record count exactly
  matching the included-event count shown on the Timeline page.
- **SC-P5-005**: Generating a report or data export does not require the
  user to leave the Export page or interrupt any other in-progress
  operation.

## Assumptions

- The user has already run detection at least once for the current job
  before any of these three actions become available, per the precise
  job-state gating defined in FR-P5-020; none of them are meant to work on a
  job with no recorded events yet.
- "Chain of custody" in this context means a basic file-integrity
  verification value suitable for demonstrating a file hasn't been altered
  since the report was generated — not a legally certified evidentiary
  process, jurisdiction-specific compliance, or digital signature/
  notarization scheme.
- The report's visual design and content are fixed for this phase (not
  user-customizable with logos, letterhead, or selectable sections) —
  customization is a possible future enhancement, not part of this scope.
- "Plain data format" for the event-log export refers to two widely
  supported, human-and-machine-readable formats suitable for spreadsheets
  and simple programmatic consumption (not a specialized or proprietary
  format).
- All three features operate only on the single active job already
  supported by the application today; none of them introduce multi-job,
  batch, or cross-session aggregation capability.
