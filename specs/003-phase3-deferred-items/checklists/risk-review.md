# Risk Review Checklist: Phase 3 — Deferred Items Release

**Purpose**: Validate requirements quality (completeness, clarity, consistency) on
the four riskiest/newest aspects of this feature before implementation begins: the
constitution exemption boundary, preset name-collision rules, undo-history
correctness, and theme persistence/consistency.
**Created**: 2026-06-21
**Feature**: [spec.md](../spec.md), [plan.md](../plan.md), [data-model.md](../data-model.md)

**Note**: This checklist tests the REQUIREMENTS, not the implementation — it asks
whether spec.md/plan.md/data-model.md say enough, clearly enough, not whether code
behaves correctly. All items below were resolved during the same pass that found
them (see Notes) — none are left open going into `/speckit.tasks`.

---

## Constitution Exemption Boundary

- [X] CHK001 - Does the data model explicitly cross-reference the constitution's
  Principle I boundary rule (no `_DEFAULTS` keys in a persisted preset), or could a
  future field addition to `ExportPreset` silently violate it without a documented
  check? [Traceability, data-model.md §ExportPreset] — **Resolved**: added an
  explicit boundary-rule callout directly above the field table.
- [X] CHK002 - Does FR-P3-001 explicitly preclude storing any field beyond the four
  named ones (output_type, quality, burn_in, label_filter), even if a future client
  request included additional data? [Clarity, Spec §FR-P3-001] — **Resolved**:
  FR-P3-001 now reads "...and exactly these four settings, nothing else."
- [X] CHK003 - Is the "user configuration vs. job state" distinction defined with a
  testable rule (e.g., "has no reference to any job ID") rather than only by example
  ("e.g. export presets")? [Clarity, Spec §Key Entities] — Already adequately
  defined: the constitution's own Principle I exemption text (referenced by the
  spec) states the rule structurally ("MUST NOT store any key present in
  `_DEFAULTS`"), not just by example.

## Preset Name-Collision Rules

- [X] CHK004 - Is preset name collision checking specified as case-sensitive or
  case-insensitive? "Security report" vs. "Security Report" is not addressed.
  [Ambiguity, Spec §FR-P3-003] — **Resolved**: FR-P3-003 now specifies
  case-insensitive comparison explicitly; plan.md and contracts/api.md updated to
  match.
- [X] CHK005 - Does the spec state whether leading/trailing whitespace is trimmed
  before the collision check, such that "Weekly Report " and "Weekly Report" are
  treated as the same name? [Gap, Spec §FR-P3-003] — **Resolved**: FR-P3-003 now
  states trimming happens before comparison, with a worked example.
- [X] CHK006 - Are the 3 built-in preset names treated as a fixed, closed list
  anywhere a future built-in preset could be added — i.e., is there a single source
  of truth referenced, or could spec and implementation drift independently?
  [Consistency, Spec §FR-P3-003] — Already adequate: the literal 3-name list is
  stated once in FR-P3-003 and referenced (not re-enumerated) everywhere else
  (data-model.md, contracts/api.md, plan.md's `BUILTIN_PRESET_NAMES` constant).

## Undo-History Correctness

- [X] CHK007 - Does the spec define how Undo behaves when the events affected by the
  reverted bulk operation are currently hidden by an active label/score filter (do
  they revert silently, or does the filter change to reveal them)? [Gap, Edge Case]
  — **Resolved**: new Edge Case bullet added — undo acts on data regardless of
  current filter visibility.
- [X] CHK008 - Is the undo history's cap (mentioned only as "a reasonable bound" in
  Assumptions) explicitly confirmed as a non-user-facing implementation detail, with
  no acceptance scenario that could be affected by its exact value? [Consistency,
  Spec §Assumptions] — Already adequate, stated explicitly in Assumptions.
- [X] CHK009 - Does FR-P3-007 (clearing selection must not clear undo history)
  have a corresponding acceptance scenario that also covers the reverse — does
  performing an Undo affect the current multi-selection state, and is that defined?
  [Gap, Spec §US2] — **Resolved**: new Edge Case bullet — Undo never changes the
  current selection.
- [X] CHK010 - Is it specified what happens to undo history when a new job is
  loaded mid-session (does it reset, same as Phase 2's single-slot behavior)?
  [Gap, Edge Case] — **Resolved**: new Edge Case bullet added.

## Theme Persistence & Consistency

- [X] CHK011 - Does the spec define fallback behavior if the client-side storage
  mechanism for theme preference is unavailable (e.g., disabled by browser/profile
  settings), or does it implicitly assume storage always succeeds? [Gap, Exception
  Flow] — **Resolved**: new Edge Case bullet — toggle still works for the session,
  only cross-restart persistence is lost.
- [X] CHK012 - Is "every page" in FR-P3-008 exhaustively bounded by the page list
  used elsewhere in this spec (Home/Processing/Timeline/Export), or could a future
  page be added without an explicit requirement to include the toggle? [Consistency,
  Spec §FR-P3-008] — Already adequate: US3's Acceptance Scenario 2 explicitly
  enumerates all four current pages.
- [X] CHK013 - Is SC-P3-004's "<100ms, no flash of unstyled content" measurable by
  an external observer without implementation knowledge (i.e., is "flash of
  unstyled content" given any objective definition)? [Measurability, Spec §SC-P3-004]
  — **Resolved**: reworded to "click to new colours visible... no full page reload
  (same scroll position, no network request)" — each clause is independently
  observable without implementation knowledge.

## Cross-Cutting Requirement Quality

- [X] CHK014 - Are all three user stories (US1/US2/US3) confirmed independent of
  each other in the spec, with no acceptance scenario in one implicitly depending on
  another being implemented first? [Consistency, Spec §Overview] — Already
  adequate: Overview states this explicitly.
- [X] CHK015 - Does the spec distinguish, for each of the three new entities
  (UndoHistoryEntry, ExportPreset custom, ThemePreference), which is session-scoped,
  which is disk-persisted, and which is browser-storage-only — and is this
  consistent between spec.md's Key Entities and data-model.md? [Consistency] —
  Already adequate and consistent between both documents.

## Notes

- 8 of 15 items required an actual spec/plan/contract edit (CHK001, CHK002, CHK004,
  CHK005, CHK007, CHK009, CHK010, CHK011, CHK013 — 9 total); the remaining 6 were
  already adequately covered on inspection. All edits were applied directly to
  `spec.md`, `data-model.md`, `plan.md`, and `contracts/api.md` in this same pass
  rather than left as open follow-ups, per the project's "fix issues before moving
  forward" working style for this feature.
- No items remain open. Safe to proceed to `/speckit.tasks`.
