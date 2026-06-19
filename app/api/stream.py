"""
SSE stream endpoint — /api/stream

Subscribes to the log_buffer for the current job, fans out log lines with
progress/event_count/status metadata. Sends keepalive every 30s.
Unsubscribes on client disconnect.
"""
import asyncio
import json
import time
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

import app.session as session
from app.core.log_buffer import log_buffer

router = APIRouter()

KEEPALIVE_INTERVAL_S = 30


async def _event_generator(job_id: str) -> AsyncGenerator[str, None]:
    q = log_buffer.subscribe(job_id)
    last_keepalive = time.monotonic()

    try:
        while True:
            # Check for new log lines with a short timeout so keepalive fires on time
            try:
                line = await asyncio.wait_for(q.get(), timeout=5.0)
            except asyncio.TimeoutError:
                # No new log line — check keepalive interval
                if time.monotonic() - last_keepalive >= KEEPALIVE_INTERVAL_S:
                    snap = session.snapshot()
                    msg = json.dumps({
                        "type": "keepalive",
                        "progress": snap["progress"],
                        "event_count": snap["event_count"],
                        "status": snap["status"],
                    })
                    yield f"data: {msg}\n\n"
                    last_keepalive = time.monotonic()
                continue

            if line == "__DONE__":
                snap = session.snapshot()
                msg = json.dumps({
                    "type": "done",
                    "progress": snap["progress"],
                    "event_count": snap["event_count"],
                    "status": snap["status"],
                })
                yield f"data: {msg}\n\n"
                break

            snap = session.snapshot()
            msg = json.dumps({
                "type": "log",
                "line": line,
                "progress": snap["progress"],
                "event_count": snap["event_count"],
                "status": snap["status"],
            })
            yield f"data: {msg}\n\n"
            last_keepalive = time.monotonic()

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
