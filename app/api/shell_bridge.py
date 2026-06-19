"""
Shell bridge: PyQt6 ↔ FastAPI inter-process communication.
The QWebEngineView cannot directly call Qt APIs, so the shell injects JS
listeners that watch for custom events and POSTs results back here.
"""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import app.session as session
from shell.platform_utils import open_folder as _open_folder

router = APIRouter()


class FilepathRequest(BaseModel):
    path: str


class OutputDirRequest(BaseModel):
    output_dir: str


@router.post("/shell/filepath")
async def set_filepath(req: FilepathRequest):
    session.update(pending_path=req.path)
    return JSONResponse({"ok": True, "path": req.path})


@router.get("/shell/pending-path")
async def get_pending_path():
    snap = session.snapshot()
    path = snap.get("pending_path")
    if path is not None:
        session.update(pending_path=None)
    return JSONResponse({"path": path})


@router.post("/shell/open-folder")
async def open_output_folder():
    snap = session.snapshot()
    output_path = snap.get("output_path")
    if not output_path:
        return JSONResponse({"ok": False})
    folder = str(Path(output_path).parent)
    try:
        _open_folder(folder)
        return JSONResponse({"ok": True})
    except Exception:
        return JSONResponse({"ok": False})


@router.post("/shell/set-output-dir")
async def set_output_dir(req: OutputDirRequest):
    session.update(output_dir=req.output_dir)
    return JSONResponse({"ok": True, "output_dir": req.output_dir})
