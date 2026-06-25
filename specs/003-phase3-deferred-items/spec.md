# Feature Specification: Phase 3 — Deferred Items Release

**Feature Branch**: `003-phase3-deferred-items`
**Created**: 2026-06-21
**Status**: Draft
**Builds on**: Phase 1 (`001-cctv-pc-processor`) and Phase 2 (`002-ui-tag-filter`) —
detection, timeline review, single-level undo, and export presets are complete and
working
**Input**: User description: "Phase 3 — Deferred Items Release: three features
explicitly deferred from Phase 2 (specs/002-ui-tag-filter/spec.md Assumptions
section) — multi-level undo history, custom export presets, and a light theme
toggle."

---

## Overview

Phase 2 shipped single-level undo, three fixed export presets, and a dark-only
theme — and explicitly deferred deepening each of these to "Phase 3" in its own
spec. This feature delivers on that deferral: a multi-step undo history on the
Timeline page, the ability to save and reuse custom export configurations, and a
light theme option. None of the three depend on each other and each is a complete,
independently shippable slice of value.

---

## User Scenarios & Testing

### User Story 1 — Custom Export Presets (Priority: P1)

A security manager exports footage the same way every week: merged, 720p, burn-in
on, filtered to "Person." Today they re-configure all four settings by hand on every
job. They configure it once, click "Save as Preset," name it "Weekly Person Report,"
and from then on — including after closing and reopening the app — it appears as a
one-click button next to the built-in presets on every future job.

**Why this priority**: Phase 2 already proved one-click presets save real time
(Security Report / Evidence Pack / Quick Highlights); letting users define their own
extends that value to whatever workflow they actually repeat, which is the
highest-value, most-requested gap left over from Phase 2.

**Independent Test**: Configure export settings, save as a named preset, close and
reopen the app, confirm the preset still appears and applies the saved settings in
one click. Delete it and confirm it's gone.

**Acceptance Scenarios**:

1. **Given** the export page with output type, quality, burn-in, and label filter
   configured, **When** the user saves these as a preset named "Weekly Person
   Report", **Then** a new preset button with that name appears next to the 3
   built-in presets
2. **Given** a saved custom preset, **When** the app is fully closed and reopened
   and a new job is loaded, **Then** the custom preset button is still present and
   clicking it applies the exact saved settings
3. **Given** a custom preset already named "Weekly Person Report", **When** the
   user tries to save another preset with the same name, **Then** the save is
   rejected with a message explaining the name is taken
4. **Given** the user tries to name a custom preset "Security Report" (a built-in
   name), **When** they attempt to save it, **Then** the save is rejected for the
   same reason
5. **Given** a custom preset exists, **When** the user deletes it, **Then** it no
   longer appears in the preset row, and the 3 built-in presets are unaffected

---

### User Story 2 — Multi-Level Undo History (Priority: P2)

An operator reviews 80 events, bulk-excludes a group of false positives, then
bulk-excludes a second unrelated group a minute later. They realize the first
exclusion was also a mistake. Today, only the second (most recent) bulk operation
can be undone — the first is unrecoverable. With multi-level undo, pressing
Ctrl+Z (or the Undo button) twice reverts both operations, one at a time, in
reverse order.

**Why this priority**: Builds directly on Phase 2's single-level undo; the value is
real but narrower than US1 (most review sessions involve few enough bulk operations
that one level is usually enough — this closes the remaining gap for the rest).

**Independent Test**: Perform 3 separate bulk-exclude operations on different event
groups. Press Undo three times. Confirm each press reverts exactly one operation, in
reverse chronological order, and the Undo button becomes disabled only after all
three are reverted.

**Acceptance Scenarios**:

1. **Given** 3 bulk operations performed in sequence, **When** Undo is pressed once,
   **Then** only the most recent operation is reverted and the Undo button remains
   enabled (2 operations still undoable)
2. **Given** all undo history has been exhausted, **When** Undo is pressed again,
   **Then** nothing happens and the button is disabled
3. **Given** an active multi-select with undo history present, **When** Escape is
   pressed to clear the selection, **Then** the selection clears but the undo
   history is NOT affected — a subsequent Undo still works
4. **Given** at least one undoable operation exists, **When** the user looks at the
   Undo button, **Then** they can tell undo is available (and Phase 2's existing
   single-press-undo behavior is otherwise unchanged)

---

### User Story 3 — Light Theme Toggle (Priority: P3)

A user reviews footage in a brightly lit room and finds the dark theme hard to read.
They click a theme toggle in the navigation bar; the entire UI switches to a light
colour scheme immediately, on every page. The next time they open the app, it
remembers their choice.

**Why this priority**: A preference/accessibility feature with broad but shallow
appeal — valuable, but it doesn't change what the app can do, only how it looks.

**Independent Test**: Click the theme toggle on any page, confirm all visible pages
switch to light colours immediately. Restart the app and confirm the choice
persisted.

**Acceptance Scenarios**:

1. **Given** the app is in dark theme (the default), **When** the user clicks the
   theme toggle, **Then** the UI switches to light theme on the current page
   immediately, with no reload
2. **Given** light theme is active, **When** the user navigates to a different page
   (Home/Processing/Timeline/Export), **Then** that page also renders in light theme
3. **Given** light theme was selected, **When** the app is closed and reopened,
   **Then** it opens in light theme without the user re-selecting it
4. **Given** either theme, **When** the user looks at a confidence badge or label
   pill, **Then** its colour-coding (green/amber/red, Person=blue, etc.) means the
   same thing in both themes

---

### Edge Cases

- A custom preset is saved with an empty or whitespace-only name → rejected, same as
  a duplicate name
- The presets configuration file is missing, deleted, or corrupted on disk → the app
  starts normally with zero custom presets (not an error state); the 3 built-in
  presets are always available regardless
- A custom preset references a label that no longer exists in the current job (e.g.
  saved while reviewing Object Detection footage, applied later to a MOG2-only job)
  → applying it sets the label filter as saved; if no events match, the existing
  Phase 2 "no events match this filter"-style empty state already handles this,
  nothing new needed
- The user performs a bulk operation, then a single-card toggle, then tries Undo →
  Undo only ever reverts bulk operations (Phase 2 scope); a single-card toggle is
  not added to the undo history, consistent with today's single-level behavior
- The user switches theme while a modal (e.g. event preview) is open → the modal
  re-themes along with the rest of the page, since it uses the same CSS custom
  properties
- The user undoes a bulk operation while a label/score filter is currently hiding
  some of the affected events → the included/excluded state of ALL affected events
  reverts regardless of current filter visibility (undo acts on data, the filter is
  just a view); the toolbar's "N shown / M total" count updates accordingly, even if
  some reverted events remain hidden by the active filter
- The user performs an Undo while a multi-selection is active → Undo does not
  change the current selection in any way; only the previously-applied
  include/exclude operation is reverted
- A new job is loaded while undo history exists from the previous job → undo
  history is cleared along with all other session-scoped UI state, consistent with
  Phase 2's existing reset-on-new-job behavior
- The client-side storage used for theme preference is unavailable (e.g. blocked by
  browser/profile settings) → the toggle still switches the current session's theme
  normally; only cross-restart persistence is lost, not the feature itself

---

## Requirements

### Functional Requirements

**Custom Export Presets (US1)**

- **FR-P3-001**: The export page MUST allow the user to save the currently
  configured output type, quality, burn-in setting, and label filter — and exactly
  these four settings, nothing else — as a named preset
- **FR-P3-002**: Saved custom presets MUST appear as additional one-click buttons
  alongside the 3 built-in presets, and MUST persist across app restarts
- **FR-P3-003**: The system MUST reject saving a custom preset whose name, after
  trimming leading/trailing whitespace, is empty, OR matches — case-insensitively —
  another custom preset's name or a built-in preset name ("Security Report",
  "Evidence Pack", "Quick Highlights"). Whitespace-trimming and case-insensitivity
  both apply to this comparison (e.g. "weekly report " collides with "Weekly
  Report")
- **FR-P3-004**: The user MUST be able to delete a custom preset they created;
  deleting a custom preset MUST NOT affect the 3 built-in presets or any other
  custom preset

**Multi-Level Undo History (US2)**

- **FR-P3-005**: The timeline page MUST maintain a history of bulk include/exclude
  operations (not just the single most recent one) and allow reverting them one at
  a time, most recent first
- **FR-P3-006**: The Undo control MUST be disabled exactly when no undo history
  remains, and MUST indicate that undo is unavailable in that state
- **FR-P3-007**: Clearing the current multi-selection (Escape, or clicking empty
  list space) MUST NOT clear undo history — these are independent pieces of state

**Light Theme Toggle (US3)**

- **FR-P3-008**: The navigation bar MUST expose a control, visible on every page,
  that switches between dark and light themes immediately with no page reload
- **FR-P3-009**: The selected theme MUST persist across app restarts
- **FR-P3-010**: Semantic colours (confidence badges, label pills, status colours)
  MUST convey the same meaning in both themes, even if the exact shades differ

### Key Entities

- **UndoHistoryEntry**: One reverted-bulk-operation record — the set of event
  indices affected and their included/excluded state immediately before the
  operation. A session-scoped ordered collection of these (not persisted between
  app launches) replaces Phase 2's single `lastBulkOp` slot.
- **ExportPreset (custom)**: A named, user-saved export configuration — name, output
  type, quality, burn-in on/off, label filter. Persisted as user configuration
  (distinct from job state) so it survives app restarts; the 3 built-in presets from
  Phase 2 are unchanged and remain separate from user-saved ones.
- **ThemePreference**: The user's selected theme (dark/light). Stored client-side
  only; not job state, not user configuration in the export-preset sense — it never
  crosses into the backend at all.

---

## Success Criteria

### Measurable Outcomes

- **SC-P3-001**: A user can save their current export configuration as a reusable
  preset in under 10 seconds
- **SC-P3-002**: A saved custom preset is still available and correctly configured
  after fully closing and reopening the application
- **SC-P3-003**: A user who performed 3 bulk operations can revert all 3, one at a
  time, ending back at the exact state before any of them were performed
- **SC-P3-004**: Switching theme takes effect in under 100ms, measured from click to
  the new colours being visible, with no full page reload (the page's content
  remains scrolled to the same position and no network request is made)
- **SC-P3-005**: A returning user's theme choice is correctly restored on 100% of
  app launches following a restart

---

## Assumptions

- No redo is provided for undo history — only the spec text already deferred from
  Phase 2 ("full multi-level undo") is in scope; redo was never requested and adds
  state-management complexity (what happens to the redo stack after a new bulk
  operation) without a corresponding user story
- The undo history is capped at a reasonable bound (not unbounded) purely as a
  memory-safety measure for very long review sessions; this bound is an
  implementation detail, not user-facing behavior, and is not expected to be reached
  in normal use
- Custom presets do not support "auto top-N" event auto-selection (the mechanism
  behind Phase 2's built-in "Quick Highlights" preset) — there is no existing UI
  control to customize the N, and adding one is a separate feature; custom presets
  save only the four settings users can already see and edit today
- The number of custom presets a user can save is not capped in this phase — if
  this becomes a real usability problem (e.g. dozens of presets cluttering the
  export page) it is a follow-up, not a blocker for this release
- Theme choice is a single global on/off toggle (dark/light); there is no
  "auto-match OS theme" option, consistent with keeping scope to what was explicitly
  deferred
- Deleting a custom preset is immediate (no undo for the deletion itself), matching
  how the rest of this app treats destructive user-initiated actions
- Custom export presets are user configuration, explicitly distinct from job state,
  per the Phase 3 constitution amendment (v1.1.0) to Principle I — this is an
  accepted, already-resolved architectural decision, not an open question
