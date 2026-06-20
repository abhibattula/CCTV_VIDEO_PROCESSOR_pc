"""
Job lifecycle router: create, start, cancel, events, toggle, export.
All state lives in app.session — single in-memory dict, one job at a time.
"""
import threading
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import app.session as session
from app.config import JOBS_DIR
from app.utils.ffprobe import probe
from app.core.log_buffer import log_buffer

router = APIRouter()

# Module-level cancel event reused per detection run
_cancel_event: threading.Event = threading.Event()


# ── Request bodies ────────────────────────────────────────────────────────────

class CreateJobRequest(BaseModel):
    source_path: str


class StartJobRequest(BaseModel):
    mode: str = "mog2"
    sensitivity: str = "medium"
    frame_skip: int = 1
    padding_s: float = 2.0
    min_gap_s: float = 2.0
    min_event_s: float = 2.0
    zones: list = []
    recording_start: Optional[str] = None


class BulkToggleRequest(BaseModel):
    indices: list[int]
    include: bool


class ExportRequest(BaseModel):
    output_type: str = "merged"
    quality: str = "original"
    output_dir: Optional[str] = None
    burn_in: bool = False
    label_filter: list[str] = []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _job_dir(job_id: str) -> Path:
    d = JOBS_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _make_log_fn(job_id: str):
    def _log(msg: str) -> None:
        log_buffer.append(job_id, msg)
    return _log


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/job/create")
async def create_job(req: CreateJobRequest):
    path = Path(req.source_path)
    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"File not found: {req.source_path}")

    try:
        source_info = probe(str(path))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Cannot probe video: {exc}")

    job_id = str(uuid.uuid4())
    session.reset()
    session.update(
        job_id=job_id,
        status="ready",
        source_path=str(path),
        source_info=source_info,
        progress=0.0,
    )

    warnings = []
    if source_info.get("needs_reencode"):
        codec = source_info.get("codec", "unknown")
        warnings.append(f"Codec '{codec}' requires re-encoding — export will be slower.")

    return JSONResponse({
        "job_id": job_id,
        "status": "ready",
        "source_info": source_info,
        "warnings": warnings,
    })


@router.get("/job")
async def get_job():
    return JSONResponse(session.snapshot())


@router.post("/job/start")
async def start_job(req: StartJobRequest):
    snap = session.snapshot()
    if snap["status"] not in ("ready", "completed", "cancelled", "error"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start detection from status '{snap['status']}'"
        )

    job_id     = snap["job_id"]
    source_path = snap["source_path"]
    source_info = snap["source_info"]

    settings = req.model_dump()

    _cancel_event.clear()
    session.update(status="detecting", progress=0.0)
    # Clear events for a fresh run
    session.update(events=[], event_count=0)

    log = _make_log_fn(job_id)
    log_buffer.reset(job_id)

    def _run():
        try:
            if req.mode == "yolo":
                try:
                    from app.core import yolo_detector as detector
                except ImportError as exc:
                    raise HTTPException(
                        status_code=400,
                        detail="ultralytics not installed — pip install ultralytics"
                    ) from exc
            else:
                from app.core import detection_engine as detector

            detector.run(
                source_path=source_path,
                source_info=source_info,
                settings=settings,
                cancel_event=_cancel_event,
                on_progress=lambda p: session.update(progress=p),
                on_event=session.append_event,
                job_dir=_job_dir(job_id),
            )

            if _cancel_event.is_set():
                session.update(status="cancelled")
                log("[CANCEL] Detection cancelled.")
            else:
                session.update(status="completed", progress=1.0)
                snap2 = session.snapshot()
                log(f"[DONE] Detection complete — {snap2['event_count']} event(s) found.")
        except Exception as exc:
            session.update(status="error", error_msg=str(exc))
            log(f"[ERROR] Detection failed: {exc}")

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"status": "detecting"})


@router.post("/job/cancel")
async def cancel_job():
    _cancel_event.set()
    session.update(status="cancelled")
    return JSONResponse({"status": "cancelled"})


@router.get("/job/events")
async def get_events():
    snap = session.snapshot()
    return JSONResponse(snap["events"])


@router.put("/job/events/bulk")
async def bulk_toggle_events(req: BulkToggleRequest):
    if not req.indices:
        raise HTTPException(status_code=400, detail="indices must be non-empty")
    snap = session.snapshot()
    total = len(snap.get("events", []))
    for idx in req.indices:
        if idx < 0 or idx >= total:
            raise HTTPException(status_code=404, detail=f"Event index {idx} not found")
    try:
        session.bulk_toggle_events(req.indices, req.include)
    except (IndexError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    snap2 = session.snapshot()
    return JSONResponse({"updated": len(req.indices), "events": snap2["events"]})


@router.put("/job/events/{idx}/toggle")
async def toggle_event(idx: int):
    try:
        session.toggle_event(idx)
    except (IndexError, KeyError):
        raise HTTPException(status_code=404, detail=f"Event index {idx} not found")
    snap = session.snapshot()
    events = snap["events"]
    if idx >= len(events):
        raise HTTPException(status_code=404, detail=f"Event index {idx} not found")
    return JSONResponse(events[idx])


@router.post("/job/export")
async def export_job(req: ExportRequest):
    snap = session.snapshot()
    if snap["status"] not in ("completed", "cancelled", "exporting"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot export from status '{snap['status']}' — run detection first."
        )

    included = [ev for ev in snap["events"] if ev.get("included", True)]
    if not included:
        raise HTTPException(status_code=400, detail="No events are included — toggle at least one on.")

    job_id      = snap["job_id"]
    source_info = snap["source_info"] or {}
    settings    = snap["settings"] or {}
    settings["source_path"] = snap["source_path"]
    settings["output_quality"] = req.quality
    settings["output_type"]    = req.output_type

    # Resolve output directory: explicit request > session stored dir > Desktop
    output_dir = req.output_dir or snap.get("output_dir")
    if not output_dir:
        import os
        output_dir = str(Path.home() / "Desktop")
    output_dir = Path(output_dir)

    session.update(status="exporting", progress=0.0)
    log = _make_log_fn(job_id)

    def _run():
        try:
            from app.core.export_engine import run as export_run
            output_path, output_name, output_size = export_run(
                events=snap["events"],
                source_info=source_info,
                settings=settings,
                output_dir=output_dir,
                on_progress=lambda p: session.update(progress=p),
                job_dir=_job_dir(job_id),
                logger=log,
                burn_in=req.burn_in,
                label_filter=req.label_filter if req.label_filter else None,
            )
            session.update(
                status="export_done",
                output_path=str(output_path),
                progress=1.0,
            )
            log(f"[EXPORT] Saved to: {output_path}")
        except Exception as exc:
            session.update(status="export_error", error_msg=str(exc))
            log(f"[EXPORT ERROR] {exc}")

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"status": "exporting"})
