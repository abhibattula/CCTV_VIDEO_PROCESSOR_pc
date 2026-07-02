"""
System stats endpoint — CPU %, RAM %, optional temp.
Also AI model status/download endpoints so users who skipped the first-run
wizard can install AI models later from the Home page.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.utils.system import get_cpu_percent, get_ram_percent, get_cpu_temp

router = APIRouter()


@router.get("/system/stats")
async def system_stats():
    return JSONResponse({
        "cpu_pct":  get_cpu_percent(),
        "ram_pct":  get_ram_percent(),
        "cpu_temp": get_cpu_temp(),
    })


@router.get("/system/capabilities")
async def system_capabilities():
    try:
        import ultralytics  # noqa: F401
        yolo_available = True
    except Exception:
        yolo_available = False
    return JSONResponse({"yolo_available": yolo_available})


@router.get("/system/ai-status")
async def system_ai_status():
    """Full AI feature status: RAM gate, per-model presence, download state."""
    from app.config import AI_FEATURES_ENABLED, MODEL_DIR
    from app.core.frame_analyzer import FrameAnalyzer
    from app.core.clip_indexer import ClipIndexer
    from app.core import model_downloader

    florence_available = FrameAnalyzer.is_available()
    return JSONResponse({
        "ai_supported": AI_FEATURES_ENABLED,
        "florence_available": florence_available,
        "florence_reason": FrameAnalyzer.unavailable_reason,
        "clip_available": ClipIndexer.is_available(),
        "yolo_model_present": (MODEL_DIR / "yolov8n.pt").exists(),
        "download": model_downloader.get_status(),
    })


@router.post("/system/ai-download")
async def system_ai_download():
    """Start downloading missing AI models in the background (idempotent)."""
    from app.core import model_downloader

    started = model_downloader.start_background_download()
    return JSONResponse({
        "started": started,
        "download": model_downloader.get_status(),
    })
