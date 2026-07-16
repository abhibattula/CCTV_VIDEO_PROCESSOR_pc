# Checklist: Fast Scan — Performance & Pipeline-Correctness Requirements Quality

**Purpose**: Unit-test the requirements (spec.md + plan.md + research.md) for the six risk clusters named by the author: sampling correctness, decoder fallback completeness, cancellation/orphan handling, quality-parity measurability, GPU no-op guarantees, and backward compatibility — before implementation.
**Created**: 2026-07-15
**Feature**: [spec.md](../spec.md)

## Sampling Correctness (timestamps, VFR, rotation, short clips)

- [x] CHK001 - Are the exact sampling rates for each preset quantified, including the source-fps cap (never upsample)? [Clarity, Spec §FR-002, Edge Cases]
- [x] CHK002 - Is the mapping from sampled frames back to source-time timestamps specified precisely enough to test (formula or invariant)? [Measurability, Spec §FR-005, data-model.md]
- [x] CHK003 - Are variable-frame-rate sources explicitly addressed with an expected behavior (not just named as a risk)? [Coverage, Spec §Edge Cases]
- [x] CHK004 - Is rotated-video behavior specified for BOTH pipelines (sampled and legacy), including which chain handles rotation? [Coverage, Spec §Edge Cases, research.md D7]
- [x] CHK005 - Is the minimum-frames guarantee for clips shorter than one sampling interval stated as a testable requirement? [Measurability, Spec §Edge Cases]
- [x] CHK006 - Is the background-model adaptation-window invariant ("constant in seconds across modes") expressed with concrete derived values that can be asserted? [Clarity, Spec §FR-005, data-model.md]
- [x] CHK007 - Are requirements stated for which detection settings are explicitly NOT rescaled by sampling (spatial thresholds, padding, min gap)? [Completeness, Spec §FR-005]
- [x] CHK008 - Is downstream consumer correctness (thumbnails, exports, reports, search) tied to a defined event-shape invariant rather than assumed? [Consistency, Spec §FR-005, data-model.md "Event dict — unchanged"]

## Decoder Fallback Chain Completeness

- [x] CHK009 - Is the full candidate order specified with unambiguous membership (which methods are in, and why d3d11va is out)? [Completeness, research.md D2]
- [x] CHK010 - Is "verify a candidate works on the actual file" quantified (trial length, success condition)? [Clarity, Spec §FR-003, research.md D2]
- [x] CHK011 - Are requirements defined for mid-run acceleration failure (after trial passed), not just start-time failure? [Coverage, Spec §US2-AC2, Gap]
- [x] CHK012 - Is the terminal fallback (software → legacy loop) defined with an observable trigger condition (zero frames) and a logging requirement? [Completeness, Spec §FR-009]
- [x] CHK013 - Is the "never slower than software due to failed accel" expectation captured as a requirement or acceptance criterion (avoiding the measured d3d11va regression)? [Measurability, Spec §Edge Cases, research.md row 3]
- [x] CHK014 - Are codec-support boundaries specified (what happens for codecs with no qsv/cuda variant)? [Edge Case, research.md D2, Gap]
- [x] CHK015 - Is the per-session caching of the selected chain specified, including cache scope and reset conditions? [Clarity, data-model.md "Decode capability", Gap]

## Cancellation & Orphan-Process Handling

- [x] CHK016 - Is "stops promptly" on cancel quantified or at least bounded (grace period before kill)? [Clarity, Spec §US1-AC3, plan.md close()]
- [x] CHK017 - Is the no-orphaned-process outcome expressed as an objectively checkable criterion (SC-007's re-scan-immediately test)? [Measurability, Spec §SC-007]
- [x] CHK018 - Are file-handle release requirements defined so a cancelled file can be re-scanned/deleted on Windows? [Coverage, Spec §Edge Cases]
- [x] CHK019 - Are requirements defined for child-process cleanup on error/exception paths, not only user cancel? [Coverage, Gap]
- [x] CHK020 - Is the never-hang guarantee for a stalled pipe (no frames, no exit) addressed in requirements? [Edge Case, Spec §Edge Cases "never hang", Ambiguity]

## Quality-Parity Acceptance Criteria

- [x] CHK021 - Is event parity defined with objective matching rules (count tolerance AND per-event overlap), not just "same events"? [Measurability, Spec §SC-002, FR-004]
- [x] CHK022 - Is the parity criterion bound to a specific reference asset and machine so the measurement is reproducible? [Measurability, Spec §Assumptions, SC-001]
- [x] CHK023 - Are speed criteria stated for both accelerated (SC-001/SC-003) and software-only (SC-004) machines? [Coverage, Spec §SC-001–SC-004]
- [x] CHK024 - Is acceptable quality degradation for the Fast preset bounded or explicitly excluded from parity requirements? [Gap, Spec §quickstart #6 "acceptable" — Ambiguity]
- [x] CHK025 - Is Thorough-mode result identity with v1.0.x stated as a testable acceptance criterion? [Measurability, Spec §US1-AC2]

## GPU No-Op Guarantees (CPU-only machines)

- [x] CHK026 - Is the CPU-only no-op requirement stated as "no behavior change" with a concrete verification path (existing suite passes untouched)? [Measurability, Spec §FR-006, SC-005]
- [x] CHK027 - Are requirements defined for torch being entirely absent (not just CUDA-unavailable)? [Edge Case, research.md D6 "import-guarded", Gap]
- [x] CHK028 - Is the AI-device report content specified for both states (cpu / cuda + name)? [Clarity, contracts §2]
- [x] CHK029 - Are the three AI consumers (YOLO, Florence-2, CLIP) all explicitly covered by the device requirement, with none left implicit? [Completeness, Spec §FR-006, plan.md]

## Backward Compatibility (Thorough mode, legacy frame_skip)

- [x] CHK030 - Is the legacy `frame_skip` field's behavior specified for every preset (honored in Thorough, superseded otherwise) including existing API callers? [Completeness, Spec §Edge Cases, contracts §1]
- [x] CHK031 - Is the default-change (implicit every-frame → Balanced) called out as intentional with its user-visible consequence documented? [Clarity, contracts §1 "deliberately", Assumption]
- [x] CHK032 - Are invalid `scan_speed` values covered by an explicit error requirement (status code + allowed values)? [Completeness, contracts §1]
- [x] CHK033 - Is the normalization-guard threshold (30 min) and its message content requirement specific enough to test? [Measurability, Spec §FR-008]
- [x] CHK034 - Do spec, plan, contracts, and data-model use the preset names consistently (thorough/balanced/fast — no drift like "turbo"/"full")? [Consistency]
