# Data Model: Phase 3 — Deferred Items Release

## UndoHistoryEntry

Replaces Phase 2's single `lastBulkOp` slot. Lives in `static/js/session-state.js`'s
`uiState.undoStack` — an ordered array, newest entry at the end, capped at
`UNDO_STACK_CAP = 20` (oldest dropped via `shift()` when exceeded).

| Field | Type | Description |
|---|---|---|
| `indices` | `number[]` | Event indices affected by the bulk operation |
| `prevIncluded` | `boolean[]` | Each affected event's `included` value immediately *before* the operation, same order as `indices` |

**Lifecycle**: Pushed by `bulkToggle()` before the PUT request; popped (consumed,
removed) by `undoBulk()` when the user undoes that step. Cleared entirely only by
`resetUiState()` (new job loaded). **Not** cleared by `clearSelection()` (Escape /
empty-area click) — this is the Phase 3 fix to a Phase 2 coupling bug (FR-P3-007).
Session-scoped only; never persisted to disk.

---

## ExportPreset (custom)

A user-saved, reusable export configuration. Persisted as a flat JSON list at
`~/.cctv_processor/presets.json` (`app/config.py:PRESETS_FILE`), under the
constitution v1.1.0 user-configuration exemption.

| Field | Type | Description | Validation |
|---|---|---|---|
| `name` | `string` | Display name and unique identifier | Non-empty after trim; must not equal "Security Report", "Evidence Pack", or "Quick Highlights"; must not match an existing custom preset's name |
| `output_type` | `string` | `"merged"` or `"individual"` | Matches `ExportRequest.output_type` in `app/api/job.py` |
| `quality` | `string` | `"original"`, `"720p"`, or `"480p"` | Matches `ExportRequest.quality` |
| `burn_in` | `boolean` | Whether the timestamp/label overlay is applied | Matches `ExportRequest.burn_in` |
| `label_filter` | `string[]` | Labels to restrict export to; empty = all labels | Matches `ExportRequest.label_filter` |

**Relationship to Phase 2's built-in presets**: The 3 built-in presets (Security
Report / Evidence Pack / Quick Highlights) are unchanged, remain hardcoded in
`export.js`, and are NOT represented in this data model or in `presets.json` — they
are a disjoint, reserved namespace that custom preset names may not collide with.

**Deliberately excluded field**: `auto_top_n` (the "select top N events by score"
behavior behind the built-in "Quick Highlights" preset) — there is no existing UI
control to customize N, and custom presets only capture settings a user can already
see and edit on the export page today (per spec Assumptions).

**Failure mode**: If `presets.json` is missing, deleted, or fails to parse, the
backend's `_load()` returns an empty list — zero custom presets, not an error. The
3 built-in presets are entirely unaffected since they don't live in this file.

---

## ThemePreference

| Field | Type | Description |
|---|---|---|
| `cctv-theme` (localStorage key) | `"dark"` \| `"light"` | The user's selected theme |

**Storage**: Browser/WebEngine `localStorage`, keyed by `"cctv-theme"`. Defaults to
`"dark"` if absent (preserves current behavior for existing users). Never read or
written by the Python backend — applied entirely via a `data-theme` attribute on
`<html>` plus the CSS override block in `base.css`.

**Explicitly not user configuration in the `ExportPreset` sense**: it never crosses
into `app/api/*`, never touches `PRESETS_FILE`, and is outside the constitution's
Principle I scope entirely (which governs `app/session.py` job state) rather than
being an instance of the new exemption.
