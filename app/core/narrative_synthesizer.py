"""
Phase 6 — Video Intelligence Export
Pure-function module for synthesizing narrative text and statistics
from a list of detected events.

No external imports — stdlib only.
"""


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def seconds_to_clock(s: float) -> str:
    """Convert a seconds value to MM:SS or HH:MM:SS clock string."""
    s = int(s)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def executive_summary(events: list[dict], source_info: dict, settings: dict) -> str:
    """
    Return a 2-3 sentence paragraph describing the detection run.

    - Empty events  → safe fallback string.
    - YOLO (any event has non-None zone_label) → names dominant class; the
      zone_label string appears verbatim (lowercased) in the output.
    - MOG2 (all zone_label=None) → describes motion activity; the word
      "motion" appears in the output.
    """
    if not events:
        return "No activity was detected during this recording."

    is_yolo = any(ev.get("zone_label") is not None for ev in events)
    duration_s = source_info.get("duration_s", 0)
    duration_min = duration_s / 60

    if duration_min >= 1:
        duration_str = f"{int(round(duration_min))}-minute"
    else:
        duration_str = f"{int(duration_s)}-second"

    total_events = len(events)
    peak_event = max(events, key=lambda ev: ev.get("peak_motion_score", 0.0))
    peak_clock = peak_event.get(
        "start_clock",
        seconds_to_clock(peak_event.get("start_s", 0)),
    )

    if is_yolo:
        # Tally zone_labels
        label_counts: dict[str, int] = {}
        for ev in events:
            label = ev.get("zone_label")
            if label is not None:
                label_counts[label] = label_counts.get(label, 0) + 1

        dominant_label = max(label_counts, key=lambda k: label_counts[k])
        dominant_count = label_counts[dominant_label]

        return (
            f"During the {duration_str} video, {total_events} events were detected. "
            f"{dominant_label.capitalize()} was the most common activity "
            f"({dominant_count} events). "
            f"Activity peaked at {peak_clock}."
        )
    else:
        return (
            f"During the {duration_str} video, {total_events} motion events were detected. "
            f"Motion activity was recorded throughout the clip. "
            f"Motion peaked at {peak_clock}."
        )


def activity_stats(events: list[dict], source_info: dict) -> dict:
    """
    Return an ActivityStats dict with aggregated metrics.

    Keys: event_count, active_s, active_pct, busiest_period,
          avg_confidence, detection_mode.

    active_pct is clamped to [0.0, 100.0].
    avg_confidence is 0.0 when events is empty (no division by zero).
    busiest_period uses a 60-second sliding window over event start times.
    """
    if not events:
        return {
            "event_count": 0,
            "active_s": 0.0,
            "active_pct": 0.0,
            "busiest_period": "N/A",
            "avg_confidence": 0.0,
            "detection_mode": "mog2",
        }

    duration_s = source_info.get("duration_s", 1.0)
    event_count = len(events)

    active_s = sum(ev["end_s"] - ev["start_s"] for ev in events)
    active_pct = min(100.0, max(0.0, active_s / duration_s * 100))

    avg_confidence = (
        sum(ev.get("peak_motion_score", 0.0) for ev in events) / event_count
    )

    detection_mode = (
        "yolo" if any(ev.get("zone_label") is not None for ev in events) else "mog2"
    )

    # 60-second sliding window to find busiest period
    best_count = 0
    best_start_s = events[0]["start_s"]
    for ev in events:
        window_start_s = ev["start_s"]
        count = sum(
            1 for e in events
            if window_start_s <= e["start_s"] < window_start_s + 60
        )
        if count > best_count:
            best_count = count
            best_start_s = window_start_s

    busiest_period = (
        f"{seconds_to_clock(best_start_s)}–{seconds_to_clock(best_start_s + 60)}"
    )

    return {
        "event_count": event_count,
        "active_s": active_s,
        "active_pct": active_pct,
        "busiest_period": busiest_period,
        "avg_confidence": avg_confidence,
        "detection_mode": detection_mode,
    }


def object_inventory(events: list[dict]) -> list[dict]:
    """
    For YOLO runs: group events by zone_label, sorted by count descending.
    Each entry: {"label", "count", "first_clock", "last_clock"}.

    For MOG2 (all zone_label=None): returns [].
    """
    is_yolo = any(ev.get("zone_label") is not None for ev in events)
    if not is_yolo:
        return []

    groups: dict[str, list[dict]] = {}
    for ev in events:
        label = ev.get("zone_label")
        if label is not None:
            groups.setdefault(label, []).append(ev)

    result: list[dict] = []
    for label, evs in groups.items():
        sorted_evs = sorted(evs, key=lambda e: e["start_s"])
        first_ev = sorted_evs[0]
        last_ev = sorted_evs[-1]
        first_clock = first_ev.get(
            "start_clock", seconds_to_clock(first_ev["start_s"])
        )
        last_clock = last_ev.get(
            "end_clock", seconds_to_clock(last_ev["end_s"])
        )
        result.append(
            {
                "label": label,
                "count": len(evs),
                "first_clock": first_clock,
                "last_clock": last_clock,
            }
        )

    # Sort by count desc, then label alphabetically for determinism
    result.sort(key=lambda x: (-x["count"], x["label"]))
    return result


def timeline_entries(events: list[dict], descriptions: dict) -> list[dict]:
    """
    Build one timeline entry dict per event.

    IMPORTANT: description is ALWAYS truncated to 200 chars, unconditionally.
    """
    entries: list[dict] = []
    for ev in events:
        event_index = ev.get("event_index", 0)
        raw_desc = descriptions.get(event_index, "") or "N/A"
        description = raw_desc[:200]  # unconditional truncation

        entries.append(
            {
                "event_num": event_index + 1,
                "start_clock": ev.get(
                    "start_clock", seconds_to_clock(ev.get("start_s", 0))
                ),
                "start_s": ev.get("start_s", 0.0),
                "end_clock": ev.get(
                    "end_clock", seconds_to_clock(ev.get("end_s", 0))
                ),
                "duration_s": ev.get("end_s", 0.0) - ev.get("start_s", 0.0),
                "label": ev.get("zone_label") or "motion",
                "confidence_pct": round(ev.get("peak_motion_score", 0.0) * 100),
                "description": description,
            }
        )

    return entries


# ---------------------------------------------------------------------------
# NarrativeSynthesizer class — thin OO wrapper used by LLMSynthesizer
# Extended by T006 with temporal_analysis() and trend_direction()
# ---------------------------------------------------------------------------

class NarrativeSynthesizer:
    """OO wrapper around module-level narrative functions.

    Provides an instance interface expected by LLMSynthesizer.synthesize().
    T006 will add temporal_analysis() and trend_direction() as class methods
    and enrich executive_summary() to incorporate them.
    """

    def executive_summary(self, events: list) -> str:
        """Return a rule-based executive summary string.

        Delegates to the module-level executive_summary() function with
        default source_info so callers only need to pass the events list.
        """
        # NOTE: bare name 'executive_summary' resolves to the module-level
        # function above (not self.executive_summary) — no recursion.
        return executive_summary(events, source_info={}, settings={})
