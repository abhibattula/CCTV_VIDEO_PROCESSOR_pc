# Implementation Gate Checklist: Video Intelligence Export

**Purpose**: Validate requirement quality and completeness across spec, data-model, and API contracts before implementation begins  
**Created**: 2026-06-25  
**Feature**: [spec.md](../spec.md) | [data-model.md](../data-model.md) | [contracts/api.md](../contracts/api.md)  
**Focus**: US1 (report content), US2 (Moondream2 integration), US3 (RAG structure); pre-implementation gate

---

## Requirement Completeness

- [ ] CHK001 — Are all required report sections enumerated with their exact content requirements (not just section names)? [Completeness, Spec §FR-P6-002 through FR-P6-009]
- [ ] CHK002 — Is the "Key Moments" selection algorithm specified — is it the top 3 by `peak_motion_score` descending, and is a tiebreaker defined for equal scores? [Completeness, Spec §FR-P6-006]
- [ ] CHK003 — Is the heatmap "interpretation text" content defined, or is only the presence of a heatmap image required? If text content is required, what must it contain? [Completeness, Spec §FR-P6-007]
- [ ] CHK004 — Is the detection configuration section's field list exhaustive? Does it match the exact fields in `session["settings"]` (mode, sensitivity, padding_s, min_event_s, min_gap_s, zones)? [Completeness, Spec §FR-P6-008]
- [ ] CHK005 — Is there a requirement that the detection settings reflected in the report are a point-in-time snapshot from when detection ran, not the current session state (which could have been mutated)? [Completeness, Gap]
- [ ] CHK006 — Are requirements defined for the Markdown Key Moments thumbnail reference — is it an absolute path, a relative path, or an embedded base64 image? [Completeness, Spec §FR-P6-006]
- [ ] CHK007 — Is there a requirement for whether the output_dir is created automatically if it does not exist (mkdir), or whether generation should fail with an error? [Completeness, Spec §FR-P6-012]
- [ ] CHK008 — Is the encoding of the Markdown file explicitly required (UTF-8 is the only safe choice for LLM consumption)? [Completeness, Gap]

---

## Requirement Clarity

- [ ] CHK009 — Is "executive summary in plain language" quantified beyond vague prose? Are the specific required facts (what was detected, when was peak, what was the activity level) listed unambiguously in FR-P6-002? [Clarity, Spec §FR-P6-002]
- [ ] CHK010 — Is "busiest period" defined with a specific measurement method? Is it a sliding window (if so, what size?), or the time range spanning the densest cluster of events? [Clarity, Spec §FR-P6-003]
- [ ] CHK011 — Is "first appearance time" in the object inventory defined as the `start_clock` of the earliest included event for that zone_label? Is `end_clock` of the latest event the definition of "last appearance time"? [Clarity, Spec §FR-P6-004]
- [ ] CHK012 — Is "self-contained" HTML for the PDF clearly defined as "no external URLs for images, fonts, or scripts" — or could a browser-cached font be acceptable? [Clarity, Spec §FR-P6-010]
- [ ] CHK013 — Is the 100KB limit defined per Markdown file, or does it apply to both Markdown and PDF combined? [Clarity, Spec §FR-P6-023]
- [ ] CHK014 — Is the distinction between "completed" and "cancelled" detection status clear for report eligibility? Are `export_done` and `export_error` session statuses also permitted (the CSV/JSON exports allow them)? [Clarity, Spec §FR-P6-001]
- [ ] CHK015 — Is "within a reasonable time" in Acceptance Scenario 1 quantified? It should match the SC-P6-002 metric of under 2 minutes — are these consistent? [Clarity, Spec §User Story 1 Scenario 1, §SC-P6-002]
- [ ] CHK016 — Is the PDF generation trigger defined in the spec (the POST → Qt event bridge) or only in the contract? A reader of the spec alone should understand how PDF generation is initiated. [Clarity, Spec §FR-P6-014]

---

## Requirement Consistency

- [ ] CHK017 — Do FR-P6-005 and `data-model.md § TimelineEntry` agree on the exact fields in the timeline table row (specifically: is "zone" or "label" the column name; is confidence shown as raw float or percent)? [Consistency, Spec §FR-P6-005]
- [ ] CHK018 — Do FR-P6-009 and `data-model.md § JSON Appendix Record` agree on exactly which fields are required vs optional? FR-P6-009 lists 8 required fields; the data model includes an optional `description` field — is this consistent? [Consistency, Spec §FR-P6-009]
- [ ] CHK019 — Do the error guard messages in the spec's Edge Cases section, FR-P6-001, and `contracts/api.md` match verbatim? Inconsistent wording across these sources could lead to mismatch between implementation and test assertions. [Consistency]
- [ ] CHK020 — Is the filename pattern `{source_stem}_intelligence_{YYYYMMDD_HHMMSS}` consistent in the spec (FR-P6-013), the design doc, and `contracts/api.md`? [Consistency, Spec §FR-P6-013]
- [ ] CHK021 — Does the spec's description of the POST response body (`{"md_path": str, "moondream_available": bool}`) match `contracts/api.md § POST /api/job/intel-report/export` exactly? [Consistency]

---

## Edge Case Coverage

- [ ] CHK022 — Is the requirement for a job cancelled BEFORE any events were detected (zero events via cancellation, not via toggle) specified? The spec covers "zero included events" but is it explicit that a cancelled run with 0 total events is the same case? [Edge Case, Spec §Edge Cases]
- [ ] CHK023 — Is there a requirement for handling events with a `null` or empty `zone_label` in YOLO mode (e.g., if the detection engine emits an event with no class)? The object inventory requirement (FR-P6-004) is YOLO-only, but what if zone_label is None in a YOLO run? [Edge Case, Gap]
- [ ] CHK024 — Is the tiebreaker for Key Moments defined when multiple events have identical `peak_motion_score`? Without a tiebreaker, implementations may produce different results. [Edge Case, Spec §FR-P6-006]
- [ ] CHK025 — Is there a requirement for what "busiest period" displays when all events fit within a single 60-second window (or when there is only 1 event)? [Edge Case, Spec §FR-P6-003]
- [ ] CHK026 — Is the maximum description string length defined to guarantee the 100KB Markdown limit? The spec says "descriptions truncated if needed" but FR-P6-023 doesn't specify the truncation limit or algorithm. [Edge Case, Spec §FR-P6-023]
- [ ] CHK027 — Is the behaviour of the object inventory defined when two zone_labels are equivalent but differ in case (e.g., "person" vs "Person") — is normalisation required? [Edge Case, Gap]

---

## Success Criteria Measurability

- [ ] CHK028 — Is SC-P6-001 ("user can identify N facts within 60 seconds") verifiable without user testing in a development context? If not, is a proxy measurable outcome defined? [Measurability, Spec §SC-P6-001]
- [ ] CHK029 — Is SC-P6-003 ("4 out of 5 factual questions") operationalised with the specific 5 questions and their expected answers, so that it can be verified consistently across different test videos? [Measurability, Spec §SC-P6-003]
- [ ] CHK030 — Is SC-P6-002's "under 2 minutes" measured from when the button is clicked (includes Qt PDF generation) or from API call start to Markdown file written (excludes Qt)? These are materially different targets. [Clarity/Measurability, Spec §SC-P6-002]

---

## Non-Functional Requirements

- [ ] CHK031 — Are requirements defined for what happens if the user triggers "Generate Intelligence Report" twice in rapid succession? Is the second request queued, rejected, or allowed to run concurrently? [Coverage, Gap]
- [ ] CHK032 — Is there a requirement for PDF file size (only Markdown has a 100KB constraint)? A PDF with many embedded base64 thumbnails can become several hundred MB. [Coverage, Gap]
- [ ] CHK033 — Are requirements defined for the visual quality of embedded thumbnails (JPEG quality level, whether they are scaled to a specific size before embedding)? The design doc mentions 320×180 but this is not in the spec. [Coverage, Gap]
- [ ] CHK034 — Is there a requirement for what happens if `thumbnail_gen.run()` partially fails (generates thumbnails for events 1-4 but fails on event 5)? Should generation continue with placeholders, or fail the whole report? [Coverage, Spec §FR-P6-018]

---

## Notes

- Mark items `[x]` when the referenced requirement is confirmed complete and unambiguous in the spec
- Use inline comments to note specific issues found (e.g., `- [x] CHK010 — confirmed: busiest period = densest 60-second sliding window, spec §FR-P6-003 updated`)
- Items with `[Gap]` indicate a requirement that appears missing from the spec — resolve before marking complete
- All `[Clarity]` items should resolve to a specific FR or SC update if the requirement is ambiguous
