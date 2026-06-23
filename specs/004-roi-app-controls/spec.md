# Feature Specification: Phase 4 — ROI Selection, Stop Application, New Project

**Feature Branch**: `004-roi-app-controls`
**Created**: 2026-06-23
**Status**: Draft
**Builds on**: Phase 1 (`001-cctv-pc-processor`), Phase 2 (`002-ui-tag-filter`), Phase 3
(`003-phase3-deferred-items`) — detection, timeline review, multi-level undo, custom
export presets, and light theme are complete and working
**Input**: User description: "Phase 4 — ROI selection, Stop Application, and New
Project button. (1) ROI selection: on the Home page, after a video file is loaded,
show a first-frame preview and let the user draw one or more free-form polygon
zones on it; detection only analyzes activity inside the drawn zones (full frame if
none are drawn); zones are per-job only, not saved/reused across videos. (2) Stop
Application: a button visible on every page that, after a confirmation dialog
warning any in-progress work will be cancelled, gracefully stops the backend server
while the application window remains open and displays a message confirming it is
now safe to close the window. (3) New Project button: a button visible on every
page that lets the user abandon/cancel the current job (with a warning if work is
in progress or unexported results exist) and return to the upload screen to start
over, without restarting the whole application."

---

## Overview

The app today analyzes the entire video frame for motion/object activity, has no
in-app way to fully stop the backend (closing the window leaves it running in the
background), and has no dedicated way to abandon the current job and start a
different video without restarting the whole program. This feature adds three
independent capabilities: drawing regions to restrict detection to areas of
interest, a controlled way to shut the application down from within the UI, and a
one-click way to start over with a new video from any page.

---

## User Scenarios & Testing

### User Story 1 - Restrict Detection to Regions of Interest (Priority: P1)

A security reviewer points a camera at a parking lot but only cares about activity
at the entrance gate — the rest of the frame (trees swaying, a busy street in the
background) creates false positives today. After loading the video, they see a
preview of its first frame and draw a shape around just the gate area. When
detection runs, only activity inside that shape is reported as events.

**Why this priority**: Directly reduces false positives and review time for the
most common real-world camera framing problem (irrelevant background motion); the
backend's masking logic already exists and is unused today, making this the
highest-value, lowest-risk story to ship first.

**Independent Test**: Load a video with motion both inside and outside a drawn
region; run detection; confirm only the region-internal motion produces events, and
that running the same video with no regions drawn still detects everywhere as today.

**Acceptance Scenarios**:

1. **Given** a video has just been loaded and analyzed, **When** the user views the
   Home page, **Then** a preview image of the video's first frame is shown
   alongside the existing detection settings
2. **Given** the first-frame preview is visible, **When** the user clicks to place
   points and closes the shape near its starting point, **Then** a completed region
   appears, shown as an outlined, semi-transparent shape over the preview
3. **Given** one or more regions are drawn, **When** the user starts detection,
   **Then** only motion/object activity inside the drawn region(s) is reported as
   events
4. **Given** no regions are drawn, **When** the user starts detection, **Then** the
   entire frame is analyzed, exactly as it behaves today
5. **Given** at least one region is drawn, **When** the user deletes it or clicks
   "Clear All", **Then** it no longer affects the next detection run
6. **Given** regions were drawn for one video, **When** the user loads a different
   video file, **Then** the previous regions are cleared and the new video's own
   first frame is shown with no regions pre-drawn

---

### User Story 2 - Stop the Application From Within the UI (Priority: P2)

A user is done reviewing footage for the day and wants to make sure the application
has fully stopped running — not just hidden — before they walk away from the
machine. Today, closing the window doesn't actually stop anything; it keeps running
invisibly. They click a "Stop" control, confirm they want to proceed, and the app
tells them once it's actually safe to close the window.

**Why this priority**: A trust and resource-hygiene issue (an invisible background
process is a real, recurring complaint) but narrower in day-to-day value than the
detection-accuracy improvement in US1.

**Independent Test**: With the app running (optionally mid-detection), click Stop,
confirm, and verify the application backend is no longer reachable/responding while
the window itself remains open and displays a "safe to close" message; then close
the window manually.

**Acceptance Scenarios**:

1. **Given** the application is running, **When** the user clicks the Stop
   control, **Then** a confirmation dialog explains that any in-progress work will
   be cancelled and asks them to confirm
2. **Given** the user confirms, **When** the stop proceeds, **Then** any
   in-progress detection or export is cancelled first, and the application becomes
   unresponsive to further requests within a few seconds
3. **Given** the stop has completed, **When** the user looks at the window,
   **Then** it displays a clear message confirming the application has stopped and
   that it is now safe to close the window, and the window itself remains open
   until the user closes it
4. **Given** the confirmation dialog is open, **When** the user cancels instead of
   confirming, **Then** nothing is stopped and the application continues operating
   normally

---

### User Story 3 - Start a New Project Without Restarting (Priority: P3)

A user finishes reviewing one video's events, exports the highlights, and wants to
immediately load a different video — or realizes partway through review that they
loaded the wrong file. Instead of closing and reopening the whole application, they
click "New Project" from wherever they are, confirm if asked, and land back on the
upload screen ready to load a different file.

**Why this priority**: A genuine convenience improvement, but the most common path
(loading a new file from the Home page when no other job is active) already works
today — this story mainly closes a discoverability gap and a race-condition edge
case rather than adding fundamentally new capability.

**Independent Test**: From the Timeline or Export page, with a job in some active
or completed state, click "New Project," confirm if a warning appears, and verify
the app returns to a clean upload screen with no leftover state from the previous
job.

**Acceptance Scenarios**:

1. **Given** the user is on any page (Home, Processing, Timeline, Export), **When**
   they look for a way to start over, **Then** a "New Project" control is visible
   and reachable without navigating away first
2. **Given** detection or export is actively running, **When** the user clicks
   "New Project," **Then** a warning explains that the in-progress operation will
   be cancelled, and only proceeds on confirmation
3. **Given** a completed job has events that have not yet been exported, **When**
   the user clicks "New Project," **Then** a warning explains that those results
   will be discarded, and only proceeds on confirmation
4. **Given** the current job is idle, freshly loaded, or already exported, **When**
   the user clicks "New Project," **Then** the app returns to the upload screen
   immediately with no warning
5. **Given** the user has returned to the upload screen via "New Project," **When**
   they load a new video file, **Then** none of the previous job's events,
   selections, filters, or undo history remain

---

### Edge Cases

- The video's first frame cannot be extracted (corrupted file, zero-duration clip)
  → the Home page shows a message that the preview is unavailable and detection
  still runs on the full frame, exactly as if no regions were ever drawn
- A region is drawn that is extremely small, a thin sliver, or has self-crossing
  edges → the system accepts it without error; it simply may not match much (or
  any) activity, which is the user's own drawing choice, not a system failure
- The user clicks Stop while a region is mid-drawing (not yet closed into a shape)
  → the in-progress shape is simply discarded along with everything else; no
  special handling needed
- The user clicks New Project while a region is mid-drawing on the Home page →
  same as above, discarded as part of returning to a clean upload screen
- The Stop confirmation is accepted but the application is slow to fully stop (e.g.
  a large export was mid-write) → the "safe to close" message only appears once the
  application is confirmed unresponsive, not optimistically shown before that
- The user clicks New Project immediately after clicking Stop (or vice versa) →
  Stop takes precedence: once a stop has been confirmed, the application is
  shutting down and no further job actions are meaningful
- A region's points are drawn at the very edge of the frame → treated like any
  other valid region, no special edge-of-frame handling needed

---

## Requirements

### Functional Requirements

**ROI Selection (US1)**

- **FR-P4-001**: After a video is loaded, the system MUST display a preview image
  representing the video's first frame
- **FR-P4-002**: The system MUST allow the user to draw one or more closed,
  free-form regions over the preview image by placing a sequence of points
- **FR-P4-003**: The system MUST allow the user to remove an individual drawn
  region, or clear all drawn regions, before starting detection
- **FR-P4-004**: When detection runs with one or more regions drawn, the system
  MUST report activity only from within those region(s); when no regions are
  drawn, the system MUST analyze the entire frame, matching today's behavior
  exactly
- **FR-P4-005**: Drawn regions MUST apply only to the video they were drawn on;
  loading a different video MUST clear any previously drawn regions and show that
  video's own first frame

**Stop Application (US2)**

- **FR-P4-006**: The system MUST provide a control, reachable from every page,
  that initiates stopping the application
- **FR-P4-007**: Before stopping, the system MUST ask the user to confirm,
  explaining that any in-progress detection or export will be cancelled
- **FR-P4-008**: On confirmation, the system MUST cancel any in-progress detection
  or export before stopping
- **FR-P4-009**: Once stopped, the system MUST display a message confirming it is
  safe to close the application window; the window MUST remain open until the user
  closes it themselves
- **FR-P4-010**: Declining the confirmation MUST leave the application running
  normally with no side effects

**New Project (US3)**

- **FR-P4-011**: The system MUST provide a control, reachable from every page,
  that returns the user to the upload screen to start a new project
- **FR-P4-012**: If detection or export is actively running, the system MUST warn
  the user that proceeding will cancel it, and only proceed on confirmation
- **FR-P4-013**: If the current job has completed with events that have not been
  exported, the system MUST warn the user that proceeding will discard them, and
  only proceed on confirmation
- **FR-P4-014**: If neither condition in FR-P4-012/013 applies, the system MUST
  return to the upload screen immediately without a warning
- **FR-P4-015**: After returning to the upload screen via New Project, no events,
  selections, filters, or undo history from the previous job MUST remain once a
  new video is loaded

### Key Entities

- **DetectionRegion**: A single user-drawn shape (an ordered sequence of points
  forming a closed boundary) used to restrict where detection looks for activity.
  Exists only for the lifetime of the current job — never saved, never reused
  across videos.
- **ApplicationRunState**: Whether the application backend is currently running or
  has been stopped. Not data the user manages directly — only observed via the
  Stop control's confirmation and result message.

---

## Success Criteria

### Measurable Outcomes

- **SC-P4-001**: A user can draw a region and confirm it is being respected within
  a single detection run (no need to re-run twice to "make it take effect")
- **SC-P4-002**: With a region drawn around the only area of real activity in a
  test video, detection produces zero events from outside that region
- **SC-P4-003**: After confirming Stop, the application is no longer responding to
  any new actions within 15 seconds, and the user is shown a clear confirmation
  message
- **SC-P4-004**: A user can move from "reviewing one finished video" to "ready to
  load a different one" via New Project in under 5 seconds, without the
  application restarting
- **SC-P4-005**: 100% of the time, starting a new project after a completed job
  results in zero leftover events, selections, or filters from the prior job once
  the new video is analyzed

---

## Assumptions

- Regions are not saved or reusable across different videos or app restarts — each
  video starts with a blank slate, consistent with the user's explicit choice for
  this phase
- Only one region "mode" exists (free-form shapes); a separate, simpler
  rectangle-drawing mode is not offered alongside it
- Stopping the application is a deliberate, infrequent action gated behind a
  confirmation step — there is no "quick stop" without confirmation
- The "safe to close" message is sufficient feedback; the application does not
  need to close its own window automatically once stopped
- New Project's warnings cover only the two cases that lose real user work (an
  active operation, or unexported completed results) — an idle, freshly-loaded, or
  already-exported job requires no warning
- This feature does not change anything about how a single job behaves once
  detection starts (mode, sensitivity, padding, etc.) — it only adds where
  detection looks, and how the overall application/session lifecycle is controlled
