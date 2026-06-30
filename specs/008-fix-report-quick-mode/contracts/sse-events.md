# Contract: SSE Progress Events (job.py → stream.py → export.js)

**Date**: 2026-06-29

## Overview

When the user clicks "Generate Intelligence Report", `export.js` opens an EventSource on `/api/stream` and concurrently POSTs to `/api/job/intel-report/export`. The export endpoint writes progress into session state; `stream.py` polls that state and pushes SSE events to the browser.

## Sequence

```
export.js                stream.py (/api/stream)   job.py (/intel-report/export)
   |                            |                            |
   |--- EventSource open ------>|                            |
   |--- POST /intel-report/export --------------------------->|
   |                            |<-- session.update(stage=thumbnails, curr=0, total=N)
   |<-- report_stage event -----|                            |
   |                            |  ... thumbnail_gen.run()  |
   |                            |<-- session.update(stage=thumbnails, curr=N, total=N)
   |<-- report_stage (100%) ----|                            |
   |                            |<-- session.update(stage=ai_analysis, curr=0, total=N)
   |<-- report_stage event -----|                            |
   |                            |  ... FrameAnalyzer loop   |
   |<-- report_stage (1/N)------|<-- session.update(curr=1) |
   |<-- report_stage (2/N)------|<-- session.update(curr=2) |
   |                            |<-- session.update(stage=markdown, ...)
   |<-- report_stage event -----|                            |
   |                            |<-- session.update(report_done_pending=True)
   |<-- report_done event -------|                           |
   |--- close EventSource        (report_done clears pending)|
```

## Phase 8 Change: SSE Disconnect Handling

`stream.py`'s generator MUST handle client disconnect without crashing:

```python
# Before (crashes on disconnect):
yield f"data: {json.dumps(payload)}\n\n"

# After (graceful):
try:
    yield f"data: {json.dumps(payload)}\n\n"
except asyncio.CancelledError:
    raise  # propagate graceful shutdown
except Exception:
    return  # client disconnected; stop generator silently
```

## Consumer Contract (export.js)

`export.js` expects these SSE event types (unchanged by Phase 8):

| Event type | Required fields | Action |
|---|---|---|
| `report_stage` | `stage`, `current`, `total` | Update progress bar for matching stage row |
| `report_stage` with `timestamp` | + `timestamp` | Show timestamp in ai_analysis row |
| `report_done` | `md_path`, `pdf_path` | Show success card, close EventSource |
| `error` (any) | `message` | Show error card |
