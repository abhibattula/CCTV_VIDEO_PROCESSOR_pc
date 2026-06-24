/**
 * Shared UI state singleton for Phase 2.
 * Imported as an ES module — same object reference survives SPA navigation
 * within a session. Reset explicitly on new job creation.
 */

const _state = {
  labelFilter:     new Set(),   // active label strings; empty = show all
  scoreThreshold:  0.0,         // events below this are hidden
  selectedIndices: new Set(),   // multi-select event indices
  undoStack:       [],          // { indices, prevIncluded }[], newest at end, cap 20
};

// Set by New Project just before navigating to "/", so Home's mount-time
// existing-job restore (see static/js/pages/home.js) knows to skip restoring
// a job the user just explicitly discarded — even though the backend leaves
// status:"cancelled" with the stale job_id/source_path still populated
// (there is no backend endpoint that fully clears session back to "idle"
// without a new source_path). Read-and-clear: consumed exactly once by the
// next Home mount.
let _justReset = false;

export const UNDO_STACK_CAP = 20;
export const uiState = _state;

export function resetUiState() {
  _state.labelFilter     = new Set();
  _state.scoreThreshold  = 0.0;
  _state.selectedIndices = new Set();
  _state.undoStack       = [];
}

export function markJustReset() {
  _justReset = true;
}

export function consumeJustReset() {
  const v = _justReset;
  _justReset = false;
  return v;
}
