/**
 * Shared UI state singleton for Phase 2.
 * Imported as an ES module — same object reference survives SPA navigation
 * within a session. Reset explicitly on new job creation.
 */

const _state = {
  labelFilter:     new Set(),   // active label strings; empty = show all
  scoreThreshold:  0.0,         // events below this are hidden
  selectedIndices: new Set(),   // multi-select event indices
  lastBulkOp:      null,        // { indices: number[], prevIncluded: boolean[] }
};

export const uiState = _state;

export function resetUiState() {
  _state.labelFilter     = new Set();
  _state.scoreThreshold  = 0.0;
  _state.selectedIndices = new Set();
  _state.lastBulkOp      = null;
}
