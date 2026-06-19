"""
FastAPI application factory.

create_app() is the single entry-point used by both the test suite and launcher.py.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.config import JOBS_DIR, PREVIEW_DIR
from app.core.log_buffer import log_buffer
import app.session as session_module
from app.api.job import router as job_router
from app.api.stream import router as stream_router
from app.api.shell_bridge import router as shell_router
from app.api.preview import router as preview_router
from app.api.system import router as system_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup / shutdown logic."""
    # Create required directories
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    # Wire the current asyncio loop into the log_buffer so worker threads can
    # push messages onto SSE subscriber queues.
    log_buffer.set_loop(asyncio.get_event_loop())

    # Reset session so any previous state from a prior run is cleared
    session_module.reset()

    # Clean up stale write-sentinels and preview files from a crashed session
    _recover_from_crash()

    yield

    # Shutdown — nothing to tear down (uvicorn handles socket close)


def _recover_from_crash() -> None:
    """
    On startup, look for any export.writing sentinel files inside JOBS_DIR.
    Each sentinel was written by the export engine at the start of an export
    and deleted on success. A surviving sentinel means the previous run crashed
    mid-export — delete the partial output and the sentinel.
    Also wipe the PREVIEW_DIR (clips are session-scoped).
    """
    for sentinel in JOBS_DIR.rglob("export.writing"):
        try:
            output_path_text = sentinel.read_text(encoding="utf-8").strip()
            if output_path_text:
                partial = Path(output_path_text)
                if partial.exists():
                    partial.unlink(missing_ok=True)
                    logger.info("Deleted partial export: %s", partial)
            sentinel.unlink(missing_ok=True)
            logger.info("Removed stale sentinel: %s", sentinel)
        except Exception as exc:
            logger.warning("Could not clean up sentinel %s: %s", sentinel, exc)

    # Wipe previews from last session
    import shutil
    if PREVIEW_DIR.exists():
        shutil.rmtree(PREVIEW_DIR, ignore_errors=True)
        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)


def create_app() -> FastAPI:
    """Build and return the FastAPI application instance."""
    app = FastAPI(title="CCTV Video Processor", lifespan=_lifespan)

    # ── Static root (resolved before any routes reference it) ─────────────────
    static_root = Path(__file__).parent.parent / "static"
    _index = static_root / "index.html"

    # ── Health endpoint ────────────────────────────────────────────────────────
    @app.get("/api/health")
    async def health():
        return JSONResponse({"status": "ok"})

    # ── SPA catch-all: serve index.html for all non-API, non-static routes ───
    @app.get("/")
    @app.get("/processing")
    @app.get("/timeline")
    @app.get("/export")
    async def spa(_=None):
        return FileResponse(str(_index))

    # ── Routers ────────────────────────────────────────────────────────────────
    app.include_router(job_router, prefix="/api")
    app.include_router(stream_router, prefix="/api")
    app.include_router(shell_router, prefix="/api")
    app.include_router(preview_router, prefix="/api")
    app.include_router(system_router, prefix="/api")

    # ── Static files ───────────────────────────────────────────────────────────
    if static_root.exists():
        app.mount("/static", StaticFiles(directory=str(static_root)), name="static")

    return app
