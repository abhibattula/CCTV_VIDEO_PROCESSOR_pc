"""
Job lifecycle router: create, start, cancel, events, toggle, export.
All state lives in app.session — single in-memory dict, one job at a time.
"""
import base64
import hashlib
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

import app.session as session
from app.config import JOBS_DIR
from app.utils.ffprobe import probe
from app.utils.time_utils import seconds_to_clock
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


class EventLogExportRequest(BaseModel):
    output_dir: Optional[str] = None
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


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def _b64_file(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _filtered_included_events(snap: dict, label_filter: list[str]) -> list[dict]:
    included = [ev for ev in snap["events"] if ev.get("included", True)]
    if label_filter:
        included = [ev for ev in included if ev.get("zone_label", "") in label_filter]
    return included


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
    _cancel_event.set()
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


@router.get("/job/preview-frame")
async def preview_frame():
    snap = session.snapshot()
    source_path = snap.get("source_path")
    job_id = snap.get("job_id")
    if not source_path or not job_id:
        return JSONResponse({"error": "No active job"}, status_code=400)

    out_path = _job_dir(job_id) / "preview_frame.jpg"
    if out_path.exists():
        return FileResponse(str(out_path), media_type="image/jpeg")

    duration_s = (snap.get("source_info") or {}).get("duration_s", 0) or 0
    ts = min(1.0, duration_s * 0.1) if duration_s else 0.0

    from app.utils.ffmpeg_path import get_ffmpeg
    cmd = [
        get_ffmpeg(), "-hide_banner", "-loglevel", "error",
        "-ss", str(ts), "-i", source_path, "-frames:v", "1",
        "-q:v", "5", "-y", str(out_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=15)
        if result.returncode != 0 or not out_path.exists():
            return JSONResponse({"error": "Could not extract preview frame"}, status_code=500)
    except Exception as exc:
        return JSONResponse({"error": f"Preview extraction failed: {exc}"}, status_code=500)
    return FileResponse(str(out_path), media_type="image/jpeg")


@router.get("/job/heatmap")
async def heatmap():
    snap = session.snapshot()
    job_id = snap.get("job_id")
    if not job_id:
        return JSONResponse({"error": "No active job"}, status_code=400)

    out_path = _job_dir(job_id) / "heatmap.png"
    if not out_path.exists():
        return JSONResponse({"error": "Heatmap not available yet"}, status_code=404)
    return FileResponse(str(out_path), media_type="image/png")


@router.get("/job/report.html")
async def report_html():
    snap = session.snapshot()
    job_id = snap.get("job_id")
    source_path = snap.get("source_path")
    if not job_id or not source_path:
        return JSONResponse({"error": "No active job"}, status_code=400)

    if snap.get("status") == "detecting":
        return JSONResponse({"error": "Detection is still in progress for this job"}, status_code=400)

    included = [ev for ev in snap["events"] if ev.get("included", True)]
    if not included:
        return JSONResponse({"error": "There is nothing to report — no events are currently included"}, status_code=400)

    job_dir = _job_dir(job_id)

    try:
        from app.core import thumbnail_gen
        thumbnail_gen.run(job_id=job_id, source_path=source_path, events=included, logger=_make_log_fn(job_id))

        for ev in included:
            ev["thumb_b64"] = _b64_file(job_dir / "thumbnails" / f"{ev['event_index']}.jpg")

        heatmap_b64 = _b64_file(job_dir / "heatmap.png")

        output_path = snap.get("output_path")
        source_hash = _sha256_file(Path(source_path)) if Path(source_path).exists() else None
        output_hash = _sha256_file(Path(output_path)) if output_path and Path(output_path).exists() else None
    except OSError as exc:
        return JSONResponse({"error": f"Could not access a required file: {exc}"}, status_code=400)

    source_info = snap.get("source_info") or {}
    total_dur = sum(ev["end_s"] - ev["start_s"] for ev in included)

    from app.core.report_renderer import render as render_report
    html = render_report({
        "source_name": Path(source_path).name,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "included_count": len(included),
        "total_count": len(snap["events"]),
        "total_duration_fmt": seconds_to_clock(total_dur),
        "resolution": f"{source_info.get('width', '?')}×{source_info.get('height', '?')}",
        "codec": source_info.get("codec", "?"),
        "events": included,
        "heatmap_b64": heatmap_b64,
        "source_filename": Path(source_path).name,
        "source_hash": source_hash,
        "output_filename": Path(output_path).name if output_path else None,
        "output_hash": output_hash,
    })
    return HTMLResponse(html)


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


@router.post("/job/export/csv")
async def export_events_csv(req: EventLogExportRequest):
    snap = session.snapshot()
    if not snap.get("job_id") or not snap.get("source_path"):
        return JSONResponse({"error": "No active job"}, status_code=400)
    if snap.get("status") == "detecting":
        raise HTTPException(status_code=400, detail="Detection is still in progress for this job")

    included = _filtered_included_events(snap, req.label_filter)
    if not included:
        raise HTTPException(status_code=400, detail="No events match the current filter.")

    try:
        output_dir = Path(req.output_dir or snap.get("output_dir") or (Path.home() / "Desktop"))
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Could not access output folder: {exc}")

    source_name = Path(snap["source_path"]).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"{source_name}_events_{timestamp}.csv"

    import csv
    fieldnames = ["event_index", "start_s", "end_s", "start_clock", "end_clock",
                  "peak_motion_score", "zone_label", "included"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(included)

    return JSONResponse({"output_path": str(out_path)})


@router.post("/job/export/json")
async def export_events_json(req: EventLogExportRequest):
    snap = session.snapshot()
    if not snap.get("job_id") or not snap.get("source_path"):
        return JSONResponse({"error": "No active job"}, status_code=400)
    if snap.get("status") == "detecting":
        raise HTTPException(status_code=400, detail="Detection is still in progress for this job")

    included = _filtered_included_events(snap, req.label_filter)
    if not included:
        raise HTTPException(status_code=400, detail="No events match the current filter.")

    try:
        output_dir = Path(req.output_dir or snap.get("output_dir") or (Path.home() / "Desktop"))
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Could not access output folder: {exc}")

    source_name = Path(snap["source_path"]).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"{source_name}_events_{timestamp}.json"

    import json
    out_path.write_text(json.dumps(included, indent=2), encoding="utf-8")

    return JSONResponse({"output_path": str(out_path)})
