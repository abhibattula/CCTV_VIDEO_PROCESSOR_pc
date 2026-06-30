import threading
import copy
import pytest
import app.session as session_module
from app.session import reset, update, snapshot, append_event, toggle_event, bulk_toggle_events


def test_initial_status_is_idle():
    reset()
    s = snapshot()
    assert s["status"] == "idle"


def test_update_changes_fields():
    reset()
    update(status="running", progress=0.5)
    s = snapshot()
    assert s["status"] == "running"
    assert s["progress"] == 0.5


def test_snapshot_returns_deep_copy():
    reset()
    update(status="running")
    s1 = snapshot()
    s1["status"] = "mutated"
    s2 = snapshot()
    assert s2["status"] == "running"


def test_append_event_adds_to_list():
    reset()
    ev = {"start_s": 1.0, "end_s": 2.0, "peak_score": 0.8, "included": True}
    append_event(ev)
    s = snapshot()
    assert len(s["events"]) == 1
    assert s["events"][0]["start_s"] == 1.0


def test_toggle_event_flips_included():
    reset()
    append_event({"start_s": 0.0, "end_s": 1.0, "peak_score": 0.5, "included": True})
    toggle_event(0)
    s = snapshot()
    assert s["events"][0]["included"] is False
    toggle_event(0)
    s2 = snapshot()
    assert s2["events"][0]["included"] is True


def test_toggle_event_out_of_range_raises():
    reset()
    with pytest.raises((IndexError, KeyError)):
        toggle_event(99)


# ── T003: bulk_toggle_events tests (TDD — written before implementation) ────


def test_bulk_toggle_include():
    reset()
    append_event({"start_s": 0.0, "end_s": 1.0, "peak_motion_score": 0.5, "included": False})
    append_event({"start_s": 1.0, "end_s": 2.0, "peak_motion_score": 0.6, "included": False})
    bulk_toggle_events([0, 1], include=True)
    s = snapshot()
    assert s["events"][0]["included"] is True
    assert s["events"][1]["included"] is True


def test_bulk_toggle_exclude():
    reset()
    append_event({"start_s": 0.0, "end_s": 1.0, "peak_motion_score": 0.5, "included": True})
    append_event({"start_s": 1.0, "end_s": 2.0, "peak_motion_score": 0.6, "included": True})
    bulk_toggle_events([0, 1], include=False)
    s = snapshot()
    assert s["events"][0]["included"] is False
    assert s["events"][1]["included"] is False


def test_bulk_toggle_invalid_index():
    reset()
    append_event({"start_s": 0.0, "end_s": 1.0, "peak_motion_score": 0.5, "included": True})
    with pytest.raises((IndexError, KeyError)):
        bulk_toggle_events([0, 99], include=False)


def test_thread_safe_concurrent_updates():
    reset()
    errors = []

    def worker(i):
        try:
            update(progress=i / 50.0)
            append_event({"start_s": float(i), "end_s": float(i) + 1, "peak_score": 0.5, "included": True})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Thread errors: {errors}"
    s = snapshot()
    assert len(s["events"]) == 50


# ── Phase 9 TDD tests (B6: output_dir persists across reset) ────────────────

def test_output_dir_persists_across_reset():
    """output_dir set by user MUST survive session.reset() (new video load).
    Written before implementation — MUST FAIL until _PERSISTENT dict added."""
    reset()
    update(output_dir="/custom/exports")
    reset()  # simulates loading a new video
    s = snapshot()
    assert s.get("output_dir") == "/custom/exports", (
        "output_dir was wiped by reset() — implement _PERSISTENT dict in app/session.py"
    )
