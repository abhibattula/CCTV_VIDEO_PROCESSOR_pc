# Implementation Plan: Phase 10 — Test Coverage Gaps

**Branch**: `010-test-coverage-gaps` | **Date**: 2026-06-29 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/010-test-coverage-gaps/spec.md`

## Summary

Add ~58 new pytest tests across 9 test files to close critical coverage gaps identified by a full audit. The six gap categories — zero-coverage modules, missing critical path tests, CI blind spots, thin coverage, Qt shell logic, and test effectiveness — are each addressed by a dedicated user story. All new tests must pass without a video file, GPU, or display server.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: pytest (existing), httpx/starlette TestClient (existing), `unittest.mock` stdlib (no new deps)  
**Storage**: N/A — test phase only; no new persistent state  
**Testing**: `pytest tests/ -v` from project root  
**Target Platform**: Windows 11 (project); tests must pass on any OS in CI  
**Project Type**: Test suite extension for a desktop FastAPI + PyQt6 app  
**Performance Goals**: Full new test suite completes in < 30 s without hardware  
**Constraints**: No `pip install` of new packages required; no display server; no video files; no GPU  
**Scale/Scope**: 9 test files (7 new, 2 expanded), ~58 new test functions, ~198 total

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

1. **Principle I (Session-First, No Persistence)**: Tests use `session.reset()` + `session.update()` per the official API. No file-based or database session state introduced. ✅ **PASS**
2. **Principle II (Cross-Platform Paths)**: New test files use `pathlib.Path` for any path construction. The Qt shell test calls `_get_desktop_path()` which is the already-approved ctypes path — tests do not bypass the abstraction. ✅ **PASS**
3. **Principle III (Test-First)**: This phase *is* the tests — writing them is the primary deliverable. All 9 test files are written before any implementation code is modified. ✅ **PASS** (self-referential)
4. **Principle IV (Callback-Driven)**: FakeDetector and MockDetector signatures match the existing `detection_engine.run` interface (`on_progress`, `on_event` kwargs). No engine-to-session direct coupling introduced. ✅ **PASS**
5. **Principle V (YAGNI)**: No test helper abstraction is introduced unless used by ≥ 2 test files. `conftest.py` only contains session reset fixture and app client fixture — no premature shared utilities. ✅ **PASS**

**Constitution check: compliant** — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/010-test-coverage-gaps/
├── plan.md              ← this file
├── research.md          ← Phase 0 decisions
├── data-model.md        ← test entity definitions
├── quickstart.md        ← how to run and verify
└── tasks.md             ← Phase 2 output (speckit-tasks)
```

### Source Code (test files)

```text
tests/
├── conftest.py                    ← extend: add ready_session + app_client fixtures
├── test_api_job_lifecycle.py      ← NEW: US1 (start_job, cancel_job, get_events)
├── test_api_shell_bridge.py       ← NEW: US2 (shell bridge endpoints)
├── test_log_buffer.py             ← NEW: US3a (LogBuffer contracts)
├── test_clip_indexer.py           ← NEW: US3b (ClipIndexer graceful degradation)
├── test_narrative_synthesizer.py  ← EXPAND: US4 (add 9 tests)
├── test_shell_logic.py            ← NEW: US5 (Qt shell logic via sys.modules mock)
├── test_stream.py                 ← EXPAND: US6 (SSE idle safety, GeneratorExit)
├── test_api_system.py             ← NEW: US6 (system stats + capabilities)
└── test_thumbnail_gen.py          ← EXPAND: US6 (ffmpeg failure path)
```

## Complexity Tracking

*No constitution violations — table not applicable.*
