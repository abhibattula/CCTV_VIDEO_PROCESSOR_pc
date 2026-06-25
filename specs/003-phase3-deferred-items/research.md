# Phase 0 Research: Phase 3 — Deferred Items Release

All unknowns from the Technical Context were resolved in a prior approved design
session (architecture validated against the actual current code: `session-state.js`,
`timeline.js`, `export.js`, `base.css`, `app/config.py`, `app/session.py`, and the
constitution). This document records the decisions and rejected alternatives.

---

## Decision 1: Constitutional basis for persisting custom presets

**Decision**: Amend Principle I (Session-First, No Persistence) with a narrow
exemption for "user configuration" — named, reusable, user-saved settings with no
reference to any job — rather than treating presets as a special case of job state
or avoiding persistence altogether. Implemented in constitution v1.1.0, already
ratified and committed ahead of this plan.

**Rationale**: The constitution's own stated purpose for Principle I is eliminating
the SQLite crash-on-PC bug (PC-02), which was about *job* state surviving and
corrupting across runs. A saved export preset has no relationship to "the current
job" — it's the same category of thing as the project's own `MODEL_DIR` for cached
YOLO models, which already persists outside the no-persistence principle's scope
without controversy. Drawing this line explicitly (rather than leaving it implicit)
prevents the obvious future loophole of someone reading "small file, should be fine"
and persisting actual job data the same way.

**Alternatives considered**:
- *Don't persist presets at all (session-only)* — rejected: defeats the entire
  point of the feature (FR-P3-002 requires surviving app restarts); a preset that
  vanishes on close is not meaningfully different from manually re-entering settings
  each time.
- *Store presets inside the existing session.py dict* — rejected: `session.py` is
  wiped by `session.reset()` on every new job and discarded entirely on exit by
  design; presets must outlive both.
- *SQLite or another embedded database* — rejected outright: re-introduces exactly
  the class of bug (PC-02) Principle I exists to prevent, for a feature that only
  needs a flat list of small records.

---

## Decision 2: Multi-level undo — capped stack, no redo

**Decision**: Replace the single `uiState.lastBulkOp` slot with a capped array
(`uiState.undoStack`, cap 20), consumed via `push`/`pop`. No redo mechanism.

**Rationale**: The spec text being satisfied is literally "full multi-level undo
history is out of scope" (Phase 2's own deferred wording) — redo was never part of
that ask. Principle V (Simplicity & YAGNI) directly favors not adding a feature
nobody requested, especially one with real design cost (a new bulk op after some
undos must invalidate or merge with a redo stack — standard editor semantics, but
unjustified complexity here). A cap of 20 is generous for a deliberate, button-click
user action (not a high-frequency event like keystrokes) while bounding memory use
even on a 300+ event job.

**Alternatives considered**:
- *Unbounded history* — rejected: no real user benefit beyond ~20 (nobody reviews
  by performing dozens of sequential bulk operations they then need to selectively
  unwind), and removes a trivial safety bound for no reason.
- *Undo + redo* — rejected per Rationale above; can be added later as a clean,
  separately-scoped feature if a real need emerges.
- *Persisting undo history to disk* — rejected: undo history is inherently
  session-scoped (it describes a sequence of actions taken on the currently loaded
  job's events); it is not user configuration and does not fall under the
  constitution's new exemption. It remains in-memory client JS state exactly as
  Phase 2's single-slot version was.

---

## Decision 3: Theme toggle — client-only, no backend involvement

**Decision**: Implement entirely in the frontend — a `localStorage` key and a
`[data-theme="light"]` CSS attribute override block — with zero backend changes.

**Rationale**: Theme preference never needs to leave the browser/WebEngine context:
it doesn't affect what the backend does, isn't read by any API endpoint, and isn't
shared between "sessions" in any sense the constitution cares about. It's the same
category as a browser remembering zoom level. Verified during design that
`QWebEngineView` in this app uses Qt's default (persistent, not off-the-record)
profile — confirmed by the absence of any `QWebEngineProfile`/off-the-record
configuration in `shell/` or `launcher.py` — so `localStorage` will in fact survive
app restarts as required by FR-P3-009.

**Alternatives considered**:
- *Store theme preference server-side (e.g., in a small config file like presets)*
  — rejected: unnecessary backend round-trip and persistence-boundary complexity
  for a value that has no reason to ever leave the browser.
- *OS-theme auto-detection* — rejected per spec Assumptions: out of scope, no
  request for it, adds a third state (auto/light/dark) for no current user story.
