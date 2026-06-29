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

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

import app.session as session
from app.config import JOBS_DIR
from app.utils.ffprobe import probe
from app.utils.time_utils import seconds_to_clock
from app.core.log_buffer import log_buffer
from app.core import thumbnail_gen
from app.core.frame_analyzer import FrameAnalyzer
from app.core.llm_synthesizer import LLMSynthesizer

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


@router.get("/job/intel-report.html")
async def intel_report_html():
    snap = session.snapshot()
    job_id = snap.get("job_id")
    source_path = snap.get("source_path")

    # Guard 1: no active job
    if not job_id or not source_path:
        return JSONResponse({"error": "No active job"}, status_code=400)

    # Guard 2: detection in progress
    if snap.get("status") == "detecting":
        return JSONResponse({"error": "Detection is still in progress"}, status_code=400)

    # Guard 3: no included events
    included = [ev for ev in snap["events"] if ev.get("included", True)]
    if not included:
        return JSONResponse({"error": "No events to report — no events are currently included"}, status_code=400)

    job_dir = _job_dir(job_id)

    try:
        from app.core import thumbnail_gen
        thumbnail_gen.run(job_id=job_id, source_path=source_path, events=included, logger=_make_log_fn(job_id))

        for ev in included:
            ev["thumb_b64"] = _b64_file(job_dir / "thumbnails" / f"{ev['event_index']}.jpg") or ""

        heatmap_b64 = _b64_file(job_dir / "heatmap.png") or ""
    except OSError as exc:
        return JSONResponse({"error": f"Could not access a required file: {exc}"}, status_code=400)

    source_info = snap.get("source_info") or {}
    settings = snap.get("settings") or {}
    duration_s = float(source_info.get("duration_s", 0) or 0)

    # Normalise event fields for new-style renderer methods (label / confidence / thumbnail_path)
    for ev in included:
        if "label" not in ev:
            ev["label"] = ev.get("zone_label") or "mog2"
        if "confidence" not in ev:
            ev["confidence"] = float(ev.get("peak_motion_score", 0.5))
        if "thumbnail_path" not in ev:
            tp = job_dir / "thumbnails" / f"{ev['event_index']}.jpg"
            ev["thumbnail_path"] = str(tp) if tp.exists() else None

    from app.core.frame_describer import FrameDescriber
    descriptions = {}
    for ev in included:
        thumb = job_dir / "thumbnails" / f"{ev['event_index']}.jpg"
        descriptions[ev["event_index"]] = FrameDescriber.describe(thumb) if thumb.exists() else ""

    from app.core.narrative_synthesizer import (
        NarrativeSynthesizer, executive_summary, activity_stats, object_inventory, timeline_entries
    )

    # Executive summary — use LLMSynthesizer when available, else rule-based
    llm_notice = ""
    if LLMSynthesizer.is_available():
        try:
            narrative_obj = NarrativeSynthesizer()
            exec_summary_text, _llm_used, llm_notice = LLMSynthesizer().synthesize(
                included, duration_s, narrative_obj
            )
            summary = exec_summary_text
        except Exception:
            summary = executive_summary(included, source_info, settings)
            llm_notice = "Executive summary: rule-based synthesis — LLM API unavailable"
    else:
        summary = executive_summary(included, source_info, settings)
        llm_notice = "Executive summary: rule-based synthesis — LLM API unavailable"

    stats = activity_stats(included, source_info)
    inventory = object_inventory(included)
    timeline = timeline_entries(included, descriptions)

    # Key moments: top 3 by peak_motion_score desc, tiebreak by event_index asc
    key_moments_raw = sorted(
        included,
        key=lambda ev: (-ev.get("peak_motion_score", 0), ev.get("event_index", 0))
    )[:3]
    key_moments = []
    for km in key_moments_raw:
        idx = km.get("event_index", 0)
        key_moments.append({
            "event_num": idx + 1,
            "start_clock": km.get("start_clock") or seconds_to_clock(km.get("start_s", 0)),
            "end_clock": km.get("end_clock") or seconds_to_clock(km.get("end_s", 0)),
            "label": km.get("zone_label") or "motion",
            "confidence_pct": round(km.get("peak_motion_score", 0) * 100),
            "thumb_b64": km.get("thumb_b64") or "",
            "description": descriptions.get(idx, ""),
        })

    # Duration format
    duration_fmt = seconds_to_clock(duration_s)

    # Build events JSON for Data Appendix
    import json
    events_records = []
    for ev in included:
        rec = {
            "event_index": ev.get("event_index"),
            "start_s": ev.get("start_s"),
            "end_s": ev.get("end_s"),
            "start_clock": ev.get("start_clock") or seconds_to_clock(ev.get("start_s", 0)),
            "end_clock": ev.get("end_clock") or seconds_to_clock(ev.get("end_s", 0)),
            "peak_motion_score": ev.get("peak_motion_score"),
            "zone_label": ev.get("zone_label"),
            "included": ev.get("included", True),
        }
        desc = descriptions.get(ev.get("event_index"), "")
        if desc:
            rec["description"] = desc
        events_records.append(rec)
    events_json = json.dumps(events_records, indent=2)

    # Build new renderer artifacts (SVG timeline, scene breakdown)
    from app.core.intel_report_renderer import IntelReportRenderer, render as render_intel
    renderer = IntelReportRenderer()
    svg_timeline = renderer._build_svg_timeline(included, duration_s)
    scene_breakdown = renderer._build_scene_breakdown(included)

    html = render_intel({
        "source_name": Path(source_path).stem,
        "source_path": source_path,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "detection_mode": stats["detection_mode"],
        "duration_fmt": duration_fmt,
        "executive_summary": summary,
        "llm_notice": llm_notice,
        "stats": stats,
        "object_inventory": inventory,
        "svg_timeline": svg_timeline,
        "timeline": timeline,
        "scene_breakdown": scene_breakdown,
        "key_moments": key_moments,
        "heatmap_b64": heatmap_b64,
        "settings": settings,
        "moondream_available": FrameDescriber.is_available(),
        "events_json": events_json,
    })
    return HTMLResponse(html)


@router.post("/job/intel-report/export")
async def intel_report_export(request: Request):
    """Export intelligence report. Accepts optional JSON body: {"formats": ["md", "pdf"]}."""
    import json as _json

    # ------------------------------------------------------------------
    # 1. Parse optional formats body (backwards-compat: missing → both)
    # ------------------------------------------------------------------
    try:
        body = await request.json()
        formats: list = body.get("formats", ["md", "pdf"])
    except Exception:
        formats = ["md", "pdf"]

    VALID_FORMATS = {"md", "pdf"}
    if not formats or not all(f in VALID_FORMATS for f in formats):
        raise HTTPException(
            status_code=400,
            detail="formats must be a non-empty list containing only 'md' and/or 'pdf'",
        )

    # ------------------------------------------------------------------
    # 2. Session guards
    # ------------------------------------------------------------------
    snap = session.snapshot()
    job_id = snap.get("job_id")
    source_path = snap.get("source_path")

    if not job_id or not source_path:
        raise HTTPException(status_code=400, detail="No active job")

    if snap.get("status") == "detecting":
        raise HTTPException(status_code=400, detail="Detection is still in progress")

    included = [ev for ev in snap["events"] if ev.get("included", True)]
    if not included:
        raise HTTPException(
            status_code=400,
            detail="No events to report — no events are currently included",
        )

    # ------------------------------------------------------------------
    # 3. Normalise events — support both T006 (zone_label/peak_motion_score)
    #    and T007 (label/confidence/thumbnail_path) event formats.
    # ------------------------------------------------------------------
    for ev in included:
        if "end_s" not in ev:
            ev["end_s"] = ev.get("start_s", 0.0) + ev.get("duration_s", 0.0)
        if "peak_motion_score" not in ev:
            ev["peak_motion_score"] = float(ev.get("confidence", 0.0))
        if "zone_label" not in ev:
            ev["zone_label"] = ev.get("label")          # None → MOG2 motion
        if "start_clock" not in ev:
            ev["start_clock"] = seconds_to_clock(float(ev.get("start_s", 0.0)))
        if "end_clock" not in ev:
            ev["end_clock"] = seconds_to_clock(float(ev.get("end_s", 0.0)))

    job_dir = _job_dir(job_id)
    source_info = snap.get("source_info") or {}
    settings = snap.get("settings") or {}
    duration_s = float(source_info.get("duration_s", 0) or 0)

    florence_available = FrameAnalyzer.is_available()
    md_path_str: Optional[str] = None
    pdf_path_str: Optional[str] = None
    llm_used = False
    llm_notice = ""

    try:
        total_events = len(included)

        # ── Stage: thumbnails ────────────────────────────────────────
        session.update(
            report_stage="thumbnails",
            report_stage_current=0,
            report_stage_total=total_events,
        )
        for n, ev in enumerate(included):
            session.update(report_stage_current=n)

        # Generate thumbnails via ffmpeg (best-effort; silent on failure)
        try:
            thumbnail_gen.run(
                job_id=job_id,
                source_path=source_path,
                events=included,
                logger=_make_log_fn(job_id),
            )
        except Exception:
            pass  # Thumbnails are optional; continue without them

        # ── Stage: ai_analysis ──────────────────────────────────────
        session.update(
            report_stage="ai_analysis",
            report_stage_current=0,
            report_stage_total=total_events,
        )
        for n, ev in enumerate(included):
            ts = ev.get("start_clock", seconds_to_clock(float(ev.get("start_s", 0))))
            session.update(report_stage_current=n, report_stage_timestamp=ts)

            # Use thumbnail_path from event (T007) or job_dir thumbnail (T006)
            tp = ev.get("thumbnail_path")
            thumb = Path(tp) if tp else (
                job_dir / "thumbnails" / f"{ev['event_index']}.jpg"
            )
            analysis = (
                FrameAnalyzer.analyze(thumb)
                if thumb.exists()
                else {
                    "caption": "",
                    "object_caption": "",
                    "detections": [],
                    "clip_embedding_path": None,
                }
            )
            ev["caption"] = analysis.get("caption", "")
            ev["object_caption"] = analysis.get("object_caption", "")
            ev["detections"] = analysis.get("detections", [])

        # ── Executive summary via LLMSynthesizer (falls back gracefully) ──
        from app.core.narrative_synthesizer import (
            NarrativeSynthesizer,
            executive_summary as _exec_summary_fn,
            activity_stats,
            object_inventory,
            timeline_entries,
        )

        if LLMSynthesizer.is_available():
            try:
                narrative_obj = NarrativeSynthesizer()
                synth_obj = LLMSynthesizer()
                exec_summary_text, llm_used, llm_notice = synth_obj.synthesize(
                    included, duration_s, narrative_obj
                )
            except Exception:
                exec_summary_text = _exec_summary_fn(included, source_info, settings)
                llm_used = False
                llm_notice = "Executive summary: rule-based synthesis — LLM API unavailable"
        else:
            exec_summary_text = _exec_summary_fn(included, source_info, settings)
            llm_used = False
            llm_notice = "Executive summary: rule-based synthesis — LLM API unavailable"

        # Stats / inventory / timeline
        stats = activity_stats(included, source_info)
        inventory = object_inventory(included)
        descriptions = {ev.get("event_index", 0): ev.get("caption", "") for ev in included}
        timeline = timeline_entries(included, descriptions)

        # ── Stage: markdown ──────────────────────────────────────────
        if "md" in formats:
            session.update(report_stage="markdown", report_stage_current=0, report_stage_total=0)

            source_name = Path(source_path).stem
            generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Build JSON appendix records
            events_records = []
            for ev in included:
                idx = ev.get("event_index")
                rec = {
                    "event_index": idx,
                    "start_s": ev.get("start_s"),
                    "end_s": ev.get("end_s"),
                    "start_clock": ev.get("start_clock") or seconds_to_clock(ev.get("start_s", 0)),
                    "end_clock": ev.get("end_clock") or seconds_to_clock(ev.get("end_s", 0)),
                    "peak_motion_score": ev.get("peak_motion_score"),
                    "zone_label": ev.get("zone_label"),
                    "included": ev.get("included", True),
                }
                cap = ev.get("caption", "")
                if cap:
                    rec["caption"] = cap
                events_records.append(rec)

            # Build Markdown string
            lines = []
            lines.append(f"# Video Intelligence Report: {source_name}")
            lines.append(f"")
            lines.append(f"**Generated:** {generated_at}  ")
            lines.append(f"**Detection Mode:** {stats['detection_mode']}  ")
            lines.append(f"**Duration:** {seconds_to_clock(duration_s)}  ")
            lines.append(f"**Source:** {source_path}  ")
            lines.append(f"")

            lines.append(f"## Executive Summary")
            lines.append(f"")
            lines.append(exec_summary_text)
            lines.append(f"")

            lines.append(f"## Activity Statistics")
            lines.append(f"")
            lines.append(f"| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Events | {stats['event_count']} |")
            lines.append(f"| Active Duration | {stats['active_s']:.1f}s |")
            lines.append(f"| Active % | {stats['active_pct']:.1f}% |")
            lines.append(f"| Busiest Period | {stats['busiest_period']} |")
            lines.append(f"| Avg Confidence | {stats['avg_confidence']:.1%} |")
            lines.append(f"| Detection Mode | {stats['detection_mode']} |")
            lines.append(f"")

            if inventory:
                lines.append(f"## Object Inventory")
                lines.append(f"")
                lines.append(f"| Class | Count | First Seen | Last Seen |")
                lines.append(f"|-------|-------|------------|-----------|")
                for item in inventory:
                    lines.append(
                        f"| {item['label']} | {item['count']} | {item['first_clock']} | {item['last_clock']} |"
                    )
                lines.append(f"")

            lines.append(f"## Chronological Timeline")
            lines.append(f"")
            lines.append(f"| # | Start | End | Duration | Activity | Confidence | Description |")
            lines.append(f"|---|-------|-----|----------|----------|------------|-------------|")
            for entry in timeline:
                desc_cell = (
                    entry["description"].replace("|", "\\|")
                    if entry["description"] and entry["description"] != "N/A"
                    else "N/A"
                )
                lines.append(
                    f"| {entry['event_num']} | {entry['start_clock']} | {entry['end_clock']} "
                    f"| {entry['duration_s']:.1f}s | {entry['label']} | {entry['confidence_pct']}% "
                    f"| {desc_cell} |"
                )
            lines.append(f"")

            # Key moments
            key_moments_raw = sorted(
                included,
                key=lambda e: (-e.get("peak_motion_score", 0), e.get("event_index", 0)),
            )[:3]
            lines.append(f"## Key Moments")
            lines.append(f"")
            for km in key_moments_raw:
                idx = km.get("event_index", 0)
                start_clock = km.get("start_clock") or seconds_to_clock(km.get("start_s", 0))
                end_clock = km.get("end_clock") or seconds_to_clock(km.get("end_s", 0))
                label = km.get("zone_label") or "motion"
                conf = round(km.get("peak_motion_score", 0) * 100)
                tp = km.get("thumbnail_path")
                thumb_path = Path(tp) if tp else (job_dir / "thumbnails" / f"{idx}.jpg")
                desc = km.get("caption", "")

                lines.append(f"### Event {idx + 1} — {label} ({conf}%)")
                lines.append(f"**Time:** {start_clock}–{end_clock}  ")
                if thumb_path.exists():
                    lines.append(f"**Thumbnail:** `{thumb_path}`  ")
                if desc:
                    lines.append(f"**Description:** {desc}  ")
                lines.append(f"")

            lines.append(f"## Activity Heatmap")
            lines.append(f"")
            heatmap_path = job_dir / "heatmap.png"
            if heatmap_path.exists():
                lines.append(f"Heatmap: `{heatmap_path}`")
            else:
                lines.append(f"Heatmap not available for this run.")
            lines.append(f"")

            lines.append(f"## Detection Configuration")
            lines.append(f"")
            lines.append(f"| Setting | Value |")
            lines.append(f"|---------|-------|")
            for k, v in settings.items():
                lines.append(f"| {k} | {v} |")
            lines.append(f"")

            lines.append(f"## Data Appendix (JSON)")
            lines.append(f"")
            lines.append(f"```json")
            lines.append(_json.dumps(events_records, indent=2))
            lines.append(f"```")
            lines.append(f"")

            md_text = "\n".join(lines)

            # Enforce UTF-8 + 100KB guard
            assert len(md_text.encode("utf-8")) < 100 * 1024, (
                "Markdown file exceeds 100KB — reduce description cap in "
                "narrative_synthesizer.timeline_entries()"
            )

            output_dir = Path(snap.get("output_dir") or (Path.home() / "Desktop"))
            output_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            source_stem = Path(source_path).stem
            out_path = output_dir / f"{source_stem}_intelligence_{timestamp}.md"
            out_path.write_text(md_text, encoding="utf-8")
            md_path_str = str(out_path)

        # ── Stage: pdf (Qt bridge — fire-and-forget via main_window.py) ──
        if "pdf" in formats:
            session.update(report_stage="pdf", report_stage_current=0, report_stage_total=0)
            # pdf_path_str remains None here; the Qt bridge (main_window.py) writes
            # the PDF asynchronously and sets pdf_path in the session when done.

    finally:
        # Store paths BEFORE signalling done (H1 ordering guarantee)
        session.update(md_path=md_path_str, pdf_path=pdf_path_str)
        session.update(report_done_pending=True)   # MUST come BEFORE clearing report_stage
        session.update(report_stage="")

    return JSONResponse({
        "md_path": md_path_str,
        "pdf_path": pdf_path_str,
        "florence_available": florence_available,
        "llm_used": llm_used,
        "llm_notice": llm_notice,
    })


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
        raise HTTPException(status_code=400, detail="No active job")
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
        raise HTTPException(status_code=400, detail="No active job")
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
