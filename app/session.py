"""
In-memory session state for the current job.
Single dict protected by a reentrant lock — no database required.
Only one job can be active at a time on this PC app.
"""
import copy
import threading

_lock = threading.RLock()

_DEFAULTS: dict = {
    "status": "idle",           # idle | ready | running | completed | error | cancelled
    "source_path": None,
    "source_info": None,        # SourceInfo dict from ffprobe
    "settings": None,           # detection settings dict
    "progress": 0.0,            # 0.0–1.0
    "eta_s": None,
    "events": [],               # list of MotionEvent dicts
    "event_count": 0,
    "output_path": None,        # set after successful export
    "error_msg": None,
    "pending_path": None,       # shell bridge file-picker result
    "output_dir": None,         # user-selected output folder
    "job_id": None,
}

_state: dict = {}


def reset() -> None:
    """Reset session to initial defaults (called on app start and between jobs)."""
    with _lock:
        _state.clear()
        _state.update(copy.deepcopy(_DEFAULTS))


def update(**kwargs) -> None:
    """Update one or more top-level session fields atomically."""
    with _lock:
        _state.update(kwargs)


def snapshot() -> dict:
    """Return a deep copy of the current session state (safe to mutate)."""
    with _lock:
        return copy.deepcopy(_state)


def append_event(ev: dict) -> None:
    """Append a MotionEvent dict to the events list and increment event_count."""
    with _lock:
        _state["events"].append(ev)
        _state["event_count"] = len(_state["events"])


def toggle_event(idx: int) -> None:
    """Flip the `included` flag on the event at index idx. Raises IndexError if out of range."""
    with _lock:
        # Deliberately raise IndexError for callers to detect invalid idx
        ev = _state["events"][idx]
        ev["included"] = not ev["included"]


# Initialise state on module import
reset()
