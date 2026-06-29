# Data Model: Phase 10 — Test Coverage Gaps

This document describes the test entities (fixtures, helpers, stubs) used across
the new test suite. These are not production data models — they are test infrastructure.

---

## Entity: TestSession

**Purpose**: Provides a known-good session state for tests that require a job to be in
`"ready"` status before calling `start_job` or other job-lifecycle endpoints.

**Fields** (set via `session.update()`):

| Field | Value | Notes |
|-------|-------|-------|
| `status` | `"ready"` | Required by `start_job` guard (`app/api/job.py:747`) |
| `job_id` | `"test-job-001"` | Stable ID for all lifecycle tests |
| `source_path` | `"/fake/video.mp4"` | Path doesn't need to exist for start_job tests |
| `source_info` | `{"fps": 25, "duration_s": 10, "width": 1920, "height": 1080}` | Minimal valid dict |
| `progress` | `0.0` | Reset default |
| `events` | `[]` | Empty — tests add events via FakeDetector |
| `event_count` | `0` | Matches events |

**Lifecycle**: Created by `ready_session` fixture in `tests/conftest.py`. Torn down by
next call to `session.reset()` (which every test does via the fixture).

**Relationship**: Used by FakeDetector, MockDetector — they mutate the same session.

---

## Entity: FakeDetector

**Purpose**: Simulates a real detection run for thread lifecycle tests (US1 AC5). Takes
50 ms (real wall clock), emits 2 synthetic events, respects cancel signal.

**Signature** (matches `detection_engine.run` exactly):
```python
def fake_detector(*, source_path, source_info, settings,
                  cancel_event, on_progress, on_event, job_dir):
    time.sleep(0.05)
    if cancel_event.is_set():
        return
    on_progress(0.5)
    on_event({
        "start_s": 0.0, "end_s": 1.0, "zone_label": None,
        "peak_motion_score": 0.8, "included": True, "event_index": 0
    })
    on_event({
        "start_s": 2.0, "end_s": 3.0, "zone_label": None,
        "peak_motion_score": 0.6, "included": True, "event_index": 1
    })
```

**Monkeypatch target**: `app.core.detection_engine.run` (attribute replacement on the
imported module object — not reimporting the module).

**Thread completion detection**: Polling loop in test:
```python
import time
deadline = time.monotonic() + 5
while time.monotonic() < deadline:
    if session.snapshot()["status"] in ("completed", "error", "cancelled"):
        break
    time.sleep(0.05)
```

---

## Entity: MockDetector

**Purpose**: Instant no-op detector for state machine tests (US1 AC1-4). Returns
immediately without sleeping or emitting events.

**Definition**:
```python
mock_detector = lambda *, source_path, source_info, settings, \
                         cancel_event, on_progress, on_event, job_dir: None
```

**Monkeypatch target**: Same as FakeDetector — `app.core.detection_engine.run`.

**Used for**: Tests that check HTTP response codes and session state transitions, where
thread speed matters (we don't want to wait 50 ms when testing a 400 rejection).

---

## Entity: QtStubRegistry

**Purpose**: Minimal Python namespace objects that replace PyQt6 modules in `sys.modules`
before importing `shell.main_window`. Allows testing pure-Python logic without a display.

**Modules patched** (verified from `shell/main_window.py` imports):

| sys.modules key | Stub contents |
|-----------------|---------------|
| `PyQt6.QtWidgets` | `QApplication`, `QMainWindow`, `QSystemTrayIcon`, `QMenu`, `QAction` — all `MagicMock()` |
| `PyQt6.QtCore` | `QTimer` (with `singleShot` tracking), `QUrl`, `Qt` (namespace), `pyqtSignal` |
| `PyQt6.QtWebEngineWidgets` | `QWebEngineView`, `QWebEngineSettings` — `MagicMock()` |
| `PyQt6.QtWebChannel` | `QWebChannel` — `MagicMock()` |
| `PyQt6.QtGui` | `QIcon`, `QCloseEvent` — `MagicMock()` |

**Fixture pattern**:
```python
@pytest.fixture
def mw_module():
    stubs = _make_qt_stubs()
    originals = {k: sys.modules.get(k) for k in stubs}
    sys.modules.update(stubs)
    sys.modules.pop("shell.main_window", None)
    try:
        import shell.main_window as mw
        yield mw
    finally:
        for k, v in originals.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        sys.modules.pop("shell.main_window", None)
```

**Relationship**: Used exclusively by `tests/test_shell_logic.py`.

---

## Entity: SyntheticEvent

**Purpose**: Minimal event dict matching the schema expected by `narrative_synthesizer.py`
functions and assertion helpers.

**Minimal valid schema**:
```python
{
    "start_s": float,     # required by seconds_to_clock and timeline_entries
    "end_s": float,       # required for duration_s calculation
    "zone_label": None,   # None → MOG2 mode; str → YOLO mode
    "peak_motion_score": float,   # 0.0–1.0; used for confidence_pct
    "event_index": int,   # 0-based; used by timeline_entries for description lookup
    "included": True,     # used by callers to filter
}
```

**Extended fields** (used in specific tests):
- `start_clock` — pre-computed clock string; overrides `seconds_to_clock(start_s)` in timeline
- `end_clock` — same for end

**Relationship**: Passed to FakeDetector `on_event` callbacks and narrative synthesizer test functions.

---

## Fixture Dependency Graph

```text
conftest.py
├── session_reset       → calls session.reset() (autouse for all job tests)
├── app_client          → TestClient(app); depends on session_reset
└── ready_session       → app_client + session.update(status="ready", ...)
    ├── test_api_job_lifecycle.py  (US1)
    └── test_api_shell_bridge.py  (US2 — needs app_client)

test_log_buffer.py      → no conftest dependency; creates LogBuffer() directly
test_clip_indexer.py    → no conftest dependency; monkeypatches ClipIndexer
test_narrative_synthesizer.py → no conftest dependency; pure function calls
test_shell_logic.py     → mw_module fixture only (local to file)
test_stream.py          → app_client (existing)
test_api_system.py      → app_client (new, from conftest)
test_thumbnail_gen.py   → existing fixture pattern
```
