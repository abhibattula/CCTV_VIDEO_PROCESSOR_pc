"""
Natural-language event search endpoints (014-clip-event-search).
Contracts: specs/014-clip-event-search/contracts/search-api.md
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import app.session as session
from app.core import search_index

router = APIRouter()


class QueryRequest(BaseModel):
    text: str


@router.get("/search/status")
async def search_status():
    """Current index lifecycle state (idle/indexing/ready/unavailable/error)."""
    return JSONResponse(search_index.get_status())


@router.post("/search/index")
async def search_index_start():
    """Start (or join) the on-demand index build for the current job."""
    snap = session.snapshot()
    if not snap.get("job_id") or not snap.get("source_path"):
        raise HTTPException(status_code=400, detail="No active job")
    if snap.get("status") == "detecting":
        raise HTTPException(status_code=400, detail="Detection is still in progress")

    started = search_index.start_background_index(
        job_id=snap["job_id"],
        source_path=snap["source_path"],
        events=snap.get("events", []),
    )
    return JSONResponse({"started": started, "status": search_index.get_status()})


@router.post("/search/query")
async def search_query(req: QueryRequest):
    """Rank the indexed events against a text description."""
    snap = session.snapshot()
    if not snap.get("job_id") or not snap.get("source_path"):
        raise HTTPException(status_code=400, detail="No active job")

    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must be non-empty")

    status = search_index.get_status()
    if status["state"] != "ready":
        detail = "Search unavailable" if status["state"] == "unavailable" \
            else "Search index not ready"
        raise HTTPException(status_code=409,
                            detail={"message": detail, "status": status})

    results = search_index.rank(text)
    if results is None:
        # Ready index but the query could not be embedded (CLIP regressed
        # mid-session, e.g. cache cleared) — same shape as unavailable.
        raise HTTPException(
            status_code=409,
            detail={"message": "Search unavailable",
                    "status": search_index.get_status()},
        )
    return JSONResponse({
        "results": [{"event_index": i, "score": s} for i, s in results],
    })
