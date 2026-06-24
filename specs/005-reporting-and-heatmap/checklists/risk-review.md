# Risk-Review Checklist: Phase 5 — Professional Reporting & Activity Insights

**Purpose**: Validate the requirements quality of `spec.md` before `/speckit.tasks` — same risk-review style used for Phase 3 and Phase 4. Tests the *requirements*, not the implementation.
**Created**: 2026-06-23
**Feature**: [spec.md](../spec.md)

## Requirement Completeness

- [x] CHK001 Are requirements defined for which job statuses (e.g. mid-detection, mid-export) the report/heatmap/data-export actions are or aren't available from, beyond "a detection run has completed"? [Gap, Spec §FR-P5-001, §FR-P5-009, §FR-P5-015] — **Resolved**: new FR-P5-020.
- [x] CHK002 Are requirements defined for any user-visible feedback during the interval between requesting the report and the file actually appearing? [Gap, Spec §FR-P5-001] — **Resolved**: new FR-P5-021.
- [x] CHK003 Are requirements defined for confirming a report or data-export request actually succeeded, versus failing silently? [Gap] — **Resolved**: new FR-P5-021.
- [x] CHK004 Are requirements defined for source video files that no longer exist on disk at the time a report is generated (e.g. moved or deleted after the job was created)? [Gap, Edge Case] — **Resolved**: new FR-P5-022 + new Edge Case bullet.
- [x] CHK005 Are requirements defined for an output folder that is missing, unwritable, or on a disconnected removable drive at the moment a report or data export is requested? [Gap, Edge Case] — **Resolved**: new FR-P5-022 + new Edge Case bullet.
- [x] CHK006 Are requirements defined for the case where the exported video file referenced by the chain-of-custody hash (FR-P5-005) has itself been deleted or moved since the export completed? [Gap, Spec §FR-P5-005] — **Resolved**: new FR-P5-022 + new Edge Case bullet.
- [x] CHK007 Are requirements defined for whether the heatmap is replaced or accumulated if the user re-runs detection a second time on the same already-loaded video within the same job? [Gap, Spec §FR-P5-014] — **Resolved**: FR-P5-014 now states it replaces rather than accumulates.
- [x] CHK008 Are requirements defined for what happens if the same report or data-export request is submitted twice before the first one finishes? [Gap, Edge Case] — **Resolved**: new FR-P5-021 (disables the triggering control while in progress).

## Requirement Clarity

- [x] CHK009 Is "a recognizable, non-colliding filename" (FR-P5-007) specific enough that two different reasonable implementations couldn't both claim compliance while producing incompatible naming schemes? [Clarity, Spec §FR-P5-007] — **Resolved**: FR-P5-007 now specifies a timestamp precise enough to guarantee no collision.
- [x] CHK010 Is "where activity concentrated" (FR-P5-009) specific enough about the visual encoding expected (e.g. a continuous color gradient versus discrete markers) to constrain acceptance testing? [Ambiguity, Spec §FR-P5-009] — **Resolved**: FR-P5-009 now specifies a continuous color gradient explicitly.
- [x] CHK011 Does the spec define, in observable terms, what "clearly indicates there is nothing to report/export" (FR-P5-008, FR-P5-017) requires — e.g. whether a disabled control alone satisfies it, or an explicit message is required? [Ambiguity, Spec §FR-P5-008, §FR-P5-017] — **Resolved**: both FRs now require an explicit, visible message, not merely a disabled control.

## Requirement Consistency

- [x] CHK012 Do FR-P5-003 (report) and FR-P5-016 (data export) both rely on the same definition of "included," with nothing in the spec that would allow one feature to diverge from the other's filtering behavior? [Consistency, Spec §FR-P5-003, §FR-P5-016] — **Resolved**: FR-P5-016 now says "identically, not merely similarly, filtered."
- [x] CHK013 Does FR-P5-013 ("the visual aid MUST also be included... within the incident report") read consistently against FR-P5-011 (no visual aid at all when zero activity was detected), or does it need an explicit "when available" qualifier to avoid an apparent conflict? [Conflict, Spec §FR-P5-011, §FR-P5-013] — **Resolved**: FR-P5-013 now has an explicit "when available... when not available" qualifier.
- [x] CHK014 Is FR-P5-014's "not retained or reused once a different video is loaded" stated in a way that's consistent with how New Project (Phase 4) already resets per-job state, or does it risk being read as a new, separate reset mechanism? [Consistency, Spec §FR-P5-014] — **Resolved**: FR-P5-014 now explicitly cross-references the existing Phase 4 reset boundary.

## Acceptance Criteria Quality

- [x] CHK015 Can SC-P5-001's "under 10 seconds for a typical job (a few dozen included events or fewer)" be objectively measured without also fixing a precise, falsifiable maximum event count that defines "typical"? [Measurability, Spec §SC-P5-001] — **Resolved**: SC-P5-001 now states a precise "50 included events or fewer."
- [x] CHK016 Is SC-P5-001's qualifier "a few dozen events or fewer" consistent with the rest of the spec containing no stated expectation (degraded performance acceptable, or not) for jobs above that count? [Consistency, Spec §SC-P5-001] — **Resolved**: SC-P5-001 now explicitly states larger jobs are expected to take proportionally longer, not fail or hang.

## Scenario Coverage

- [x] CHK017 Is there a concrete Given/When/Then acceptance scenario covering generating the same report twice in a row (FR-P5-018), or is this only described narratively as an Edge Case bullet? [Coverage, Spec §Edge Cases] — **Resolved**: new Acceptance Scenario 6 added to User Story 1.
- [x] CHK018 Is there an acceptance scenario for a user toggling the heatmap visual aid off again after viewing it, confirming the zone-drawing canvas underneath remains fully usable throughout? [Coverage, Spec §User Story 2] — **Resolved**: new Acceptance Scenario 6 added to User Story 2.

## Edge Case Coverage

- [x] CHK019 Does the spec address what happens if a user attempts these actions on a job that was cancelled mid-detection (partial results only), as distinct from a job that ran to full completion? [Gap, Edge Case] — **Resolved**: new FR-P5-020 + new Edge Case bullet.
- [x] CHK020 Does the spec address concurrent access — e.g. the user clicking "Generate PDF Report" and then immediately clicking "New Project" before the report finishes? [Gap, Edge Case] — **Resolved**: new Edge Case bullet.

## Non-Functional Requirements

- [x] CHK021 Does the spec state any expectation (or explicit non-requirement) for chain-of-custody hashing performance on very large source video files, given FR-P5-005 has no stated file-size bound? [Gap, Non-Functional] — **Resolved**: FR-P5-005 now explicitly states no time limit/size bound is assumed in this phase.
- [x] CHK022 Does the spec define any visual/scaling expectation for the heatmap on very high-resolution (e.g. 4K) source video, or is this left fully to implementation discretion? [Gap, Non-Functional] — **Resolved**: FR-P5-009 now states the aid is shown at the source video's own resolution, so clarity isn't reduced for higher-resolution sources.
- [x] CHK023 Does the spec address whether displaying full source/output file-system paths in the report's chain-of-custody section (FR-P5-005) is intentional, given these paths may reveal local username or folder structure if the report is later shared with an external client? [Gap, Privacy] — **Resolved**: new FR-P5-023 requires filenames only, never full paths; `data-model.md` updated to match.
- [x] CHK024 Are keyboard/non-pointer accessibility requirements defined for the new heatmap toggle control, consistent with the rest of the app's existing keyboard-driven review experience? [Gap, Coverage] — **Resolved**: new FR-P5-024.

## Dependencies & Assumptions

- [x] CHK025 Is the Assumptions section's dependency ("at least one detection run before these actions become available") cross-referenced against specific job statuses anywhere in the Functional Requirements, or only stated narratively in Assumptions? [Assumption, Spec §Assumptions] — **Resolved**: the Assumptions bullet now cross-references FR-P5-020 directly.

## Notes

- All 25 items resolved via direct `spec.md` edits (plus one downstream
  correction to `data-model.md` for CHK023, to keep the Phase 1 design
  artifact consistent with the strengthened requirement). No items deferred.
- Five new functional requirements were added (FR-P5-020 through FR-P5-024)
  rather than overloading existing ones, keeping each requirement testable
  and singular.
- CHK023 (path-privacy in the report) was the one finding with no precedent
  already addressed elsewhere in the plan/spec — now closed via FR-P5-023.
