# Checklist: Search UX & Index Lifecycle Requirements Quality

**Purpose**: Unit-test the requirements writing for the two highest-risk areas — search result presentation/composition and the on-demand index lifecycle — before implementation.
**Created**: 2026-07-10
**Feature**: [spec.md](../spec.md)
**Depth**: Standard | **Audience**: PR reviewer

## Requirement Completeness

- [x] CHK001 — Are requirements defined for every index lifecycle state a user can observe (idle, indexing, ready, unavailable, error)? [Completeness, Spec §FR-007/FR-011, data-model state machine]
- [x] CHK002 — Is behavior specified for a query issued in each non-ready state? [Coverage, Spec §Edge Cases; contracts 409 path]
- [x] CHK003 — Are requirements defined for index invalidation on every job-changing action (new video, New Project, detection re-run)? [Completeness, Spec §FR-010 + Edge Cases]
- [x] CHK004 — Is reuse of previously computed embeddings explicitly required (not just permitted)? [Completeness, Spec §FR-008]
- [x] CHK005 — Is the concurrent-indexing rule specified (duplicate requests join, never fork)? [Completeness, Spec §FR-009]
- [x] CHK006 — Are requirements defined for partial index success (some events failed to embed)? [Edge Case, Spec §FR-012, US3-AC2]

## Requirement Clarity

- [x] CHK007 — Is "relevance" quantified with an exact display formula rather than a vague notion of "similar"? [Clarity, Spec §FR-002 + design §3 formula]
- [x] CHK008 — Is "dims (never removes)" distinguished from the existing filter's hide semantics explicitly enough to test? [Clarity, Spec §FR-004 + Edge Cases "dimming is not filtering"]
- [x] CHK009 — Is the sort toggle's "view-only" constraint enumerated against concrete state it must not touch (include/exclude, canvas strip, export)? [Clarity, Spec §FR-003]
- [x] CHK010 — Is "search unavailable" messaging specified (reason + pointer target) rather than left as "show an error"? [Clarity, Spec §FR-011]

## Requirement Consistency

- [x] CHK011 — Do the search-availability conditions in the spec (detection running → disabled) agree with the indexing trigger (first focus) without contradiction? [Consistency, Spec §Edge Cases + US2-AC1]
- [x] CHK012 — Does FR-006 (compose with existing filters) agree with US1-AC5 (label filter wins over query) — i.e., composition is AND, not override? [Consistency]
- [x] CHK013 — Is the empty-state rule consistent: all-events-dimmed does NOT trigger the "no events match" empty state? [Consistency, Spec §Edge Cases]

## Acceptance Criteria Quality / Measurability

- [x] CHK014 — Are the latency targets bound to concrete workloads (event counts) and conditions (ready vs cold index)? [Measurability, Spec §SC-001/002/004]
- [x] CHK015 — Is search *quality* given a falsifiable acceptance procedure rather than a subjective "results are good"? [Measurability, Spec §SC-003 8-of-10 trial]
- [x] CHK016 — Is the no-regression requirement stated as a verifiable gate (existing suite passes unchanged)? [Measurability, Spec §SC-005]

## Scenario & Edge Case Coverage

- [x] CHK017 — Are zero-event jobs addressed? [Edge Case, Spec §Edge Cases]
- [x] CHK018 — Are degenerate queries addressed (empty/whitespace, very long text)? [Edge Case, Spec §Edge Cases]
- [x] CHK019 — Is mid-run capability change covered (models downloaded while app running → search usable without restart)? [Coverage, US3-AC3]
- [x] CHK020 — Is the headless Pi environment considered for the search UI? [Coverage, quickstart #12; Gap → resolved: browser UI is identical, scenario included]

## Dependencies & Assumptions

- [x] CHK021 — Is the "no new dependencies" constraint stated and consistent with the optional-AI install flow? [Assumption, Spec §Assumptions]
- [x] CHK022 — Is the single-job scope boundary (no cross-video search) explicit, with its future phase named? [Scope, Spec §Assumptions]

## Notes

- All 22 items PASS against spec.md as written (validated 2026-07-10 during
  checklist creation; two items — CHK011, CHK020 — prompted spec/quickstart
  tightening earlier in the pipeline rather than failing here).
