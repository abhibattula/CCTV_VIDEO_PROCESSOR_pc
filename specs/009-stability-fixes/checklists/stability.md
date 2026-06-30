# Stability Checklist: Phase 9 — Stability Fixes

**Purpose**: Validate requirements quality across six stability bug fixes before implementation
**Created**: 2026-06-29
**Feature**: [spec.md](../spec.md)

## Requirement Completeness

- [ ] CHK001 — Are error-path requirements specified for all six bug-fix scenarios (browse fail, poll stall, no-quit, false-PDF, terminal noise, wrong path)? [Completeness, Spec §Requirements/FR-001–FR-013]
- [ ] CHK002 — Are requirements defined for the "browse clicked while file is already loading" edge case (not just the double-click race)? [Completeness, Spec §Edge Cases]
- [ ] CHK003 — Is a requirement specified for what happens when a new Browse click fires while `doLoadFile` is in progress (cancel or queue)? [Completeness, Spec §FR-001, Gap]
- [ ] CHK004 — Is the expected user-visible message text defined for each Browse failure mode (network error, backend unreachable, 400 response)? [Completeness, Spec §FR-002, Gap]
- [ ] CHK005 — Are requirements defined for the "output folder set by user was later deleted from disk" fallback scenario? [Completeness, Spec §Edge Cases]
- [ ] CHK006 — Is a requirement specified for what happens when the Desktop path resolution via the Windows Shell API itself fails (ctypes error)? [Completeness, Spec §FR-005, Gap]

## Requirement Clarity

- [ ] CHK007 — Is "cancel the previous chain" in FR-001 unambiguous — does it mean silently stop, or show a cancel confirmation? [Clarity, Spec §FR-001]
- [ ] CHK008 — Is the "visible Desktop folder" in FR-005 and US2 defined precisely enough to distinguish from `Path.home()/"Desktop"` without prior context? [Clarity, Spec §FR-005]
- [ ] CHK009 — Is "within the same app session" in FR-004 bounded — does it mean "until the process exits" or "until the user explicitly resets"? [Clarity, Spec §FR-004]
- [ ] CHK010 — Is "inline error" in FR-007 positioned clearly — same element as the status text, or a separate banner? [Clarity, Spec §FR-007]
- [ ] CHK011 — Is the "≤3 seconds" exit requirement in FR-009 applied to the full process (uvicorn + Qt) or just the Qt window? [Clarity, Spec §FR-009, SC-004]
- [ ] CHK012 — Is "no included events" detection in FR-007 defined as zero events with `included=true`, or zero total events? [Clarity, Spec §FR-007]

## Requirement Consistency

- [ ] CHK013 — Do FR-010 (close-to-tray only when job active) and the Edge Case "Stop clicked while detection is in progress: detection cancels, then app auto-closes" agree on what happens after Stop during active detection? [Consistency, Spec §FR-010, Edge Cases]
- [ ] CHK014 — Are the Quick Report PDF feedback requirements in FR-007/FR-008 consistent with SC-003 ("truthful status on 100% of clicks") — is there any scenario where FR-008's timeout (120 s) would cause SC-003 to fail? [Consistency, Spec §FR-008, SC-003]
- [ ] CHK015 — Does the "output_dir persists across video loads" requirement (FR-004) conflict with the constitution's `session.reset()` contract, and is the resolution documented? [Consistency, Spec §Assumptions, plan.md §Complexity Tracking]
- [ ] CHK016 — Is the `_PERSISTENT` dict approach (plan.md) consistent with the spec's statement that `output_dir` "persists for the lifetime of the app session" (spec §Key Entities)? [Consistency, Spec §Key Entities]

## Acceptance Criteria Quality

- [ ] CHK017 — Is SC-001 ("exactly one file dialog") objectively verifiable — what defines a "file dialog" count vs. an aborted dialog? [Measurability, Spec §SC-001]
- [ ] CHK018 — Is SC-004 ("<3 seconds" for Ctrl+C exit) measurable — is there a defined start time (keypress) and end time (process exit vs. window close)? [Measurability, Spec §SC-004]
- [ ] CHK019 — Is SC-005 ("< 100 ms after the first") testable — what is the defined measurement point (browser DevTools, server-side log, pytest timer)? [Measurability, Spec §SC-005]
- [ ] CHK020 — Is SC-006 ("zero MISSING-key or FutureWarning lines") verifiable in automated testing, or only in manual terminal observation? [Measurability, Spec §SC-006]

## Scenario Coverage

- [ ] CHK021 — Are requirements defined for the race between two concurrent Quick Report PDF requests (button clicked twice before the first result returns)? [Coverage, Spec §Edge Cases]
- [ ] CHK022 — Is the "detection in progress + Ctrl+C" scenario covered — should Ctrl+C cancel detection gracefully or abort immediately? [Coverage, Spec §FR-009, Gap]
- [ ] CHK023 — Are requirements specified for the `_generate_intel_report_pdf` code path as well as `_generate_pdf_report` for the PDF result injection fix? [Coverage, Spec §FR-008, Gap]
- [ ] CHK024 — Is the "backend returns 4xx for `/api/job/report.html`" error path explicitly covered by FR-007 (pre-validation should prevent it) or FR-008 (inject failure result)? [Coverage, Spec §FR-007, FR-008]
- [ ] CHK025 — Are requirements defined for the Florence-2 noise suppression scope: stdout only, or also stderr? [Coverage, Spec §FR-012, Gap]

## Edge Case Coverage

- [ ] CHK026 — Is the edge case "OneDrive Desktop Folder Backup is disabled" addressed — does `_get_desktop_path()` still return the correct path? [Edge Case, Spec §Edge Cases]
- [ ] CHK027 — Is the edge case "Browse dialog cancelled by user (no file selected)" specified — should it re-enable the button with no error? [Edge Case, Spec §US1, Gap]
- [ ] CHK028 — Is the edge case "Quick Report clicked exactly at 120 s poll timeout with no result" covered — should it show an error or silently re-enable? [Edge Case, Spec §FR-008]

## Non-Functional Requirements

- [ ] CHK029 — Are timing requirements for the availability cache effect quantified (FR-013 says "no re-run"; SC-005 says "< 100 ms") — are these two requirements linked? [Non-Functional, Spec §FR-013, SC-005]
- [ ] CHK030 — Is there a requirement for the FrameAnalyzer cache to be thread-safe when `is_available()` is called concurrently (e.g., during parallel API calls)? [Non-Functional, Gap]

## Dependencies & Assumptions

- [ ] CHK031 — Is the assumption "model weights never installed/removed mid-run" (Assumptions §FR-013) validated — what if the user installs Florence-2 while the app is running? [Assumption, Spec §Assumptions]
- [ ] CHK032 — Is the Windows-only scope of the Desktop path fix clearly documented in user-facing documentation (not just internal assumptions)? [Assumption, Spec §Assumptions]
- [ ] CHK033 — Is the `ctypes.windll.shell32` dependency documented — does it require a specific Windows SDK or is it always present? [Dependency, Spec §Assumptions, research.md §Decision 1]

## Notes

- CHK003, CHK004, CHK006, CHK022, CHK025, CHK027 are potential gaps; review spec before closing.
- CHK013 (FR-010 vs. Edge Case consistency) should be resolved before implementing `closeEvent`.
- CHK023 (intel-report coverage) — plan.md documents this fix; spec FR-008 should be updated to explicitly mention both PDF paths.
