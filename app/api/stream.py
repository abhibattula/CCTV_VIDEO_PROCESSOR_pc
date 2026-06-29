"""
SSE stream endpoint — /api/stream

Subscribes to the log_buffer for the current job, fans out log lines with
progress/event_count/status metadata.

Phase 7: also emits report_stage and report_done events when the intel-report
export endpoint updates the session state.

Design note: report and keepalive events are emitted at the TOP of each poll
iteration so they appear before the wait, avoiding any "yield inside except"
edge-case on some Python/asyncio builds.
"""
import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

import app.session as session
from app.core.log_buffer import log_buffer

router = APIRouter()

POLL_INTERVAL_S = 0.5   # How often to poll when no log line is available
_MAX_IDLE_POLLS = 10    # Break after this many consecutive idle polls (5 s safety net)
                        # In production uvicorn terminates via CancelledError on disconnect;
                        # this ensures starlette TestClient calls also terminate cleanly.


async def _event_generator(job_id: str) -> AsyncGenerator[str, None]:
    q = log_buffer.subscribe(job_id)
    idle_polls = 0
    try:
        while True:
            # ── Snapshot session state ──────────────────────────────────────
            snap = session.snapshot()

            # Emit report_stage if actively generating
            report_stage = snap.get("report_stage", "")
            if report_stage:
                msg = json.dumps({
                    "type": "report_stage",
                    "stage": report_stage,
                    "current": snap.get("report_stage_current", 0),
                    "total": snap.get("report_stage_total", 0),
                    "ts": snap.get("report_stage_timestamp", ""),
                })
                yield f"data: {msg}\n\n"

            # Emit report_done once when pending, then clear the flag
            if snap.get("report_done_pending"):
                msg = json.dumps({
                    "type": "report_done",
                    "md_path": snap.get("md_path"),
                    "pdf_path": snap.get("pdf_path"),
                })
                yield f"data: {msg}\n\n"
                session.update(report_done_pending=False)

            # Always emit a keepalive heartbeat
            msg = json.dumps({
                "type": "keepalive",
                "progress": snap["progress"],
                "event_count": snap["event_count"],
                "status": snap["status"],
            })
            yield f"data: {msg}\n\n"

            # ── Wait for next log line or poll interval ─────────────────────
            try:
                line = await asyncio.wait_for(q.get(), timeout=POLL_INTERVAL_S)
                idle_polls = 0  # reset idle counter on any activity
            except asyncio.TimeoutError:
                idle_polls += 1
                if idle_polls >= _MAX_IDLE_POLLS:
                    # Safety-net: terminate so starlette TestClient can collect the
                    # buffered response.  In production uvicorn cancels via
                    # CancelledError on client disconnect long before this fires.
                    break
                # No new log line — loop back to re-check session state
                continue

            # Got a log line
            if line == "__DONE__":
                snap2 = session.snapshot()
                msg = json.dumps({
                    "type": "done",
                    "progress": snap2["progress"],
                    "event_count": snap2["event_count"],
                    "status": snap2["status"],
                })
                yield f"data: {msg}\n\n"
                break

            snap2 = session.snapshot()
            msg = json.dumps({
                "type": "log",
                "line": line,
                "progress": snap2["progress"],
                "event_count": snap2["event_count"],
                "status": snap2["status"],
            })
            yield f"data: {msg}\n\n"

    except asyncio.CancelledError:
        pass
    finally:
        log_buffer.unsubscribe(job_id, q)


@router.get("/stream")
async def sse_stream():
    snap = session.snapshot()
    job_id = snap.get("job_id") or "default"
    return StreamingResponse(
        _event_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
