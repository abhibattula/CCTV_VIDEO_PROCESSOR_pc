<!--
SYNC IMPACT REPORT
==================
Version change: 1.1.0 → 1.2.0 (MINOR — Principle III materially expanded, not redefined)

Modified principles:
  - III. Test-First (NON-NEGOTIABLE) — added an explicit frontend-JS exemption from
    the automated failing-test-first sequence (no JS test runner exists in this
    stack by deliberate choice), scoped narrowly so it does NOT extend to any
    backend Python logic. Closes a gap first identified during the
    002-ui-tag-filter analyze pass and left unresolved at the time; re-identified
    during 003-phase3-deferred-items's analyze pass and fixed immediately rather
    than deferred again.

Added sections: none (amendment is within existing Principle III)

Removed sections: none

Templates requiring updates:
  ✅ .specify/templates/plan-template.md — Constitution Check question 3 ("Is there
     a failing test written before implementation begins?") now has a documented
     "N/A — frontend, see quickstart.md" answer path; no structural change needed
  ✅ .specify/templates/spec-template.md — no change required
  ✅ .specify/templates/tasks-template.md — no change required
  ✅ .specify/extensions.yml — no principle references; not affected

Follow-up TODOs:
  - None. Prior amendment (1.0.0 → 1.1.0, Principle I user-configuration exemption
    for custom export presets) remains in effect unchanged below.
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
- User configuration is exempt from this principle and MAY be persisted to a single
  flat file under `Path.home() / ".cctv_processor"`, following the same pattern as
  `MODEL_DIR` in `app/config.py`. User configuration is defined narrowly: named,
  reusable settings the user explicitly chose to save (e.g. export presets), which
  are NOT derived from and have NO reference to any specific job, video file, or
  detection run. A config file MUST NOT store any key present in `app/session.py`'s
  `_DEFAULTS` dict (the full set of job-state fields, kept there as the single source
  of truth — not re-enumerated here, since a copy would drift out of sync as fields
  are added) and MUST NOT be written to automatically — only on an explicit user
  action (e.g. a "Save as Preset" click), never as a side effect of detection or
  export. Job state remains exclusively in-memory and is wiped by `session.reset()`
  exactly as before.

**Rationale**: Eliminates the SQLite crash-on-PC bug (PC-02) at the root. A RAM dict
cannot fail to open, cannot become corrupted, and requires zero setup on any OS.
User configuration (e.g. saved export presets) is a different category from job
state: it has no relationship to "the current job," is written rarely and only on
explicit user action, and its loss is a minor inconvenience rather than a correctness
bug — unlike job state, where stale persisted data was the actual root cause of PC-02.

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
- Frontend JavaScript (`static/js/`) is exempt from the automated failing-test-first
  sequence above, since this project deliberately has no build step, no npm, and no
  JS test runner (Principle V: simplicity over adding one). Frontend logic MUST
  instead be verified by directly driving the running application — manually, or via
  a temporary script that launches a real `QWebEngineView`/`MainWindow` instance and
  is deleted after use — with the scenario documented in the feature's
  `quickstart.md` before the corresponding task is marked complete. This exemption
  does NOT extend to `app/api/*.py` or `app/core/*.py`: any backend Python logic,
  including code that only serves frontend-adjacent endpoints, MUST still follow the
  standard write-test-first sequence.

**Rationale**: Prevents regression of the 7 PC-specific bugs and 17 Pi bugs that were
already fixed in the reference implementation. TDD enforces that fixes stay fixed.
The frontend exemption reflects a real, repeatedly-confirmed constraint (this stack
has shipped two full phases plus several follow-up features with no JS test runner)
rather than a loophole — Python backend logic remains fully bound by this principle
with no exceptions.

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
1. **Principle I**: Does this feature require persistent storage? If yes, justify or
   reject — unless it is user configuration (named, reusable, user-saved settings with
   no reference to any specific job), which is pre-approved per the Principle I
   exemption and does not need separate justification.
2. **Principle II**: Are all paths via `pathlib.Path`? Is FFmpeg resolved via the utility?
3. **Principle III**: Is there a failing test written before implementation begins? —
   for `app/api/*.py`/`app/core/*.py` changes this is required with no exception;
   for `static/js/` changes, cite the frontend exemption and point to the
   corresponding `quickstart.md` scenario instead.
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

**Version**: 1.2.0 | **Ratified**: 2026-06-19 | **Last Amended**: 2026-06-21
