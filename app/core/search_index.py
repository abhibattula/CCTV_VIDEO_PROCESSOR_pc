"""
On-demand CLIP search index for the current job (014-clip-event-search).

Builds one embedding per event thumbnail in a background thread the first
time search is used, reusing `.clip.npy` sidecars already written by
Intelligence Report runs. Thread-safe module-level registry modeled on
app/core/model_downloader.py. Never imports app.session — the API layer
passes (job_id, source_path, events) in.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_index: dict = {
    "job_id": None,
    "event_count": 0,
    "vectors": {},          # event_index -> float32 (512,) unit vector
    "matrix": None,         # (N, 512) stack of vectors, row order = event_indices
    "event_indices": [],
}
_status: dict = {
    "state": "idle",        # idle | indexing | ready | unavailable | error
    "done": 0,
    "total": 0,
    "reason": "",
}
_thread: Optional[threading.Thread] = None


# ---------------------------------------------------------------------------
# Status / lifecycle
# ---------------------------------------------------------------------------

def get_status() -> dict:
    """Thread-safe snapshot of the index status."""
    with _lock:
        return dict(_status)


def reset_index() -> None:
    """Discard the index and return to idle (job change / New Project)."""
    with _lock:
        _index.update(job_id=None, event_count=0, vectors={}, matrix=None,
                      event_indices=[])
        _status.update(state="idle", done=0, total=0, reason="")


def start_background_index(job_id: str, source_path: str, events: list) -> bool:
    """Start building the index for (job_id, events) in a daemon thread.

    Idempotent: returns False when a build is already running, or when a
    ready index for the same (job_id, event_count) already exists. A request
    whose job/event-count differs from the stored index — or that arrives
    after an `error` — discards the old state and starts fresh.
    """
    global _thread
    from app.core.clip_indexer import ClipIndexer

    if not ClipIndexer.is_available():
        with _lock:
            _status.update(
                state="unavailable", done=0, total=0,
                reason=ClipIndexer.unavailable_reason
                or "CLIP is not available on this device.",
            )
        return False

    with _lock:
        if _status["state"] == "indexing":
            return False
        if (
            _status["state"] == "ready"
            and _index["job_id"] == job_id
            and _index["event_count"] == len(events)
        ):
            return False  # warm index — nothing to do
        # Fresh build (first use, stale index, or recovery from error)
        _index.update(job_id=job_id, event_count=len(events), vectors={},
                      matrix=None, event_indices=[])
        _status.update(state="indexing", done=0, total=len(events), reason="")

    def _run() -> None:
        try:
            _generate_thumbnails(job_id, source_path, events)
        except Exception as exc:
            # Thumbnails are best-effort: events whose thumbs are missing are
            # simply skipped by the embed loop below.
            logger.warning("Thumbnail generation for search index failed: %s", exc)

        try:
            thumbs_dir = _job_thumbs_dir(job_id)
            vectors: dict[int, np.ndarray] = {}
            for n, ev in enumerate(events):
                idx = int(ev["event_index"])
                try:
                    vec = _load_or_embed(thumbs_dir, idx)
                except Exception as exc:
                    logger.warning("Embed failed for event %s: %s", idx, exc)
                    vec = None
                if vec is not None:
                    vectors[idx] = vec
                with _lock:
                    _status["done"] = n + 1
            with _lock:
                if vectors:
                    event_indices = sorted(vectors)
                    matrix = np.stack([vectors[i] for i in event_indices])
                else:
                    event_indices, matrix = [], None
                _index.update(vectors=vectors, matrix=matrix,
                              event_indices=event_indices)
                _status.update(state="ready", reason="")
        except Exception as exc:  # never die silently
            logger.exception("Search index build crashed")
            with _lock:
                _status.update(state="error", reason=str(exc))

    _thread = threading.Thread(target=_run, name="clip-search-index", daemon=True)
    _thread.start()
    return True


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def rank(text: str) -> Optional[list]:
    """Rank the indexed events against a text query.

    Returns [(event_index, score), ...] sorted by score desc (tiebreak:
    event_index asc), [] for a ready-but-empty index, or None when the query
    could not be embedded (CLIP unavailable) or no ready index exists.
    """
    from app.core.clip_indexer import ClipIndexer

    query_vec = ClipIndexer.embed_text(text)
    if query_vec is None:
        return None
    return rank_with_vector(query_vec)


def rank_with_vector(query_vec: np.ndarray) -> Optional[list]:
    """Rank against an already-embedded query vector (see rank())."""
    with _lock:
        if _status["state"] != "ready":
            return None
        matrix = _index["matrix"]
        event_indices = list(_index["event_indices"])
    if matrix is None or not event_indices:
        return []
    scores = matrix @ np.asarray(query_vec, dtype="float32")
    pairs = sorted(
        zip(event_indices, scores.tolist()),
        key=lambda p: (-p[1], p[0]),
    )
    return [(int(i), float(s)) for i, s in pairs]


# ---------------------------------------------------------------------------
# Internals (monkeypatch seams for tests)
# ---------------------------------------------------------------------------

def _job_thumbs_dir(job_id: str) -> Path:
    from app.config import JOBS_DIR
    return Path(JOBS_DIR) / job_id / "thumbnails"


def _generate_thumbnails(job_id: str, source_path: str, events: list) -> None:
    """Ensure event thumbnails exist (thumbnail_gen skips existing files)."""
    from app.core import thumbnail_gen
    thumbnail_gen.run(job_id=job_id, source_path=source_path, events=events,
                      logger=lambda msg: logger.debug("[thumbs] %s", msg))


def _load_or_embed(thumbs_dir: Path, event_index: int) -> Optional[np.ndarray]:
    """Load an event's sidecar embedding, creating it from the thumbnail if
    missing. Returns a unit-norm float32 (512,) vector or None."""
    from app.core.clip_indexer import ClipIndexer

    sidecar = thumbs_dir / f"{event_index}.clip.npy"
    if not sidecar.exists():
        thumb = thumbs_dir / f"{event_index}.jpg"
        if not thumb.exists():
            return None
        written = ClipIndexer.embed(thumb)
        if written is None:
            return None
        sidecar = Path(written)
    vec = np.load(str(sidecar)).astype("float32").reshape(-1)
    norm = float(np.linalg.norm(vec))
    if norm == 0.0:
        return None
    return vec / norm


# ---------------------------------------------------------------------------
# Test hooks
# ---------------------------------------------------------------------------

def _reset_for_tests() -> None:
    reset_index()


def _set_ready_index_for_tests(job_id: str, vectors: dict) -> None:
    with _lock:
        event_indices = sorted(vectors)
        matrix = (
            np.stack([np.asarray(vectors[i], dtype="float32") for i in event_indices])
            if vectors else None
        )
        _index.update(job_id=job_id, event_count=len(vectors), vectors=dict(vectors),
                      matrix=matrix, event_indices=event_indices)
        _status.update(state="ready", done=len(vectors), total=len(vectors), reason="")
