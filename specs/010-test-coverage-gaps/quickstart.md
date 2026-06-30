# Quickstart: Phase 10 — Test Coverage Gaps

How to run, verify, and extend the new test suite.

---

## Prerequisites

```
python -m pip install pytest httpx  # already installed from earlier phases
```

No new packages are required for Phase 10.

---

## Running the Tests

### Run the full suite (all 198+ tests)
```
pytest tests/ -v
```
Expected: all tests pass; suite completes in < 60 s without any video file.

### Run only the new Phase 10 test files
```
pytest tests/test_api_job_lifecycle.py tests/test_api_shell_bridge.py \
       tests/test_log_buffer.py tests/test_clip_indexer.py \
       tests/test_shell_logic.py tests/test_api_system.py -v
```

### Run a single story
```
pytest tests/test_api_job_lifecycle.py -v         # US1 — job lifecycle
pytest tests/test_api_shell_bridge.py -v          # US2 — shell bridge
pytest tests/test_log_buffer.py -v                # US3a — LogBuffer
pytest tests/test_clip_indexer.py -v              # US3b — ClipIndexer
pytest tests/test_narrative_synthesizer.py -v     # US4 — narrative
pytest tests/test_shell_logic.py -v               # US5 — Qt shell
pytest tests/test_api_system.py tests/test_stream.py tests/test_thumbnail_gen.py -v  # US6
```

---

## Verification Scenarios

### S1 — Job Lifecycle (US1)

**What to verify**: `start_job` state machine and thread lifecycle.

1. Run `pytest tests/test_api_job_lifecycle.py -v`
2. Verify all tests in `TestStartJobStateMachine` pass: reject-when-detecting, 400-when-yolo-missing, detecting-status-returned
3. Verify all tests in `TestStartJobThreadLifecycle` pass: completed-with-2-events, cancel-stops-thread
4. Verify `test_cancel_job_*` and `test_get_events_*` pass

**Key assertions to look for**:
- `assert status_after == "detecting"` (immediate response)
- `assert final_status == "completed"` (after polling loop)
- `assert snap["event_count"] == 2`

---

### S2 — Shell Bridge (US2)

**What to verify**: Browse/drag-drop API endpoints.

1. Run `pytest tests/test_api_shell_bridge.py -v`
2. Verify `test_set_filepath_stores_path` passes
3. Verify `test_get_pending_path_clears_on_read` passes (critical: second call returns `null`)
4. Verify `test_open_folder_*` tests pass with mocked `platform_utils.open_folder`

---

### S3 — LogBuffer (US3a)

**What to verify**: Ring buffer caps and pub/sub.

1. Run `pytest tests/test_log_buffer.py -v`
2. Verify `test_subscribe_replays_history` passes
3. Verify `test_ring_buffer_cap` passes (buffer never exceeds `LOG_RING_SIZE`)
4. Verify `test_reset_clears_only_target_job` passes

---

### S4 — ClipIndexer (US3b)

**What to verify**: Graceful degradation when `open_clip` is absent.

1. Run `pytest tests/test_clip_indexer.py -v`
2. Verify `test_embed_returns_none_when_unavailable` passes
3. Verify `test_embed_returns_none_on_exception` passes (never raises to caller)
4. Verify `test_embed_returns_sidecar_path_on_success` passes

---

### S5 — Narrative Synthesizer (US4)

**What to verify**: seconds_to_clock formatting and timeline_entries structure.

1. Run `pytest tests/test_narrative_synthesizer.py -v`
2. Verify `test_seconds_to_clock_zero` passes: `"00:00"`
3. Verify `test_seconds_to_clock_90s` passes: `"01:30"` (2-digit MM:SS, no hours)
4. Verify `test_seconds_to_clock_over_hour` passes: `"01:01:01"`
5. Verify `test_timeline_entries_structure` passes with 3 required keys

---

### S6 — Qt Shell Logic (US5)

**What to verify**: closeEvent and _get_desktop_path without a display.

1. Run `pytest tests/test_shell_logic.py -v`
2. Verify all tests import successfully (no ImportError despite PyQt6 absence)
3. Verify `test_get_desktop_path_returns_string` passes
4. Verify `test_close_event_hides_when_detecting` passes
5. Verify `test_close_event_quits_when_idle` passes

---

### S7 — System API (US6)

**What to verify**: Exact key names in system endpoints.

1. Run `pytest tests/test_api_system.py -v`
2. Verify `test_system_stats_keys` passes: response has `cpu_pct`, `ram_pct`, `cpu_temp`
3. Verify `test_system_capabilities_without_ultralytics` passes: `yolo_available == False`

---

### S8 — Full Suite Regression

**What to verify**: No existing tests broken.

1. Run `pytest tests/ -v`
2. Verify total count ≥ 195
3. Verify 0 failures and 0 errors
4. Verify any skipped tests are only the pre-existing video-dependent ones (not new ones)

---

## Troubleshooting

**Import error on shell.main_window** — The `mw_module` fixture must patch sys.modules before importing. If the module was already imported earlier in the test session, del it from sys.modules in the fixture setup.

**LogBuffer ring buffer test fails** — The `deque(maxlen=...)` is set at creation time. Tests must create a fresh `LogBuffer()` instance after patching `app.config.LOG_RING_SIZE`, not reuse the module-level singleton.

**Thread lifecycle test times out** — The polling loop waits 5 s. If FakeDetector's `on_event` calls fail (signature mismatch), the thread will raise, session will become `"error"`, and the loop will exit immediately — check session's `error_msg`.

**yolo_available is True in system capabilities test** — If `ultralytics` is installed in the test environment, the capabilities test will return `True`. The test should monkeypatch the import to raise `ImportError`:
```python
import builtins, importlib
real_import = builtins.__import__
def fake_import(name, *args, **kwargs):
    if name == "ultralytics":
        raise ImportError("mocked")
    return real_import(name, *args, **kwargs)
monkeypatch.setattr(builtins, "__import__", fake_import)
```
