# Feature Specification: Fast Scan — Detection Performance Overhaul

**Feature Branch**: `015-fast-scan-performance`
**Created**: 2026-07-15
**Status**: Draft
**Input**: User description: "Make motion/object detection dramatically faster on long recordings (target: 24-hour CCTV files) by eliminating the decode-everything bottleneck, adding a user-facing scan-speed control, and opportunistically using GPU hardware where available — while finding the same events as today. Design doc: docs/superpowers/specs/2026-07-15-fast-scan-design.md (user-approved, benchmark-backed)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Long recordings finish in a fraction of the time (Priority: P1)

A security reviewer loads a long CCTV recording (hours up to a full day), picks how thorough the scan should be — or just keeps the default — and starts detection. The scan completes several times faster than it does today, and the events found are the same ones the slow scan would have found: same incidents, same time ranges, reviewable on the Timeline exactly as before.

**Why this priority**: This is the whole point of the phase. Detection speed is the single biggest usability ceiling for real CCTV work — a 24-hour file currently takes on the order of half a day to process, which makes daily review impractical.

**Independent Test**: Run detection twice on the reference test video (115 s, high-bitrate 1080p60), once in Thorough mode and once in Balanced mode. Balanced must finish at least 3× faster and produce the same events (count within ±1, overlapping time ranges).

**Acceptance Scenarios**:

1. **Given** a video is loaded and scan speed is Balanced (the default), **When** the user starts detection, **Then** detection completes at least 3× faster than Thorough mode on the same file and the Timeline shows the same events (count ±1, overlapping time ranges).
2. **Given** a video is loaded, **When** the user selects Thorough scan speed and starts detection, **Then** the system behaves exactly as the current release (every frame analyzed, identical results to v1.0.x).
3. **Given** a detection run is in progress in any scan mode, **When** the user cancels, **Then** the run stops promptly and the app remains usable (no orphaned background work).
4. **Given** detection completed in Balanced or Fast mode, **When** the user reviews events, exports clips, generates reports, or searches events, **Then** all timestamps, thumbnails, exports, and report content refer to the correct moments in the original video.

---

### User Story 2 - The scan is as fast as this machine can go, automatically (Priority: P2)

The user does nothing special: on a machine with capable graphics hardware (Intel integrated graphics, NVIDIA card), the app automatically uses the hardware's video decoder and — where a compatible GPU exists — runs AI analysis on it. On a machine with no usable acceleration, everything still works, just at software speed. The user can see which acceleration is active.

**Why this priority**: Acceleration multiplies the User Story 1 gains (measured 3.6× decode speedup on the developer's Intel machine) but must never be a prerequisite — the app's promise is "works offline on ordinary hardware."

**Independent Test**: On the development machine (Intel graphics, no NVIDIA), start a Balanced scan and confirm the hardware decode path is chosen and reported; force acceleration to fail and confirm the scan still completes via software. Confirm AI analysis still runs on CPU (no CUDA present) with unchanged results.

**Acceptance Scenarios**:

1. **Given** a machine with a supported hardware video decoder, **When** detection starts, **Then** the system verifies the accelerated path actually works on this file before committing to it, and uses it.
2. **Given** acceleration fails verification or fails mid-run, **When** detection proceeds, **Then** the system falls back to the software path automatically and the run still completes correctly.
3. **Given** any machine, **When** the user views system/app status, **Then** the active video decode method and AI compute device (GPU or CPU) are visible.
4. **Given** a machine with a CUDA-capable GPU and GPU-enabled AI stack, **When** AI analysis (object labeling, frame descriptions, search indexing) runs, **Then** it uses the GPU; **Given** a CPU-only machine (like the user's), **Then** behavior and results are unchanged from today.

---

### User Story 3 - No silent multi-hour surprises on problem files (Priority: P3)

A user loads a very long file that turns out to be malformed in a way that previously triggered a silent full re-encode before analysis. Instead of the app disappearing into hours of unexplained work, the user sees a clear warning about what is happening and why, with an idea of the cost, before/while it proceeds.

**Why this priority**: A rare path, but on a 24-hour file it is catastrophic (hours of hidden work + double disk usage). Cheap to guard once the new pipeline exists — and the new pipeline itself tolerates malformed streams better, so this path fires less often.

**Independent Test**: Simulate a file that fails to open normally; confirm (a) the new pipeline attempts it first, and (b) if the repair fallback is reached on a long file, a clear warning with an estimated cost is logged/visible rather than silence.

**Acceptance Scenarios**:

1. **Given** a malformed video the accelerated pipeline can still read, **When** detection runs, **Then** no re-encode happens and the scan completes normally.
2. **Given** a malformed long video that genuinely requires repair before analysis, **When** the repair fallback triggers, **Then** the user sees a clear message stating that a one-time repair is running, why, and its approximate scale — before hours are spent silently.

---

### Edge Cases

- Source video's native frame rate is at or below the sampled analysis rate (e.g., 2 fps timelapse in Balanced 5 fps mode): system must analyze at the native rate, never duplicate/upsample frames, and never divide by zero.
- Variable-frame-rate recordings (common on phones/dashcams): sampled timestamps must still map to correct source moments.
- Rotated video (portrait phone footage with rotation metadata): analyzed frames must respect the same orientation the user sees in players and exports.
- Cancel/stop during a sampled scan: the decoding child process must terminate promptly (no orphaned FFmpeg process, no locked file handle preventing re-run).
- Zero frames delivered by the new pipeline (codec quirk, truncated file): automatic fallback to the legacy path; the run must still complete or fail with a clear error — never hang.
- Extremely short clips (shorter than one sampling interval): at least one frame must be analyzed.
- Existing API callers passing the legacy `frame_skip` field: must not break; field remains honored in Thorough mode, superseded by scan speed otherwise.
- Machine where the hardware decoder exists but is slower than software (measured on the dev machine for naive full-resolution copy-back): selection logic must avoid configurations that are slower than software.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to choose a scan speed — Thorough, Balanced, or Fast — when starting detection, with Balanced as the default; the choice MUST be available where detection is configured (alongside sensitivity) and via the start-detection API.
- **FR-002**: Balanced and Fast modes MUST analyze the video at a reduced, fixed sampling rate (Balanced ≈ 5 frames/second, Fast ≈ 2 frames/second of source time) instead of every frame; Thorough mode MUST preserve the current every-frame behavior and results.
- **FR-003**: The system MUST automatically select the fastest working video decode method available on the machine (Intel hardware decode, NVIDIA hardware decode, or software), MUST verify a candidate works on the actual file before committing to it, and MUST fall back through the chain (ending at software, then at the legacy path) without user intervention.
- **FR-004**: Detection quality MUST be preserved in Balanced mode: on the reference test asset, Balanced finds the same events as Thorough (count within ±1; each event's time range overlaps its counterpart).
- **FR-005**: All user-facing timing semantics MUST be unchanged by scan speed: minimum event duration, merge gap, and padding remain in seconds of source time; event timestamps, thumbnails, exports, reports, and search must reference correct source-video moments; the background model's adaptation window MUST remain constant in seconds of source time across modes.
- **FR-006**: AI analysis stages (object detection, frame description, search embedding) MUST use a compatible GPU automatically when one is available to the installed AI stack, and MUST behave exactly as today on CPU-only machines — no user configuration, no behavior change without a GPU.
- **FR-007**: The system MUST report the active acceleration status — video decode method in use and AI compute device — through the existing system-capabilities surface, and the UI MUST make it visible to the user.
- **FR-008**: The repair/re-encode fallback for malformed files MUST NOT run silently on long inputs: when triggered for a video longer than 30 minutes, the system MUST emit a clear, user-visible warning describing the one-time repair and its approximate scale before proceeding.
- **FR-009**: If the sampled pipeline delivers no frames for a readable video, the system MUST automatically complete the run via the legacy detection path (correctness over speed), logging that fallback occurred.
- **FR-010**: The feature MUST work fully offline, add no new runtime dependencies, and keep all detection engines callback-driven (no session imports from engines).

### Key Entities

- **Scan speed preset**: A named trade-off (Thorough / Balanced / Fast) mapping to an analysis sampling rate; part of detection settings for a job; not persisted beyond the session.
- **Decode capability**: The machine's detected video-acceleration status (chosen decode method per codec, AI compute device); derived at runtime, surfaced read-only to the UI.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the 115 s reference video, a Balanced scan completes end-to-end at least 3× faster than a Thorough scan on the same machine.
- **SC-002**: On the 115 s reference video, Balanced mode finds the same events as Thorough mode: count within ±1 and overlapping time ranges for each matched event.
- **SC-003**: On the developer machine, Balanced mode processes high-bitrate 1080p60 footage at 6× real-time or better (a 24-hour file of that class in ≤ 4 hours), versus ~1.7× real-time today.
- **SC-004**: On a machine with no usable hardware acceleration, Balanced mode is still at least 1.2× faster than the current release on the reference video (software-only gain).
- **SC-005**: The full existing test suite (~274 tests) passes unchanged, and at least 12 new tests cover the new pipeline, presets, fallbacks, and capability reporting.
- **SC-006**: A user can determine from the UI, without documentation, which acceleration (video decode method, AI device) is active on their machine.
- **SC-007**: Cancelling a sampled scan leaves no orphaned decoding process and the same file can be re-scanned immediately.

## Assumptions

- The bundled FFmpeg (imageio-ffmpeg 7.1) remains the only external media tool; its presence is already a hard dependency of the app.
- Analyzing at ~5 fps is sufficient for CCTV motion review given the existing 2-second minimum event duration (≥10 samples per minimum event); the Thorough preset remains available for users who want every frame.
- The reference test asset is the local 115 s HEVC 1080p60 clip used for Phase 14 E2E verification; benchmarks cited (8× real-time accelerated, 1.7× current) were measured on the developer's machine on 2026-07-15.
- The user's own machine has Intel integrated graphics (hardware decode benefits apply) and no CUDA GPU (AI stays on CPU there); CUDA benefit applies only to installs with a CUDA-enabled AI stack — the shipped installers bundle a CPU-only stack, so GPU AI is effectively for source installs today.
- The legacy `frame_skip` API field is retained for backward compatibility (honored in Thorough mode) but the new scan-speed presets supersede it; the UI never exposed it, so no UI migration is needed.
- Heatmap, progress reporting, preview, and report generation consume whatever frames the detection loop processes; reduced sampling changes their granularity proportionally but not their correctness.
- The event-parity requirement (FR-004/SC-002) applies to Balanced mode only. Fast mode is an explicit user-chosen recall trade-off: brief events may merge or shorten; no parity criterion is defined for it.
- This phase ships in v1.1.0 together with Phase 14 (CLIP event search) and the CLIP download fix.
