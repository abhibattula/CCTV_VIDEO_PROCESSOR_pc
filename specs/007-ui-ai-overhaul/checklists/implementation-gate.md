# Implementation Gate Checklist: UI/UX Overhaul & Enhanced AI Analysis

**Purpose**: Validate that spec, plan, contracts, and data-model are ready for SDD implementation
**Created**: 2026-06-26
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md) | [contracts/api.md](../contracts/api.md) | [data-model.md](../data-model.md)
**Depth**: Standard | **Audience**: Implementer + task reviewer

---

## Requirement Completeness

- [x] CHK001 — Are all four SSE stage names ("thumbnails", "ai_analysis", "markdown", "pdf") and their trigger conditions documented in both the plan and contracts? [Completeness, plan.md §SSE Stage Progress, contracts/api.md]
- [x] CHK002 — Is the minimum number of Scene Breakdown entries specified for runs with fewer than 5 events? [Completeness, Spec §FR-010] ✓ Spec says "all available events (minimum 1)"
- [x] CHK003 — Are all `FrameAnalysis` dict fields and their empty/null equivalents explicitly defined for the case where Florence-2 is absent? [Completeness, data-model.md §FrameAnalysis]
- [x] CHK004 — Are the `formats` parameter validation rules (empty list, invalid values) specified with response status codes? [Completeness, contracts/api.md §POST /job/intel-report/export]
- [x] CHK005 — Is the behaviour defined when the format dialog is closed without selecting? [Completeness, Spec §Edge Cases] ✓ "button returns to enabled state"
- [x] CHK006 — Are both new optional dependencies (`open-clip-torch`, `anthropic`) documented in requirements.txt update scope? [Completeness, plan.md §Files Changed]

---

## Requirement Clarity

- [x] CHK007 — Is "multi-sentence paragraph" from SC-001 quantified with a minimum sentence count? [Clarity, Spec §SC-001] ✓ SC-001 says "at least 2 sentences"
- [x] CHK008 — Is the distinction between `clip_embedding_path: None` (library absent) and a valid path documented clearly for callers? [Clarity, data-model.md §FrameAnalysis]
- [x] CHK009 — Are the exact severity levels for log entries (INFO, EVENT, WARN, ERROR) enumerated with their trigger conditions in the spec? [Clarity, Spec §FR-016] ✓ Plan §Log Panel Polish enumerates all four with example entries
- [x] CHK010 — Is "highest-confidence events" for Scene Breakdown defined as the `confidence` field from detection data? [Clarity, Spec §FR-010, data-model.md §SceneBreakdownEntry] ✓ data-model.md defines "sorted by confidence descending"
- [x] CHK011 — Is the LLM fallback notice text specified precisely enough that two implementers would write the same string? [Clarity, Spec §FR-013] ✓ Spec gives example: "Executive summary: rule-based synthesis — LLM API unavailable"
- [ ] CHK012 — Is the meaning of `current=0, total=0` for single-step stages ("markdown", "pdf") documented in the contracts? [Clarity, contracts/api.md] ⚠️ GAP: the contracts/api.md shows `"total": 0` for single-step stages but does not state this explicitly

---

## Requirement Consistency

- [x] CHK013 — Does the `formats` default in contracts/api.md (`["md", "pdf"]`) match the plan's stated backwards-compat default? [Consistency, contracts/api.md vs plan.md §Global Constraints]
- [x] CHK014 — Are SSE event field names consistent across plan.md, contracts/api.md, and data-model.md? [Consistency] ✓ All three documents use `"ts"` for the timestamp field in `report_stage` events
- [x] CHK015 — Is the `florence_available` field definition consistent between `/api/job/status` contract and its computation logic (transformers installed AND model weights cached)? [Consistency, contracts/api.md]
- [x] CHK016 — Is the breaking change (`moondream_available` → `florence_available`) noted in both contracts/api.md and the task that must update export.js? [Consistency, contracts/api.md §Deprecated Fields]
- [ ] CHK017 — Does the session state reset (`session.reset()`) clear the four new `report_stage_*` fields? [Consistency, data-model.md §Session State Extensions, plan.md §Global Constraints] ⚠️ Plan states "reset to defaults when session.reset() is called" but does not specify they must be added to `_DEFAULTS`

---

## Acceptance Criteria Quality

- [x] CHK018 — Is SC-001 ("at least 2 sentences, at least one specific visual detail") objectively verifiable on a real detection run without access to implementation internals? [Measurability, Spec §SC-001]
- [x] CHK019 — Is SC-007 ("persists across browser sessions") verifiable without knowledge of `localStorage` key names? [Measurability, Spec §SC-007] ✓ Quickstart Scenario 1 step 10–11 specifies the exact test
- [x] CHK020 — Is SC-004 ("Scene Breakdown section present with at least 1 entry") distinguishable from an empty section containing placeholder text? [Measurability, Spec §SC-004]
- [x] CHK021 — Is SC-003 ("all four stages visually represented") testable without counting internal SSE messages? [Measurability, Spec §SC-003] ✓ Quickstart Scenario 2 specifies what to observe in the UI

---

## Scenario Coverage

- [x] CHK022 — Are requirements defined for the case where `formats=["pdf"]` but the Qt PDF bridge is unavailable? [Coverage, Spec §Edge Cases] ✓ "if Markdown was also requested it is still written; warning shown"
- [x] CHK023 — Is the behaviour defined when fewer than 5 events exist (Scene Breakdown with <5 entries)? [Coverage, Spec §Edge Cases] ✓ "shows all available events (minimum 1)"
- [x] CHK024 — Is the behaviour defined when a thumbnail file is missing at report generation time? [Coverage, Spec §Edge Cases] ✓ "that event's description is empty; other events unaffected"
- [ ] CHK025 — Are requirements defined for what happens when a CLIP `.npy` write fails mid-generation (e.g. disk full)? [Coverage, Gap] ⚠️ Not explicitly addressed — should it abort CLIP silently and continue, or surface an error?
- [ ] CHK026 — Are requirements defined for concurrent/simultaneous report generation attempts (two tabs)? [Coverage, Gap] ⚠️ Session is single-job but concurrent POST calls from two tabs are not addressed
- [x] CHK027 — Is the model download progress scenario (first-run Florence-2 download) covered in spec edge cases? [Coverage, Spec §Edge Cases] ✓ "progress display should show 'Downloading AI model (first time)…'"

---

## Non-Functional Requirements

- [x] CHK028 — Is disk space consumption (~230 MB Florence-2, ~600 MB CLIP) documented for the user? [NFR, plan.md §Technical Context]
- [ ] CHK029 — Is a per-frame CPU inference timeout specified for Florence-2 to prevent indefinite blocking? [NFR, Gap] ⚠️ No timeout defined — a single slow/hung inference call could freeze report generation
- [x] CHK030 — Is the SSE polling interval documented such that the "<500 ms progress update" goal can be validated? [NFR, plan.md §Architecture §SSE Stage Progress Pattern]

---

## Dependencies & Assumptions

- [x] CHK031 — Is the assumption that `transformers` is already installed documented in Spec §Assumptions? [Dependency, Spec §Assumptions]
- [x] CHK032 — Is the dependency on the Phase 6 Qt PDF bridge explicitly listed as a prerequisite assumption? [Dependency, Spec §Assumptions]
- [x] CHK033 — Is the Windows-specific `device_map="cpu"` requirement (not "auto") documented in research.md? [Dependency, research.md §Florence-2-base]
- [x] CHK034 — Is the CLIP model name `'ViT-B-32-quickgelu'` (with `-quickgelu` suffix) documented so implementers use the exact string? [Dependency, research.md §CLIP ViT-B/32]

---

## Ambiguities & Conflicts

- [ ] CHK035 — Does FR-013 create a conflict with FR-007 (format persists)? If the user selects "Markdown only" and the LLM notice only appears in the report header, is the notice visible in PDF format at all? [Ambiguity, Spec §FR-013] — Note: LLM notice is in the report content, not the format modal; no actual conflict but worth confirming
- [x] CHK036 — Is the `object_caption` empty-string contract (not None) for MOG2 events (no crop to describe) documented? [Ambiguity, data-model.md §FrameAnalysis Validation rules]
- [x] CHK037 — Is the SVG `viewBox="0 0 800 48"` coordinate space documented so both the backend SVG generator and any future frontend consumer produce consistent output? [Ambiguity, plan.md §SVG Activity Timeline, data-model.md §ActivityTimeline]

---

## Summary

| Category | Total | Pass | GAP / Needs Attention |
|---|---|---|---|
| Requirement Completeness | 6 | 6 | 0 |
| Requirement Clarity | 6 | 5 | 1 (CHK012) |
| Requirement Consistency | 5 | 3 | 2 (CHK017) |
| Acceptance Criteria Quality | 4 | 4 | 0 |
| Scenario Coverage | 6 | 4 | 2 (CHK025, CHK026) |
| Non-Functional Requirements | 3 | 2 | 1 (CHK029) |
| Dependencies & Assumptions | 4 | 4 | 0 |
| Ambiguities & Conflicts | 3 | 2 | 1 (CHK035, informational) |
| **Total** | **37** | **30** | **7** |

---

## Items Requiring Remediation Before Implementation

| CHK | Severity | Issue | Recommended Fix |
|---|---|---|---|
| CHK012 | LOW | `current=0, total=0` semantics for single-step SSE stages not documented | Add a note to `contracts/api.md` clarifying that single-step stages emit `current=0, total=0` |
| CHK017 | MEDIUM | `report_stage_*` fields not explicitly listed in `_DEFAULTS` | Add explicit note in `data-model.md` that these four fields MUST be in `session.py`'s `_DEFAULTS` |
| CHK025 | MEDIUM | No spec/plan guidance on CLIP sidecar write failure | Add edge case: CLIP write failure → log warning, skip embedding for that event, continue report |
| CHK026 | LOW | Concurrent POST calls from two browser tabs not addressed | Add note: second POST while `report_stage != ""` returns 409; or first POST wins (whichever matches session-first principle) |
| CHK029 | HIGH | No per-frame Florence-2 inference timeout | Add to plan global constraints: Florence-2 inference per frame has a 30 s timeout; on timeout → empty description, log WARN |
| CHK035 | INFO | Potential ambiguity in FR-013 LLM notice visibility in PDF-only mode | Confirm: LLM notice goes in report body section, which IS present in PDF — no conflict |
