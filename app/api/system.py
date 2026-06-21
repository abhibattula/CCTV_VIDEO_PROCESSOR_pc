"""
System stats endpoint — CPU %, RAM %, optional temp.
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
