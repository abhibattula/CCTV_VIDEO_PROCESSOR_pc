# Specification Risk Review Checklist: Phase 4 — ROI Selection, Stop Application, New Project

**Purpose**: Unit tests for the requirements themselves — validate completeness,
clarity, consistency, measurability, and coverage of `spec.md` before planning
proceeds further.
**Created**: 2026-06-23
**Feature**: [spec.md](../spec.md)

## Requirement Completeness

- [X] CHK001 - Is the minimum number of points required to close a region into
  a valid shape stated in the spec itself, not only in a downstream design
  artifact? [Completeness, Spec §FR-P4-002]
- [X] CHK002 - Is there a stated assumption about whether the number of
  regions, or points per region, a user may draw is bounded? [Gap, Spec
  §Assumptions]
- [X] CHK003 - Does the spec address what happens if the Stop control is used
  when no job has ever been created in the current session? [Gap, Edge Cases]
- [X] CHK004 - Does the spec address what happens if the Stop control is used
  a second time after the application has already been confirmed stopped?
  [Gap, Edge Cases]

## Requirement Clarity

- [X] CHK005 - Is the rule for combining multiple simultaneously-drawn regions
  (does activity in ANY region count, or must it be inside ALL of them)
  stated explicitly? [Ambiguity, Spec §FR-P4-004]
- [X] CHK006 - Are "the application" (the backend/detection process) and "the
  window" (the visible UI shell) used as distinct, clearly-separated terms
  throughout US2, or could a reader conflate the two given that stopping one
  must not stop the other? [Clarity, Spec §FR-P4-006, §FR-P4-009]

## Requirement Consistency

- [X] CHK007 - Does User Story 2's Acceptance Scenario 2 ("becomes
  unresponsive... within a few seconds") use language consistent with
  SC-P4-003's precise 15-second threshold, or do the two read as different
  commitments? [Consistency, Spec §US2 Scenario 2, §SC-P4-003]
- [X] CHK008 - Are the two New Project warning conditions (FR-P4-012,
  FR-P4-013) and the "no warning needed" condition (FR-P4-014) collectively
  exhaustive over every possible job status, with no status left unaddressed?
  [Consistency, Spec §FR-P4-012 to §FR-P4-014]

## Acceptance Criteria Quality

- [X] CHK009 - Can every acceptance scenario in US1-US3 be verified by an
  observer with no access to the implementation (i.e., do they describe
  user-visible outcomes only)? [Measurability]
- [X] CHK010 - Is SC-P4-002's "zero events from outside that region" testable
  against a concrete, describable test setup rather than a hypothetical one?
  [Measurability, Spec §SC-P4-002]

## Scenario Coverage

- [X] CHK011 - Are primary, alternate (cancel-the-dialog), and exception
  (extraction-failure) flows all represented across the three user stories?
  [Coverage]
- [X] CHK012 - Is there a scenario covering a user drawing zero regions and
  proceeding directly to detection, distinct from drawing-then-clearing all
  regions? [Coverage, Spec §US1]

## Edge Case Coverage

- [X] CHK013 - Are boundary conditions for region geometry (very small area,
  self-crossing edges) addressed, and is the system's tolerance of them
  (accept without error) explicit rather than implied? [Edge Case, Spec
  §Edge Cases]
- [X] CHK014 - Is the precedence rule between Stop and New Project being
  triggered in close succession stated clearly enough to resolve any
  ordering ambiguity? [Edge Case, Spec §Edge Cases]

## Non-Functional Requirements

- [X] CHK015 - Are the three quantified Success Criteria (SC-P4-003 15s,
  SC-P4-004 5s, SC-P4-005 100%) each tied to an unambiguous start/end event
  for measurement (e.g., "from confirmation click" to "from what observable
  moment")? [Clarity, Spec §Success Criteria]

## Dependencies & Assumptions

- [X] CHK016 - Is the assumption that this feature does not alter
  already-running-job behavior (mode/sensitivity/padding) stated explicitly
  enough to prevent scope creep during implementation? [Assumption, Spec
  §Assumptions]

## Ambiguities & Conflicts

- [X] CHK017 - Is there any requirement in this spec that could be read as
  conflicting with Phase 3's existing undo-history or custom-preset behavior
  (e.g., does New Project's reset interact with either in a way not already
  covered by FR-P4-015)? [Conflict]

## Resolution Notes

All 17 items resolved on first pass, edited directly into `spec.md` (no
deferral, per project policy):

- **Required actual edits** (11): CHK001 (≥3 points stated in FR-P4-002),
  CHK002 (uncapped-regions assumption added), CHK003/CHK004 (two new Stop
  edge cases added), CHK005 (union-not-intersection rule added to
  FR-P4-004), CHK006 (application-vs-window terminology note added to US2),
  CHK007 (Acceptance Scenario 2 now references SC-P4-003 instead of its own
  vague "a few seconds"), CHK008 (FR-P4-014 now states exhaustiveness
  explicitly), CHK010/CHK015 (SC-P4-002 and SC-P4-004 reworded with concrete
  test setups and explicit start/end events), CHK016/CHK017 (Assumptions
  strengthened: no-change-to-detection-params clause, and an explicit
  carve-out distinguishing job-scoped reset from Phase 3's user
  configuration).
- **Already adequate, no edit needed** (6): CHK009 (all acceptance scenarios
  already describe user-visible outcomes only), CHK011 (an exception flow —
  cancel-call failure — was added under CHK002's edit pass as a side effect,
  completing coverage), CHK012 (already covered by US1 Acceptance Scenario
  4), CHK013 (Edge Cases already states tiny/self-crossing regions are
  accepted without error), CHK014 (Edge Cases already states the
  Stop-vs-New-Project precedence rule).

