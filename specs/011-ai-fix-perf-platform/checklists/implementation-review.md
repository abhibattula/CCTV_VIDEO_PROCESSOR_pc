# Implementation Review Checklist: AI Fix, Performance & Cross-Platform

**Purpose**: Validate requirement quality, completeness, and measurability across all three tracks before implementation begins  
**Created**: 2026-06-30  
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md)  
**Audience**: PR reviewer  
**Depth**: Standard

---

## Requirement Completeness

- [ ] CHK001 - Are all three root causes of Florence-2 garbage output individually addressed by separate functional requirements? [Completeness, Spec §FR-001, FR-002, FR-003]
- [ ] CHK002 - Is the requirement for warning suppression scoped to specific warning categories (UserWarning, DeprecationWarning) rather than a blanket suppress-all? [Completeness, Spec §FR-004]
- [ ] CHK003 - Is the `AI_FEATURES_ENABLED` threshold value (5.0 GB) specified in the requirements, or only in implementation notes? [Clarity, Spec §FR-005, FR-015]
- [ ] CHK004 - Is the YOLO warm-up requirement specified for the failure case (what happens if warm-up thread raises an exception)? [Completeness, Spec §FR-009, Edge Cases]
- [ ] CHK005 - Are requirements defined for the case where ultralytics is installed but the model weights cannot be downloaded (network outage)? [Gap, Spec §FR-009]
- [ ] CHK006 - Is the frame skip ratio (3 on PC, 6 on Pi) specified as a requirement or only as a plan-level implementation detail? [Clarity, Spec §FR-010]
- [ ] CHK007 - Are the README platform sections defined as a functional requirement (FR-019) with sufficient detail to be verifiable? [Completeness, Spec §FR-019]

---

## Requirement Clarity

- [ ] CHK008 - Is "readable English sentence" in SC-001 defined with measurable criteria, or is it subjective? [Clarity, Spec §SC-001]
- [ ] CHK009 - Does FR-008 specify what constitutes a "successful message received" that resets the SSE retry counter? [Clarity, Spec §FR-008]
- [ ] CHK010 - Is the 2-second progress callback interval in FR-011 a wall-clock guarantee or a best-effort target? [Clarity, Spec §FR-011]
- [ ] CHK011 - Is the desktop path fallback chain (`$XDG_DESKTOP_DIR` → `~/Desktop` → `~/Downloads` → `~/`) specified with clear precedence rules (e.g., what if `~/Desktop` exists but is not writable)? [Clarity, Spec §FR-014]
- [ ] CHK012 - Does FR-016 define what "close-to-tray only attempted when available" means for the user — does the window simply close? Quit the app? [Clarity, Spec §FR-016, US4 AC3]
- [ ] CHK013 - Is "Pi 4 / Pi 5 only" clearly stated as an explicit assumption (Pi 2/3 not supported), and is this discoverable from the spec without reading the Assumptions section? [Clarity, Spec §Assumptions]

---

## Requirement Consistency

- [ ] CHK014 - Does SC-007 (≥205 tests) align with the plan's statement of "10 new tests" + 195 existing? Is the arithmetic consistent? [Consistency, Spec §SC-007, Plan §Phase 6]
- [ ] CHK015 - Is the `max_new_tokens` value consistent between the spec (mentions fix but not the value) and the plan (100)? Should the spec reference the value for traceability? [Consistency, Spec §FR-003, Plan §1C]
- [ ] CHK016 - Does US2 AC1 ("ready by the time Start is clicked") conflict with the plan's "60s timeout wait" behaviour — what if the user clicks Start in <1 second? [Consistency, Spec §US2 AC1, Plan §3B]
- [ ] CHK017 - Are the SSE retry parameters (5 retries, 3s backoff) consistent between FR-008 in the spec and the plan's implementation section? [Consistency, Spec §FR-008, Plan §Phase 2]

---

## Acceptance Criteria Quality

- [ ] CHK018 - Is SC-001 (zero occurrences of raw tokens in report) objectively verifiable without requiring Florence-2 to run? Can it be tested with the unit sanitiser alone? [Measurability, Spec §SC-001]
- [ ] CHK019 - Is SC-002 (zero terminal warnings) verifiable in the automated test suite, or does it require a manual terminal inspection run? [Measurability, Spec §SC-002]
- [ ] CHK020 - Is SC-004 ("log messages emitted during absence visible on return") measurable — is there a defined maximum reconnect window within which this guarantee holds? [Measurability, Spec §SC-004]
- [ ] CHK021 - Is SC-005 (florence2_available: false on <5 GB RAM) verifiable without a real low-RAM device — is there a mock/override path specified? [Measurability, Spec §SC-005]
- [ ] CHK022 - Are the acceptance scenarios in US3 (log panel) sufficient to cover the case where the SSE connection never successfully reconnects? [Acceptance Criteria, Spec §US3]

---

## Scenario Coverage

- [ ] CHK023 - Are requirements defined for the case where a user starts detection with YOLO mode but ultralytics is NOT installed (ImportError path)? [Coverage, Spec §Edge Cases, FR-009]
- [ ] CHK024 - Are requirements specified for concurrent jobs — what happens if the user creates a second job before warm-up for the first is complete? [Gap, Spec §US2]
- [ ] CHK025 - Is the Linux headless scenario (no Qt, backend only) covered by a user story with acceptance criteria, or only mentioned in an assumption? [Coverage, Spec §US4 AC5]
- [ ] CHK026 - Are requirements defined for the Windows case where `SHGetFolderPathW` succeeds but returns a path that does not exist on disk? [Gap, Spec §FR-014, Edge Cases]
- [ ] CHK027 - Is there a requirement covering what happens when `get_desktop_path()` is called during an export and all fallback paths fail (e.g., `~/` does not exist)? [Coverage, Spec §FR-014]

---

## Edge Case Coverage

- [ ] CHK028 - Is the `AI_FEATURES_ENABLED=False` edge case (exactly 5.0 GB RAM) specified clearly — does ≥5.0 mean 5.0 exactly enables, or does it require >5.0? [Clarity, Spec §Edge Cases, FR-015]
- [ ] CHK029 - Is the YOLO warm-up edge case (ultralytics not installed) specified — does `prewarm()` raise, no-op, or set `_model_ready`? [Completeness, Spec §Edge Cases, FR-009]
- [ ] CHK030 - Is the SSE "Connection lost" fallback behaviour defined — does the app continue to poll indefinitely, or does it stop after job completion? [Coverage, Spec §FR-008]
- [ ] CHK031 - Are requirements defined for the Pi 4 with 8 GB RAM variant — does it get `AI_FEATURES_ENABLED=True` (≥5 GB), and is YOLO still frame-skipped at 6? [Gap, Spec §FR-010, FR-015]

---

## Non-Functional Requirements

- [ ] CHK032 - Is the 90-second per-task inference timeout documented as an existing constraint in the spec, or only in the plan? Should FR-003 reference it? [Completeness, Spec §FR-003, Plan §research Decision 2]
- [ ] CHK033 - Are RAM consumption requirements specified for the YOLO warm-up thread — does caching the model in `_cached_yolo_model` increase peak memory, and is this acceptable on 8 GB PC? [Gap, Spec §Assumptions]
- [ ] CHK034 - Is the test suite execution time (SC-007) constrained — the Phase 10 suite took 50+ minutes due to the YOLO video test; is the 205-test target for the standard (fast) run or the full run? [Clarity, Spec §SC-007]

---

## Dependencies & Assumptions

- [ ] CHK035 - Is the assumption "Florence-2 model weights already cached" explicitly stated and does the spec define what happens when weights are absent on an AI-enabled device? [Assumption, Spec §Assumptions]
- [ ] CHK036 - Is the dependency on `psutil` (for `_total_gb` RAM detection) validated — is it listed in requirements.txt and confirmed available on all target platforms? [Dependency, Spec §Assumptions]
- [ ] CHK037 - Is the assumption that `LogBuffer.subscribe()` already replays 100 lines (which eliminates the need for a new `snapshot()` method) documented as a discovered constraint rather than a design decision? [Assumption, Plan §research Decision 1]
- [ ] CHK038 - Are the Raspberry Pi OS version requirements (64-bit Bookworm) explicitly stated as a hard requirement, and is the consequence of using an older OS version (Bullseye) documented? [Dependency, Spec §Assumptions]

---

## Notes

- Items marked with [Gap] indicate requirements that may need to be added or clarified before implementation.
- CHK016 is the highest-priority item: the US2 AC1 wording could create a false expectation that warm-up always completes before Start — the 60s wait behaviour needs to be reflected in the user story.
- CHK031 is a latent issue: Pi 4 8 GB would get `AI_FEATURES_ENABLED=True` and `YOLO_FRAME_SKIP=6` — is that combination intended?
- Items marked complete: `[x]`
