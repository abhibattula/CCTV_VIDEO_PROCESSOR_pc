# Data Model: Phase 8 — Report Fix + Quick Mode UI

**Date**: 2026-06-29

This feature modifies no data entities. The only relevant data shapes are the SSE event fields that `job.py` writes and `stream.py` / `export.js` read. These are documented here as a reference for test writers and implementers.

---

## Session State Fields (report-related)

These fields live in `app/session.py`'s in-memory dict and are accessed via `session.update()` / `session.snapshot()`.

| Field | Type | Values | Set by |
|---|---|---|---|
| `report_stage` | `str` | `"thumbnails"`, `"ai_analysis"`, `"markdown"`, `"pdf"`, `""` | `job.py` intel-report export endpoint |
| `report_stage_current` | `int` | 0..N (current item index) | `job.py` intel-report export endpoint |
| `report_stage_total` | `int` | N (total items in stage) | `job.py` intel-report export endpoint |
| `report_done_pending` | `bool` | True when generation complete, False otherwise | `job.py` intel-report export endpoint |
| `report_done_md_path` | `str \| None` | Absolute path to .md file, or None | `job.py` |
| `report_done_pdf_path` | `str \| None` | Absolute path to .pdf file, or None | `job.py` |

**Phase 8 change**: `report_stage_current` for the `"thumbnails"` stage is now set AFTER `thumbnail_gen.run()` completes, not before.

---

## SSE Event Shapes

Events emitted by `stream.py` to the browser's EventSource on `/api/stream`.

### `report_stage` event

```json
{
  "type": "report_stage",
  "stage": "thumbnails" | "ai_analysis" | "markdown" | "pdf",
  "current": 0,
  "total": 12,
  "timestamp": "00:01:23"
}
```

`timestamp` is only present for `"ai_analysis"` stage (shows current event's clock time).

### `report_done` event

```json
{
  "type": "report_done",
  "md_path": "/absolute/path/to/report.md" | null,
  "pdf_path": "/absolute/path/to/report.pdf" | null
}
```

---

## FrameAnalyzer Constants (modified in Phase 8)

| Constant | Old Value | New Value | Location |
|---|---|---|---|
| `_TASK_TIMEOUT` | 300 | 90 | `app/core/frame_analyzer.py` |
| `max_new_tokens` | 128 | 64 | `app/core/frame_analyzer.py` (3 call sites) |
