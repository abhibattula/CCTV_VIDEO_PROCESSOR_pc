"""
In-memory session state for the current job.
Single dict protected by a reentrant lock — no database required.
Only one job can be active at a time on this PC app.
"""
import copy
import threading

_lock = threading.RLock()

_DEFAULTS: dict = {
    "status": "idle",           # idle | ready | detecting | completed | cancelled | error
                                 # | exporting | export_done | export_error
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
    "job_id": None,
    # Phase 7 — report generation SSE progress (H1 race condition fix)
    "report_stage": "",             # "" | "thumbnails" | "ai_analysis" | "markdown" | "pdf"
    "report_stage_current": 0,      # items processed in current stage
    "report_stage_total": 0,        # total items in current stage
    "report_stage_timestamp": "",   # clock string of most-recently processed event
    "report_done_pending": False,   # True until SSE loop emits report_done event
}

# Fields in _PERSISTENT survive session.reset() — they represent user preferences
# that should not be wiped when loading a new video (e.g., output_dir chosen by user).
_PERSISTENT: dict = {
    "output_dir": None,         # user-selected output folder; preserved across video loads
}

_state: dict = {}


def reset() -> None:
    """Reset session to initial defaults (called on app start and between jobs)."""
    with _lock:
        # Preserve user preferences before clearing job state
        saved_persistent = {k: _state.get(k, _PERSISTENT[k]) for k in _PERSISTENT}
        _state.clear()
        _state.update(copy.deepcopy(_DEFAULTS))
        _state.update(saved_persistent)


def update(**kwargs) -> None:
    """Update one or more top-level session fields atomically."""
    with _lock:
        _state.update(kwargs)
        # Keep _PERSISTENT in sync so reset() preserves the latest value
        for k in _PERSISTENT:
            if k in kwargs:
                _PERSISTENT[k] = kwargs[k]


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


def bulk_toggle_events(indices: list, include: bool) -> None:
    """Set included=include for all events at the given indices atomically. Raises IndexError on invalid idx."""
    with _lock:
        for idx in indices:
            _state["events"][idx]["included"] = include


def patch_event_field(event_index: int, **fields) -> None:
    """Update arbitrary fields on the event with the given event_index. No-op if not found."""
    with _lock:
        for ev in _state["events"]:
            if ev.get("event_index") == event_index:
                ev.update(fields)
                break


# Initialise state on module import
reset()


# ---------------------------------------------------------------------------
# Session proxy object — some callers (tests, new API code) prefer
# session_module.session.reset() / .update() / .snapshot() over the
# module-level functions.  This lightweight proxy delegates to the same
# module-level functions so both patterns share exactly one state dict.
# ---------------------------------------------------------------------------

class _SessionProxy:
    """Thin OO wrapper around the module-level session functions."""

    def reset(self) -> None:  # noqa: D401
        reset()

    def update(self, **kwargs) -> None:
        update(**kwargs)

    def snapshot(self) -> dict:
        return snapshot()


session = _SessionProxy()
