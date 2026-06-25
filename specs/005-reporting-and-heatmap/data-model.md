# Phase 1 Data Model: Phase 5 — Professional Reporting & Activity Insights

No new persisted entities are introduced (Constitution Principle I — Phase 5
is entirely derived, job-scoped output). This document describes the shape
of each derived artifact and the one change to an existing in-memory entity.

## Existing entity, extended: Event (in `session.py`'s `events` list)

| Field | Type | Notes |
|---|---|---|
| `event_index` | int | **Fixed in this phase for YOLO-produced events.** `detection_engine.py` always set this; `yolo_detector.py`'s `_emit_event` never did — a pre-existing gap, fixed here since thumbnails/report entries are addressed by this field. |
| `start_s` / `end_s` | float | Unchanged. |
| `start_clock` / `end_clock` | str \| None | Unchanged. |
| `peak_motion_score` | float | Unchanged — used as the report's "confidence score." |
| `zone_label` | str \| None | Unchanged — used as the report's "label" (falls back to "Motion" display text if `None`). |
| `included` | bool | Unchanged — the filter all three Phase 5 features respect (`included = [ev for ev in events if ev.get("included", True)]`, the same expression `export_job()` already uses). |

No new fields are added to the `Event` shape itself.

## New derived artifact: Activity Heatmap

| Property | Value |
|---|---|
| Storage location | `_job_dir(job_id) / "heatmap.png"` |
| Format | PNG, JET color map, normalized 0-255 |
| Resolution | Native source resolution (`source_info["width"]`/`["height"]`) — accumulated at a smaller working resolution internally, then upscaled before writing |
| Lifecycle | Written once at the end of a completed (or cancelled) detection `run()`; overwritten by the next detection run for the same job; never written if zero activity was detected (file simply doesn't exist in that case) |
| Produced by | `detection_engine.py` (from `fg_mask` accumulation) or `yolo_detector.py` (from filled-bounding-box accumulation) — same output format regardless of producer |
| Consumed by | `GET /api/job/heatmap` (ROI editor overlay, ad-hoc); inlined as base64 into the Incident Report |

**Validation rule**: A heatmap file existing is the sole signal of
availability — there is no separate "heatmap available" flag in `session.py`.
Absence of the file means either no detection has completed yet for this job,
or the completed run detected zero activity (FR-P5-011/FR-P5-012) — both
cases are handled identically by callers (treat as "not available," not an
error).

## New derived artifact: Incident Report

| Property | Value |
|---|---|
| Storage location | Rendered on-demand at `GET /api/job/report.html`; saved to disk only when converted to PDF by `shell/main_window.py`, into the user's `output_dir` as `incident_report_<timestamp>.pdf` |
| Composition | Summary (source name, generated-at timestamp, included/total event counts, total duration, resolution, codec) + optional heatmap image (base64-inlined) + thumbnail grid (one card per included event: base64-inlined thumbnail, label, time range, confidence) + chain-of-custody table (source filename + SHA-256; export filename + SHA-256, or "not yet exported" fallback — **filenames only, never full file-system paths**, per FR-P5-023, to avoid leaking local folder/username structure when the report is shared externally) |
| Source data | `session.snapshot()`'s `events` (filtered to `included`), `source_path`, `source_info`, `output_path` (if set); thumbnails generated lazily via `thumbnail_gen.run()`; heatmap read from the artifact above if present |
| Lifecycle | Regenerated fresh on every request — always reflects the *current* inclusion state, never a stale snapshot from an earlier visit to the Export page (Edge Case: re-generating after changing inclusions on Timeline must reflect the new set) |

**Validation rule**: If `included` is empty at request time, the report
endpoint MUST refuse (matches FR-P5-008) rather than render an empty
document — surfaced to the user as "nothing to report," not a blank PDF.

## New derived artifact: Event Log Export (CSV / JSON)

| Property | Value |
|---|---|
| Storage location | User's `output_dir`, filename `<source_stem>_events_<timestamp>.csv` or `.json` |
| Fields | `event_index, start_s, end_s, start_clock, end_clock, peak_motion_score, zone_label, included` — the `included` events only, optionally further narrowed by an explicit `label_filter` list (same semantics as the existing video export) |
| Lifecycle | One file written per request; a repeated request produces a new, distinctly timestamped file (FR-P5-018), never overwrites a prior export |

**Validation rule**: Same zero-included-events refusal as the Incident
Report (FR-P5-017) — a request with no matching events after filtering
returns an error, not an empty file.

## Relationships

```
Job (session.py, in-memory, unchanged)
 ├── events[]  (existing; event_index now always populated, both engines)
 ├── heatmap.png        (new, job_dir-scoped, 0 or 1 per job, latest-run-wins)
 ├── thumbnails/*.jpg    (existing code, now wired in; 1 per included event, lazy)
 ├── report.html (ephemeral, rendered per-request, never persisted as a file by the backend)
 │    └── incident_report_<ts>.pdf   (written only by the Qt shell, into output_dir)
 ├── <stem>_events_<ts>.csv   (written into output_dir, 1 per request)
 └── <stem>_events_<ts>.json  (written into output_dir, 1 per request)
```

None of these artifacts are referenced from `session.py`'s `_DEFAULTS` — they
are derived, on-disk-only side effects, consistent with Principle I.
