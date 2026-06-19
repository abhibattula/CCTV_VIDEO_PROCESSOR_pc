<!--
SYNC IMPACT REPORT
==================
Version change: [TEMPLATE] → 1.0.0 (initial ratification — all placeholders resolved)

Modified principles:
  - [PRINCIPLE_1_NAME] → I. Session-First, No Persistence
  - [PRINCIPLE_2_NAME] → II. Cross-Platform by Default
  - [PRINCIPLE_3_NAME] → III. Test-First (NON-NEGOTIABLE)
  - [PRINCIPLE_4_NAME] → IV. Callback-Driven Processing
  - [PRINCIPLE_5_NAME] → V. Simplicity & YAGNI

Added sections:
  - Cross-Platform Constraints (Section 2)
  - Development Workflow & Quality Gates (Section 3)

Removed sections: none

Templates requiring updates:
  ✅ .specify/templates/plan-template.md — Constitution Check gates updated to reference
     the 5 principles above; no structural changes required
  ✅ .specify/templates/spec-template.md — cross-platform and session-state constraints
     already aligned with FR/SC patterns; no changes required
  ✅ .specify/templates/tasks-template.md — task categories cover foundational
     (session state, FFmpeg path), detection, export, frontend, shell; no changes needed
  ✅ .specify/extensions.yml — no principle references; not affected

Follow-up TODOs:
  - None. All placeholders resolved. Ratification date set to project start (2026-06-19).
-->

# CCTV Video Processor PC — Constitution

## Core Principles

### I. Session-First, No Persistence

All job state MUST live in a single in-memory Python dict (`app/session.py`) protected
by `threading.RLock()`. No SQLite, no database, no file-based state for job data.

- One job at a time. `session.reset()` wipes state before each new job.
- All writes MUST go through `session.update(**kwargs)` to guarantee lock acquisition.
- All reads MUST use `session.snapshot()` which returns a deep copy — never mutate
  the live dict from outside the session module.
- On app exit, all session state is discarded. This is by design: no history, no clutter.

**Rationale**: Eliminates the SQLite crash-on-PC bug (PC-02) at the root. A RAM dict
cannot fail to open, cannot become corrupted, and requires zero setup on any OS.

### II. Cross-Platform by Default

Every file path MUST be constructed via `pathlib.Path`. Bare string concatenation with
`/` or `\\` is PROHIBITED for path operations.

- FFmpeg and ffprobe MUST be resolved through `app/utils/ffmpeg_path.py`
  (`imageio-ffmpeg` bundled binary), never the bare string `"ffmpeg"` in subprocess calls.
- Temp directories MUST use `tempfile.gettempdir()` — never hardcoded `/tmp` or `C:\Temp`.
- The file picker MUST use `QFileDialog` — never Linux-style `"/media/"` or `"/home/"` paths.
- Output folders MUST default to `Path.home() / "Desktop"` — user-overridable, never
  hardcoded `"./outputs/"`.
- CPU temperature reporting MUST be platform-guarded; return `None` on Windows rather
  than failing.

**Rationale**: Fixes PC-03, PC-05, PC-07. The app must run identically on Windows,
macOS, and Linux without any user configuration of PATH or system tools.

### III. Test-First (NON-NEGOTIABLE)

New logic MUST be covered by a failing test before implementation code is written.
The sequence is: write test → run to confirm failure → implement minimal code → run to
confirm pass → commit.

- Tests live in `tests/` and mirror the `app/` structure.
- All tests MUST be runnable with `pytest tests/ -v` from the project root.
- Tests that require external resources (real video file, GPU) MUST be guarded with
  `@pytest.mark.skipif` — skipping is not a failure.
- Thread-safety of `app/session.py` MUST be covered by a concurrent-write test.
- The FFmpeg binary resolver MUST be covered by a path-existence test.

**Rationale**: Prevents regression of the 7 PC-specific bugs and 17 Pi bugs that were
already fixed in the reference implementation. TDD enforces that fixes stay fixed.

### IV. Callback-Driven Processing

Detection and export engines MUST communicate results via injected callbacks, never via
side effects such as database writes, global variable mutation, or direct session access.

The signatures are fixed:
```
on_progress(pct: float)   → called each checkpoint; 0.0–1.0
on_event(ev: dict)        → called for each confirmed motion event
```

- `detection_engine.run()` and `yolo_detector.run()` MUST accept `on_progress` and
  `on_event` as keyword arguments.
- `export_engine.run()` MUST accept `on_progress`.
- Engines MUST NOT import or call `app.session` directly.
- Callers (API layer) wire the callbacks to session mutations.

**Rationale**: Fixes PC-02 at the architecture level. Engines become independently
testable without a running session or database. YOLO and MOG2 share the same interface,
enabling per-job mode selection (PC-06 fix).

### V. Simplicity & YAGNI

No feature, abstraction, or dependency MUST be introduced unless it is required by a
currently active user story.

- Three similar lines of code are better than a premature abstraction.
- No half-finished implementations may be committed.
- Error handling MUST only cover scenarios that can actually occur at the call site —
  no defensive code for impossible states in internal functions.
- The YOLO detector is optional; the app MUST function fully without `ultralytics`
  installed (graceful `ImportError` with install hint).
- Detection resolution MUST auto-scale based on available RAM — no hardcoded 320×240
  remnant from the Pi version (PC-04 fix).

**Rationale**: The Pi version accumulated 24 documented bugs partly due to premature
complexity (global YOLO flag, hardcoded paths, SQLite in the hot loop). Simplicity is
the primary defense against future accumulation.

## Cross-Platform Constraints

These rules apply to ALL code in this repository:

- **No bare `"ffmpeg"` or `"ffprobe"` strings** in any `subprocess` call. Always use
  `get_ffmpeg()` / `get_ffprobe()` from `app/utils/ffmpeg_path.py`.
- **No OS detection for path construction.** `pathlib.Path` handles separators.
  OS detection is permitted only for: opening a folder in the file manager, reading
  CPU temperature, and packaging/distribution.
- **No system-level dependencies** beyond Python 3.11+. FFmpeg is bundled.
  PyQt6 + WebEngine are pip-installable. No Homebrew, apt, or MSI installers required.
- **File paths with spaces MUST work.** `pathlib.Path` and `subprocess` list-form
  commands guarantee this — never shell-string commands.
- **YOLO model cache** MUST be stored at `Path.home() / ".cctv_processor" / "models"` —
  consistent across all platforms.

## Development Workflow & Quality Gates

### Commit Discipline

- Every logical unit of work gets its own commit.
- Commit messages follow: `type(scope): description`
  - `feat:` new capability, `fix:` bug fix, `test:` test-only, `refactor:`, `docs:`, `chore:`
- Never commit broken code to `master`.

### Branch Strategy

- `master` is always runnable (`python launcher.py` works).
- Feature work happens on branches named `###-feature-slug`.
- Merge only after tests pass and the feature is manually smoke-tested.

### Constitution Check (for plan templates)

Before implementing any feature, verify it does not violate:
1. **Principle I**: Does this feature require persistent storage? If yes, justify or reject.
2. **Principle II**: Are all paths via `pathlib.Path`? Is FFmpeg resolved via the utility?
3. **Principle III**: Is there a failing test written before implementation begins?
4. **Principle IV**: Do engines receive callbacks rather than accessing session directly?
5. **Principle V**: Is this the simplest implementation that satisfies the requirement?

Any violation MUST be documented in the plan's Complexity Tracking table with explicit
justification.

## Governance

This constitution supersedes all default practices. When a coding convention conflicts
with a principle here, the constitution wins.

**Amendment procedure:**
1. Propose amendment in a PR with rationale and migration plan for existing code.
2. Update `LAST_AMENDED_DATE` and increment `CONSTITUTION_VERSION` per semver rules:
   - MAJOR: principle removed or redefined incompatibly
   - MINOR: principle added or materially expanded
   - PATCH: wording clarification, typo, non-semantic refinement
3. Propagate changes to plan/spec/tasks templates as described in the Sync Impact Report.
4. All open specs and plans must be re-validated against the new version before merge.

**Compliance review:** Every PR description MUST include a one-line constitution
check: "Constitution check: compliant" or list any approved exceptions.

**Runtime guidance:** See `docs/superpowers/specs/2026-06-19-cctv-pc-processor-design.md`
for architecture detail, and `docs/superpowers/plans/2026-06-19-cctv-pc-processor.md`
for the active implementation plan.

**Version**: 1.0.0 | **Ratified**: 2026-06-19 | **Last Amended**: 2026-06-19
