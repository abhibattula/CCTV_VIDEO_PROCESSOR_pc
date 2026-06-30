# Test Requirements Quality Checklist: Phase 10 — Test Coverage Gaps

**Purpose**: Validate that test design requirements are complete, unambiguous, and ready for implementation — testing the requirements, not the tests themselves
**Created**: 2026-06-29
**Feature**: [spec.md](../spec.md) | [data-model.md](../data-model.md) | [research.md](../research.md)

---

## Requirement Completeness

- [ ] CHK026 - Are acceptance criteria defined for all 6 user stories (US1–US6) with at least one verifiable Given/When/Then scenario each? [Completeness, Spec §US1–US6]
- [ ] CHK027 - Is the required behavior for session state after a cancelled job explicitly specified? Does the spec define the expected terminal status for US1 AC6 cancel scenario? [Completeness, Spec §US1 AC6]
- [ ] CHK028 - Are requirements defined for what happens when the fake-detector thread exceeds the 5-second polling deadline — does the spec say the test should fail with a specific assertion, or just time out? [Completeness, Spec §US1, Data-model §FakeDetector]
- [ ] CHK029 - Is the expected behavior of `GET /api/system/stats` on a machine where `cpu_temp` returns `None` (Windows) documented in the spec or research? [Completeness, Spec §US6, Research §Decision 8]
- [ ] CHK030 - Are all 9 test files that will be created or modified explicitly listed with their story mapping in the spec? [Completeness, Spec §US1–US6]

## Requirement Clarity

- [ ] CHK031 - Is "mock counterpart" for CI blind spots (US6 AC6) defined with sufficient precision — does the spec specify WHICH 12 tests need mock variants, or only the count? [Clarity, Spec §US6 AC6]
- [ ] CHK032 - Is the term "standard developer environment" (FR-007) defined with an explicit exclusion list (no video file, no GPU, no display)? Or does it leave room for ambiguous interpretation? [Clarity, Spec §FR-007]
- [ ] CHK033 - Is "graceful degradation" (US3b) quantified — does the spec define what "returns None without raising" means for every `ClipIndexer.embed()` failure path (unavailable, image load error, numpy write error)? [Clarity, Spec §US3 AC2–5]
- [ ] CHK034 - Is the phrase "CI mock counterparts" in US6 measurable — can a reviewer determine from the spec alone whether a given test counts as a mock counterpart? [Clarity, Spec §US6]
- [ ] CHK035 - Are the exact monkeypatch targets specified for US1 thread lifecycle tests? Does the spec or research identify `app.core.detection_engine.run` as the target (not `app.api.job._run`)? [Clarity, Research §Decision 4]

## Requirement Consistency

- [ ] CHK036 - Is the `start_job` precondition consistent across US1 AC1 (`"ready"`), FR-001 ("US1 acceptance criteria"), and the data-model `TestSession` entity (status=`"ready"`)? [Consistency, Spec §US1 AC1, Spec §FR-001, Data-model §TestSession]
- [ ] CHK037 - Are the shell bridge route names consistent between the spec acceptance criteria (US2 AC4-6) and the research document (Decision 6)? Do both say `POST /shell/set-output-dir` and `POST /shell/open-folder`? [Consistency, Spec §US2, Research §Decision 6]
- [ ] CHK038 - Are the `seconds_to_clock` expected values consistent between US4 acceptance criteria, Research Decision 7, and the data-model SyntheticEvent entity? [Consistency, Spec §US4 AC1-3, Research §Decision 7]
- [ ] CHK039 - Is there a conflict between SC-001 ("at least 55 new checks") and SC-003 ("6 zero-coverage modules covered")? Could someone achieve SC-001 without satisfying SC-003? Does the spec require both independently? [Consistency, Spec §SC-001, Spec §SC-003]
- [ ] CHK040 - Are the LogBuffer API calls consistent between US3 AC1-5 (subscribe, append, reset, close) and the data-model §LogBuffer entity definition? Does any acceptance criteria reference `get()` or `history` which don't exist in the actual API? [Consistency, Spec §US3, Data-model §LogBuffer]

## Acceptance Criteria Testability

- [ ] CHK041 - Can US5 AC1 (`_get_desktop_path()` returns "non-empty string") be objectively verified on a machine without Windows CSIDL support — is the fallback path `Path.home() / "Desktop"` considered passing? [Measurability, Spec §US5 AC1]
- [ ] CHK042 - Is US5 AC2 ("close event is ignored / window stays open or hides to tray") measurable without a running Qt instance? Does the spec define what "ignored" means in terms of observable mock calls? [Measurability, Spec §US5 AC2]
- [ ] CHK043 - Is US6 AC3 ("generator exits cleanly after MAX_IDLE_POLLS") measurable — does the spec define what "cleanly" means (no exception raised, returns without error)? [Measurability, Spec §US6 AC3]
- [ ] CHK044 - Can SC-004 ("both state-machine check AND thread lifecycle check for start_job") be objectively verified as two distinct test functions, or could a single parameterized test satisfy it? [Measurability, Spec §SC-004]

## Scenario Coverage

- [ ] CHK045 - Are requirements defined for the scenario where `start_job` is called with status `"exporting"` (not just `"detecting"`)? The edge cases section mentions it but FR-001 does not include it as a required acceptance criterion. [Coverage, Spec §Edge Cases, Spec §FR-001]
- [ ] CHK046 - Are requirements defined for the LogBuffer `close()` scenario with zero subscribers — is this covered by an acceptance criterion or only by the edge cases bullet? [Coverage, Spec §US3, Spec §Edge Cases]
- [ ] CHK047 - Is there a requirement for what happens when `reset(job_id)` is called on a job_id that was never created — is "no-op, no exception" specified in an acceptance criterion or only implied? [Coverage, Spec §US3 AC4]
- [ ] CHK048 - Are recovery requirements defined for the Qt stub fixture when `shell.main_window` import fails despite sys.modules patching — is there a rollback requirement on the fixture teardown? [Coverage, Data-model §QtStubRegistry]

## Non-Functional Requirements

- [ ] CHK049 - Is the "< 30 s" test suite completion time target (plan.md Technical Context) referenced anywhere in the spec's Success Criteria? Or is it only in the plan — leaving SC-002 as the sole non-functional criterion? [Completeness, Plan §Technical Context, Spec §SC-002]
- [ ] CHK050 - Are concurrency requirements for LogBuffer (multiple threads appending simultaneously) specified in the acceptance criteria, or only in the edge cases section? Is "concurrent appends don't corrupt state" an independently testable requirement? [Coverage, Spec §Edge Cases]

## Dependencies & Assumptions

- [ ] CHK051 - Is the assumption "PyQt6 is not installed in CI" validated — if PyQt6 IS installed, would the Qt stub tests still work, or would the import succeed and bypass the sys.modules mock? [Assumption, Spec §Assumptions]
- [ ] CHK052 - Is the dependency on `session.append_event` (called by `start_job` via `on_event=session.append_event`) documented in the spec or research? FakeDetector calls `on_event` — is it clear the session method is used? [Dependency, Research §Decision 4]
- [ ] CHK053 - Is the assumption "no new pip packages required" validated against all 9 test files? Does `test_shell_logic.py` require any import not in the existing dependency set? [Assumption, Spec §Assumptions, Plan §Technical Context]

## Notes

This checklist validates the REQUIREMENTS QUALITY for Phase 10 test coverage gaps.
It complements `requirements.md` (CHK001–CHK025) which validated the spec structure.
Focus areas: CI safety constraints, acceptance criteria testability, spec/data-model consistency.
Depth: Standard (formal PR gate for a production codebase with active regression risk).
