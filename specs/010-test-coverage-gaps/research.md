# Research: Phase 10 — Test Coverage Gaps

All decisions below were researched by reading actual source code in the repository
(not external references) to ensure test patterns match production code exactly.

---

## Decision 1: Thread Completion Detection Pattern

**Decision**: Polling loop — `deadline = time.monotonic() + 5; while time.monotonic() < deadline: if session.snapshot()["status"] == "completed": break; time.sleep(0.05)` followed by an assertion on status.

**Rationale**: Tests the same polling behaviour that all real callers use (`GET /api/job` returns `session.snapshot()`). Thread.join() would couple tests to the internal `threading.Thread` object which the endpoint doesn't expose. A threading.Event set by a callback wrapper would require modifying production code.

**Alternatives considered**:
- `thread.join(timeout=5)` — rejected; production code never exposes the thread handle; tests must reach completion through the public session API
- `threading.Event` flag via callback wrapper — rejected; requires adding a wrapper around `on_event` which changes what's being tested

---

## Decision 2: LogBuffer Asyncio Event Loop

**Decision**: Replace `LogBuffer._loop` with a `MagicMock` stub; assert `mock._loop.call_soon_threadsafe.called` with the expected `(queue.put_nowait, line)` arguments.

**Rationale**: `LogBuffer.append()` calls `self._loop.call_soon_threadsafe(q.put_nowait, line)` if `_loop` is not None (line 30 in `log_buffer.py`). The mock stub verifies the bridge call is made correctly without running a real asyncio event loop in a sync pytest session.

**Alternatives considered**:
- `asyncio.new_event_loop()` — rejected; adds real async machinery to a sync test; race conditions possible in CI
- `pytest-asyncio` — rejected; not installed; adds a dependency for marginal benefit when a mock suffices

---

## Decision 3: PyQt6 Module Mocking Strategy

**Decision**: Replace `sys.modules` entries for `PyQt6.QtWidgets`, `PyQt6.QtCore`, `PyQt6.QtWebEngineWidgets`, `PyQt6.QtWebChannel`, `PyQt6.QtGui` with minimal namespace objects (`types.SimpleNamespace` or `MagicMock`) before importing `shell.main_window`. Restore originals in fixture teardown.

**Rationale**: `shell/main_window.py` imports PyQt6 at module level. Patching sys.modules before the first import prevents `ImportError` on CI machines with no display. The fixture must delete `shell.main_window` from `sys.modules` before import to force a fresh module load with stubs active.

**Key stubs needed** (verified from `shell/main_window.py`):
- `QApplication`, `QMainWindow`, `QSystemTrayIcon`, `QMenu`, `QAction` — QtWidgets
- `QTimer`, `QUrl`, `Qt.WindowType`, `pyqtSignal` — QtCore
- `QWebEngineView`, `QWebEngineSettings` — QtWebEngineWidgets
- `QWebChannel` — QtWebChannel
- `QIcon`, `QCloseEvent` — QtGui

**Alternatives considered**:
- Running under `Xvfb` virtual display — rejected; requires system-level setup in CI
- `pytest-qt` — rejected; not installed; heavyweight dependency

---

## Decision 4: FakeDetector and MockDetector Signatures

**Decision**: Both callables must match `detection_engine.run` signature exactly:
```python
def fake_detector(*, source_path, source_info, settings,
                  cancel_event, on_progress, on_event, job_dir):
```
FakeDetector sleeps 50 ms, checks `cancel_event.is_set()`, calls `on_progress(0.5)`, then calls `on_event` twice. MockDetector is a lambda that returns immediately.

**Rationale**: `start_job` monkeypatches `app.core.detection_engine` (imported inside `_run` thread via `from app.core import detection_engine as detector`). The monkeypatch target must be `app.core.detection_engine.run` — replacing the function attribute on the already-imported module.

**Critical finding**: The YOLO path (`req.mode == "yolo"`) imports `app.core.yolo_detector` inside the thread. For YOLO ImportError tests, monkeypatching `builtins.__import__` for `ultralytics` is simpler than monkeypatching the yolo_detector module.

---

## Decision 5: Session Reset Fixture Location

**Decision**: Add shared fixtures to `tests/conftest.py`:
- `app_client` — creates a `starlette.testclient.TestClient` for the FastAPI app
- `ready_session` — calls `session.reset()` then `session.update(status="ready", job_id="test-job-001", source_path="/fake/video.mp4", source_info={...})`

**Rationale**: Multiple test files (US1, US2, US3-API) need the same session + client setup. conftest.py avoids duplication without a premature abstraction.

**Alternative considered**: Per-file fixtures — rejected; DRY principle, and the fixtures are small (< 10 lines each).

---

## Decision 6: Shell Bridge Test Client

**Decision**: Use `starlette.testclient.TestClient(app)` where `app` is the FastAPI application from `app.main`. Mock `shell.platform_utils.open_folder` when testing `POST /shell/open-folder`.

**Rationale**: Shell bridge endpoints are pure FastAPI routes with no Qt dependency. The TestClient approach is consistent with existing tests in `test_api_job.py`.

**Key finding**: `open_output_folder` uses `session.output_path` (the export result, set by export endpoints) — NOT `session.output_dir` (the user-selected folder). Tests must set `output_path` in session, not `output_dir`.

---

## Decision 7: Narrative Synthesizer Test Values

**Decision**: Use these exact expected values, verified from `narrative_synthesizer.py:14-21`:

| Call | Expected | Reason |
|------|----------|--------|
| `seconds_to_clock(0)` | `"00:00"` | `h=0`, `m=0`, `sec=0` → no-hours branch |
| `seconds_to_clock(90)` | `"01:30"` | `h=0`, `m=1`, `sec=30` → no-hours branch |
| `seconds_to_clock(3661)` | `"01:01:01"` | `h=1`, `m=1`, `sec=1` → hours branch |
| `seconds_to_clock(3600)` | `"01:00:00"` | boundary: exactly 1 hour |

**Alternative**: The spec originally had `"0:00:00"`, `"0:01:30"` — these are WRONG. The `f"{h:02d}:{m:02d}:{sec:02d}"` format pads to 2 digits, giving `"01:01:01"` not `"1:01:01"`. The no-hours branch produces `"MM:SS"` (2+2 digits), not `"H:MM:SS"`.

---

## Decision 8: System API Key Names

**Decision**: `GET /api/system/stats` returns `{"cpu_pct", "ram_pct", "cpu_temp"}`. `GET /api/system/capabilities` returns `{"yolo_available"}`.

**Verified from**: `app/api/system.py:13-28`. These differ from what was initially described in the brainstorming spec.

---

## Decision 9: LogBuffer Ring Buffer Size

**Decision**: Test the ring-buffer cap by setting `app.config.LOG_RING_SIZE` to a small value (e.g., 3) via monkeypatching, then appending 4 lines and verifying `subscribe()` replays only 3.

**Rationale**: `LogBuffer._ensure_job` creates `deque(maxlen=LOG_RING_SIZE)` on first use. The `maxlen` is set at deque creation time, so tests must create a fresh `LogBuffer` instance with the patched config value.

---

## No Unresolved Items

All NEEDS CLARIFICATION items from the spec have been resolved. No new unknowns discovered during Phase 0 research.
