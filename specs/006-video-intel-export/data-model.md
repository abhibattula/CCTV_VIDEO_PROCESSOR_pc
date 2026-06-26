# Data Model: Video Intelligence Export (Phase 6)

**Date**: 2026-06-25 | **Branch**: `006-video-intel-export`

---

## Existing Entities (unchanged, referenced by this feature)

### Event (from detection engines)

Each event dict already in `session["events"]`:

| Field | Type | Notes |
|-------|------|-------|
| `event_index` | `int` | 0-based sequential index |
| `start_s` | `float` | Event start, seconds from video start |
| `end_s` | `float` | Event end, seconds from video start |
| `start_clock` | `str` | Wall-clock HH:MM:SS if recording_start set, else elapsed MM:SS |
| `end_clock` | `str` | Same format as start_clock |
| `peak_motion_score` | `float` | 0.0–1.0 confidence/motion score |
| `zone_label` | `str \| None` | YOLO: object class; MOG2: zone name or None |
| `included` | `bool` | Whether user has toggled this event on (default True) |

---

## New Data Structures (Phase 6)

### EventDescribed

An event dict augmented with a visual description — used internally when building
the template context. Never persisted to session.

| Field | Type | Notes |
|-------|------|-------|
| *(all Event fields)* | | Inherited unchanged |
| `description` | `str` | Moondream2 output, or `""` if unavailable |
| `thumb_b64` | `str` | Base64-encoded JPEG thumbnail for HTML/PDF embedding |

---

### ActivityStats (returned by `narrative_synthesizer.activity_stats()`)

| Field | Type | Notes |
|-------|------|-------|
| `event_count` | `int` | Total included events |
| `active_s` | `float` | Sum of all event durations (seconds) |
| `active_pct` | `float` | `active_s / source_info["duration_s"] * 100`, clamped 0–100 |
| `busiest_period` | `str` | Clock-formatted time range of the densest 60-second window |
| `avg_confidence` | `float` | Mean of `peak_motion_score` across included events |
| `detection_mode` | `str` | `"yolo"` or `"mog2"` |

---

### ObjectInventoryItem (one per YOLO class detected; empty list for MOG2)

Returned by `narrative_synthesizer.object_inventory(events)`.

| Field | Type | Notes |
|-------|------|-------|
| `label` | `str` | YOLO class name (e.g. `"person"`, `"car"`) |
| `count` | `int` | Number of included events with this zone_label |
| `first_clock` | `str` | Clock time of earliest event in this class |
| `last_clock` | `str` | Clock time of latest event in this class |

---

### TimelineEntry (one per included event; merged by `narrative_synthesizer.timeline_entries()`)

| Field | Type | Notes |
|-------|------|-------|
| `event_num` | `int` | 1-based display number (`event_index + 1`) |
| `start_clock` | `str` | From event |
| `start_s` | `float` | From event |
| `end_clock` | `str` | From event |
| `duration_s` | `float` | `end_s - start_s` |
| `label` | `str` | `zone_label or "motion"` |
| `confidence_pct` | `int` | `round(peak_motion_score * 100)` |
| `description` | `str` | From descriptions dict; `"N/A"` if empty |

---

### IntelReportContext (passed to `intel_report_renderer.render()`)

The full context dict for the Jinja2 template.

| Field | Type | Notes |
|-------|------|-------|
| `source_name` | `str` | Video filename |
| `generated_at` | `str` | ISO datetime string |
| `detection_mode` | `str` | `"YOLO"` or `"MOG2"` |
| `duration_fmt` | `str` | Video duration as MM:SS |
| `executive_summary` | `str` | From narrative_synthesizer |
| `stats` | `ActivityStats` | From narrative_synthesizer |
| `object_inventory` | `list[ObjectInventoryItem]` | Empty for MOG2 |
| `timeline` | `list[TimelineEntry]` | Chronological, all included events |
| `key_moments` | `list[EventDescribed]` | Top 3 by `peak_motion_score` descending |
| `heatmap_b64` | `str \| None` | Base64 PNG or None if no heatmap exists |
| `settings` | `dict` | Detection settings snapshot |
| `events_json` | `str` | JSON-serialised list of JSON appendix records |
| `moondream_available` | `bool` | Whether frame_describer.is_available() is True |

---

### JSON Appendix Record (embedded in Markdown + returned in POST response)

One object per included event in the ````json` appendix block.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `event_index` | `int` | Yes | 0-based; matches timeline table row |
| `start_s` | `float` | Yes | Seconds from video start |
| `end_s` | `float` | Yes | Seconds from video start |
| `start_clock` | `str` | Yes | Wall-clock or elapsed format |
| `end_clock` | `str` | Yes | Wall-clock or elapsed format |
| `peak_motion_score` | `float` | Yes | 0.0–1.0 |
| `zone_label` | `str \| null` | Yes | YOLO class or null |
| `included` | `bool` | Yes | Always `true` (excluded events never appear) |
| `description` | `str` | No | Omitted if empty (`""`) |

---

## State Transitions

No new session state. Intelligence report generation is stateless — it reads a
`session.snapshot()` and writes files. The only transient state is:

- `FrameDescriber._model`: class-level singleton loaded once per process, held in
  memory until app exit. Not serialisable, not in session.

## Validation Rules

- `active_pct` is clamped to [0, 100] — floating-point rounding cannot exceed 100%.
- `key_moments` contains at most 3 entries; if fewer than 3 included events exist, contains all of them.
- `events_json` MUST parse successfully with `json.loads()` — no trailing commas, all strings UTF-8.
- Markdown output file MUST be written with `encoding="utf-8"`.
- Description strings in the JSON appendix are omitted entirely (not null) when empty — keeps the appendix clean for LLM consumption.
