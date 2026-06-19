# Feature Specification: CCTV Video Processor PC

**Feature Branch**: `001-cctv-pc-processor`
**Created**: 2026-06-19
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Quick Activity Export (Priority: P1)

A user has a CCTV recording from a day where something may have happened. They drop the
file onto the app, click Start, wait a few minutes, and receive a single merged video
file containing only the moments where movement occurred — without reviewing anything.

**Why this priority**: This is the core value proposition. Every other story builds on
the ability to detect motion and produce a clean output. Without this, the app has no
purpose.

**Independent Test**: Drop a test video with 3 clearly active segments and 2 long dead
periods. After detection and Quick Export, the output file contains only the active
segments with no silent gaps. Total duration of output is less than source duration.

**Acceptance Scenarios**:

1. **Given** a video file with recorded motion, **When** the user drops it onto the app
   and clicks Start Detection with default settings, **Then** detection completes within
   a reasonable time and at least one motion event is found.
2. **Given** detection has completed with events found, **When** the user clicks Quick
   Export, **Then** a merged MP4 file is written to the user's Desktop containing only
   the detected active segments.
3. **Given** a video whose codec supports stream copy (H.264, HEVC), **When** export
   completes, **Then** the output file is produced in under 30 seconds regardless of
   source duration.
4. **Given** a file the app cannot read, **When** the user drops it, **Then** a clear
   error message is shown explaining why and suggesting HandBrake for re-encoding.

---

### User Story 2 — Review and Curate Timeline (Priority: P2)

After detection, a user wants to see every detected moment on a visual timeline, preview
individual clips before deciding, exclude false positives (wind, shadows, animals), and
then export only the events they selected.

**Why this priority**: Users investigating a specific incident need to confirm what they
export. False positives waste time when reviewing hours of footage.

**Independent Test**: Run detection on a video with mixed true positives and false
positives. On the Timeline page, toggle off two events. On the Export page, confirm
only the included events appear in the output file.

**Acceptance Scenarios**:

1. **Given** detection has completed, **When** the user opens the Timeline page, **Then**
   a full-width visual strip shows the source duration with blue blocks for each event's
   position and a card for each event below it.
2. **Given** the timeline is open, **When** the user clicks an event card, **Then** the
   event is toggled excluded (greyed out in strip, card dims) or re-included on the
   next click.
3. **Given** the timeline is open, **When** the user clicks the Preview button on an
   event card, **Then** a video clip of that segment plays in an overlay modal within
   5 seconds.
4. **Given** the user has toggled some events off, **When** they click Export Selected,
   **Then** the output file contains only the included events in chronological order.
5. **Given** detection finds zero events, **When** the Timeline page loads, **Then** a
   diagnostic message is shown with the suggestion to try a higher sensitivity setting
   or verify the source video contains motion.

---

### User Story 3 — Flexible Output Options (Priority: P3)

A user wants to choose the output format: either a single merged video or individual
clip files per event, and optionally downscale the output quality to reduce file size.

**Why this priority**: Different use cases need different formats — a security review
needs individual time-stamped clips; sharing an incident summary needs a single merged
file. Quality downscaling saves storage for long recordings.

**Independent Test**: Export the same detected events twice — once as Merged MP4 and
once as Individual Clips. Verify a single file appears in one case and multiple
numbered files in the other. Export at 720p and confirm the output resolution matches.

**Acceptance Scenarios**:

1. **Given** the Export page, **When** the user selects "Individual Clips" and exports,
   **Then** one MP4 file per included event is written to the output folder, each named
   with the event number and timestamp.
2. **Given** the Export page, **When** the user selects "Merged MP4" (default),
   **Then** a single MP4 file containing all included events is written with chapter
   markers at each event boundary.
3. **Given** the Export page, **When** the user selects 720p quality and exports,
   **Then** the output video height is 720 pixels regardless of source resolution.
4. **Given** the Export page, **When** the user clicks Browse next to the output folder
   field, **Then** the operating system's native folder picker opens and the selected
   path is populated in the field.
5. **Given** export completes, **When** the user clicks Open Folder, **Then** the
   system file manager opens to the folder containing the output file(s).

---

### Edge Cases

- What happens when the source video has no audio track? Export must succeed without
  errors; output file also has no audio.
- What happens when the source codec requires re-encoding (MJPEG, VP9, AV1)? A warning
  banner appears before detection starts; export proceeds but takes longer.
- What happens when detection is cancelled mid-run? Events found so far are preserved
  and the user can export partial results or restart detection.
- What happens when the output folder runs out of disk space during export? A clear
  error message is shown with the path and estimated space needed.
- What happens when a video file with spaces or non-ASCII characters in its path is
  selected? The app must handle it correctly on all operating systems.
- What happens if the user drops a new video file while a completed but unexported session
  exists? The app MUST show a confirmation dialog: "You have N events from [filename].
  Starting a new job will discard them — export first or continue?" The user can choose
  to export before proceeding or discard the previous session immediately.
- What happens if the app is force-closed or crashes while writing an export? On next
  launch, the app MUST detect any incomplete output file (via a write-in-progress
  marker) and delete it automatically without prompting the user.
- What happens when the user selects object detection mode and the required model has
  not been downloaded yet? A progress indicator shows the download; if the device is
  offline, an error suggests switching to background subtraction mode.
- What happens to temporary preview clip files when the app exits? All preview clips
  MUST be deleted from the system temp folder on app close.

---

## Clarifications

### Session 2026-06-19

- Q: Should the app let users enter the recording's start time so event cards show real-world clock timestamps alongside file-relative timestamps? → A: Yes — an optional "Recording started at (HH:MM:SS)" field on the Home screen. When provided, event cards display both wall-clock time (e.g., "02:47:33") and file-relative position. Individual clip filenames also use wall-clock time when the field is set.
- Q: If the app is closed or crashes mid-export, what should happen to the partially written output file? → A: Auto-delete any incomplete output file on next launch using a write-in-progress marker; no user prompt required.
- Q: Should the app warn before discarding a completed but unexported session when a new video is loaded? → A: Yes — show a confirmation dialog: "You have N events from [filename]. Starting a new job will discard them. Export first or continue?" with Export and Continue buttons.
- Q: When should temporary preview clip files be deleted? → A: Delete all preview clips when the app is closed (on exit).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The app MUST allow a user to load a video file by dropping it onto the
  application window or by clicking a Browse button that opens the OS native file picker.
- **FR-002**: The app MUST probe the video file immediately on load and display its
  resolution, codec, duration, and any compatibility warnings before detection starts.
- **FR-003**: The user MUST be able to choose the detection mode (background subtraction
  or object detection) and sensitivity level (Low / Medium / High) before starting.
- **FR-018**: The app MUST delete all temporary preview clip files from the system temp
  folder when the application is closed.
- **FR-017**: When a new video file is loaded while the current session has completed
  detection with at least one event and no export has been performed, the app MUST show
  a confirmation dialog giving the user the choice to export first or discard the
  existing session and proceed.
- **FR-016**: On launch, the app MUST check for any incomplete export output file left by
  a previous crashed or force-closed session and delete it automatically before the user
  can start a new job.
- **FR-015**: The Home screen MUST provide an optional "Recording started at" time-of-day
  field (HH:MM:SS). When set, all event cards on the timeline MUST display both the
  wall-clock timestamp (e.g., "02:47:33") and the file-relative position. Individual
  clip filenames MUST include the wall-clock timestamp when this field is set.
- **FR-004**: Detection MUST run in the background and stream live progress, log lines,
  estimated time remaining, and a running count of events found to the user.
- **FR-005**: The user MUST be able to cancel detection at any time; events found up
  to that point MUST be preserved and available for export.
- **FR-006**: The app MUST display each detected event on an interactive timeline strip
  showing its position within the source recording.
- **FR-007**: The user MUST be able to toggle individual events as included or excluded
  from export by clicking their event card on the timeline.
- **FR-008**: The user MUST be able to preview any individual event as a short video
  clip without leaving the timeline view.
- **FR-009**: The app MUST export only the included events, in chronological order,
  to a user-specified folder.
- **FR-010**: The user MUST be able to choose between a single merged output file and
  individual clip files per event before exporting.
- **FR-011**: The user MUST be able to choose output quality: original, 720p, or 480p.
- **FR-012**: The app MUST show a live export progress indicator and notify the user
  when export is complete.
- **FR-013**: The app MUST work on Windows, macOS, and Linux without requiring the user
  to install FFmpeg or any external tool manually.
- **FR-014**: The app MUST include a Quick Export path that skips timeline review and
  exports all detected events immediately after detection completes.

### Key Entities

- **Video Source**: A local video file. Attributes: path, codec, resolution, frame rate,
  duration, audio presence, disk size.
- **Detection Job**: A single run of the motion detector on a source video. Attributes:
  status, progress, detection mode, sensitivity, padding seconds, minimum event duration.
- **Motion Event**: A detected period of activity within a source video. Attributes:
  start time (file-relative), end time (file-relative), wall-clock start time (derived
  from recording start when provided), duration, peak motion score, included/excluded
  flag, label (Person / Vehicle / Animal — object detection mode only).
- **Export**: A conversion of selected events to output video. Attributes: output type
  (merged or individual), quality, output folder, output file path(s).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-01**: A user can go from dropping a 1-hour video onto the app to receiving an
  exported merged file in under 10 minutes on a standard desktop computer (4 cores,
  8 GB RAM) for H.264 source footage.
- **SC-02**: Export of H.264 or HEVC source footage completes in under 30 seconds
  regardless of total source duration or number of events.
- **SC-03**: Detected event timestamps are accurate to within 1 second of the actual
  motion boundary in the source recording.
- **SC-04**: A user can complete the full workflow (drop file → detect → review →
  export) on Windows, macOS, and Linux without installing any external software beyond
  the application itself.
- **SC-05**: When detection finds no events, the user receives a specific, actionable
  diagnostic message within 3 seconds of detection completing.
- **SC-06**: A user can preview any detected event clip within 5 seconds of clicking
  the Preview button.
- **SC-07**: The application launches and is ready for a file drop within 5 seconds on
  a standard desktop computer.
- **SC-08**: Object detection mode correctly identifies motion involving a person in at
  least 9 in 10 test video clips containing a walking person.

---

## Assumptions

- The target user is a home owner, small business owner, or security professional
  reviewing footage from an IP camera or DVR. They are not expected to have technical
  knowledge of video codecs or FFmpeg.
- Videos are local files; no streaming, network, or cloud video sources are in scope
  for this version.
- One video file is processed at a time; batch processing of multiple files is out of
  scope.
- The app retains no history between sessions; closing and reopening the app starts
  fresh with no memory of previous jobs.
- Object detection mode requires an active internet connection on first use to download
  a detection model (~6 MB). Subsequent uses work offline.
- Mobile support is out of scope; the app targets desktop operating systems only.
- The output format for merged exports is MP4 (H.264 video, AAC audio when present).
  Container format selection is out of scope for this version.
- Detection quality may vary for footage recorded in very low light or at frame rates
  below 10 fps; the app is not expected to compensate for these conditions beyond the
  High sensitivity setting.
