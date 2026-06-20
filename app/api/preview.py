"""
Preview clip endpoint — extract a short clip per event for in-browser playback.
generate_preview() is CPU/IO-bound so it runs in an executor thread, keeping
the asyncio event loop free for other requests during FFmpeg encoding.
"""
import asyncio
import re
import secrets
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

import app.session as session
from app.config import PREVIEW_DIR
from app.core.export_engine import generate_preview

router = APIRouter()

_TOKEN_RE = re.compile(r"^[0-9a-f]{16}$")


@router.post("/job/preview/{idx}")
async def create_preview(idx: int):
    snap = session.snapshot()
    events = snap.get("events", [])
    if idx < 0 or idx >= len(events):
        raise HTTPException(status_code=404, detail=f"Event index {idx} not found")

    ev          = events[idx]
    source_path = snap.get("source_path", "")
    if not source_path:
        raise HTTPException(status_code=400, detail="No source video loaded")

    token = secrets.token_hex(8)  # 16 hex chars

    # Run FFmpeg in a thread so the event loop stays responsive
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(
            None,
            lambda: generate_preview(
                source_path=source_path,
                start_s=float(ev["start_s"]),
                end_s=float(ev["end_s"]),
                token=token,
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Preview extraction failed: {exc}")

    return JSONResponse({"url": f"/api/preview/{token}.mp4", "token": token})


@router.get("/preview/{token}.mp4")
async def serve_preview(token: str):
    if not _TOKEN_RE.match(token):
        raise HTTPException(status_code=400, detail="Invalid token format")

    clip = PREVIEW_DIR / f"{token}.mp4"
    if not clip.exists():
        raise HTTPException(status_code=404, detail="Preview clip not found or expired")

    return FileResponse(
        str(clip),
        media_type="video/mp4",
        headers={"Accept-Ranges": "bytes", "Cache-Control": "no-store"},
    )
