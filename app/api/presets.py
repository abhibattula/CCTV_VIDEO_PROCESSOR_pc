"""
Custom export presets — user configuration, NOT job state.
Persisted to a flat JSON file under ~/.cctv_processor per the Principle I
exemption in constitution v1.1.0 (presets are reusable user config, unrelated
to any specific job).
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import PRESETS_FILE

router = APIRouter()

BUILTIN_PRESET_NAMES = {"Security Report", "Evidence Pack", "Quick Highlights"}


class PresetCreateRequest(BaseModel):
    name: str
    output_type: str = "merged"
    quality: str = "original"
    burn_in: bool = False
    label_filter: list[str] = []


def _load() -> list[dict]:
    if not PRESETS_FILE.exists():
        return []
    try:
        data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []  # corrupt/missing file → empty, never crash the app
    if not isinstance(data, list) or not all(isinstance(p, dict) for p in data):
        return []  # valid JSON but wrong shape → still treat as corrupt
    return data


def _save(presets: list[dict]) -> None:
    PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PRESETS_FILE.write_text(json.dumps(presets, indent=2), encoding="utf-8")


@router.get("/presets")
async def list_presets():
    return JSONResponse(_load())


@router.post("/presets")
async def create_preset(req: PresetCreateRequest):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Preset name cannot be empty")
    name_lower = name.lower()
    if name_lower in {b.lower() for b in BUILTIN_PRESET_NAMES}:
        raise HTTPException(status_code=400, detail=f"'{name}' is a built-in preset name")
    presets = _load()
    if any(p["name"].lower() == name_lower for p in presets):
        raise HTTPException(status_code=400, detail=f"Preset '{name}' already exists")
    new_preset = req.model_dump()
    new_preset["name"] = name
    presets.append(new_preset)
    _save(presets)
    return JSONResponse(new_preset)


@router.delete("/presets/{name}")
async def delete_preset(name: str):
    presets = _load()
    remaining = [p for p in presets if p["name"] != name]
    if len(remaining) == len(presets):
        raise HTTPException(status_code=404, detail=f"Preset '{name}' not found")
    _save(remaining)
    return JSONResponse({"deleted": name})
