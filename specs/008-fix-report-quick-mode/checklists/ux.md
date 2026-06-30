# UX Requirements Quality Checklist: Phase 8 — Quick Report Button

**Purpose**: Validate requirement quality for the Quick Report PDF button UI addition
**Created**: 2026-06-29
**Feature**: [spec.md](../spec.md)

## Requirement Completeness

- [ ] CHK018 - Is the exact layout of the two buttons specified (horizontal side-by-side vs vertical stack)? FR-006 says "alongside" but does not define orientation or responsive behavior. [Completeness, Spec §FR-006]
- [ ] CHK019 - Is the disabled state of the "Quick Report" button specified for the zero-events case (as mentioned in the spec's Edge Cases)? [Completeness, Spec §FR-006, Edge Cases]
- [ ] CHK020 - Are loading/in-progress states specified for the Quick Report button after it is clicked (e.g., does it show a spinner, disable itself, or remain interactive while the Qt dialog is open)? [Completeness, Gap]
- [ ] CHK021 - Is the button label exact text specified? FR-008 specifies "Quick Report" for the label and "Instant · rule-based synthesis" for the subtitle, but FR-006 refers to it as "Quick Report (PDF)". Is the parenthetical "(PDF)" part of the label or only for documentation? [Clarity, Spec §FR-006 vs FR-008]

## Requirement Clarity

- [ ] CHK022 - Is "triggered immediately without any AI analysis delay" (Spec §US3 Scenario 1) measurable? What is the maximum allowed latency between button click and PDF save dialog appearance? SC-005 says "< 5 seconds" — is this measured from click to dialog, or from click to PDF file written? [Clarity, Spec §US3 vs SC-005]
- [ ] CHK023 - Is "identical to what the existing Incident Report button produces" (Spec §US3 Scenario 2) specific enough? If the existing Incident Report button is in a different section of the page, are there any visual or content differences expected between the two flows? [Clarity, Spec §US3 Scenario 2]
- [ ] CHK024 - Does FR-007 ("completing within 5 seconds") specify whether this is the time to show the Qt save dialog, or the time to fully write the PDF file? These are different end-points. [Clarity, Spec §FR-007]

## Requirement Consistency

- [ ] CHK025 - Is the behavior of the Quick Report button consistent with the existing "Generate PDF Report" button that already exists in the "Reports & Data Export" section of the export page? If both buttons do the same thing, is there a requirement to consolidate them or keep both? [Consistency, Spec §Assumptions]
- [ ] CHK026 - Does FR-008 (subtitle text) align with the plan's visual mock: "Instant · rule-based" vs spec's "Instant · rule-based synthesis"? Are these the same string or different? [Consistency, Spec §FR-008 vs Plan]

## Acceptance Criteria Quality

- [ ] CHK027 - Is SC-005 ("< 5 seconds to generate and open") verifiable without triggering the Qt PDF bridge in an automated test? Is there a specification for how this is measured in the CI environment vs manual test? [Measurability, Spec §SC-005]
- [ ] CHK028 - Is the manual test scenario in quickstart.md sufficient as the acceptance gate for FR-006/FR-007/FR-008, given the frontend exemption from automated tests (Constitution III)? [Coverage, Assumption]

## Scenario Coverage

- [ ] CHK029 - Is there a requirement for the state of the Quick Report button when the app is NOT running in a Qt context (e.g., launched with a standalone browser for debugging)? [Coverage, Gap]
- [ ] CHK030 - Is there a requirement for what happens if the Qt PDF save dialog is cancelled by the user — should the button return to its normal state, or show an error? [Coverage, Edge Case]

## Notes

- CHK021 (label inconsistency FR-006 vs FR-008) is a low-risk wording issue but should be resolved before implementation so both the button label and tests use the same string.
- CHK025 (duplicate PDF buttons) should be discussed — if both buttons do the same thing, one may be redundant and cause user confusion.
