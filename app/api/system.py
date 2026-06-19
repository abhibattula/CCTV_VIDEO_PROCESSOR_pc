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
