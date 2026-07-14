# Data Model — CLIP Natural-Language Event Search (014)

## Entities

### SearchIndex (in-memory, module-level in `app/core/search_index.py`)

| Field | Type | Notes |
|-------|------|-------|
| `job_id` | `str \| None` | Job this index belongs to; `None` = no index |
| `event_count` | `int` | Event count at build time — staleness check with `job_id` |
| `vectors` | `dict[int, np.ndarray]` | `event_index → float32 (512,)` L2-normalized |
| `matrix` | `np.ndarray \| None` | `(N, 512)` stack of `vectors` for one-shot dot product |
| `event_indices` | `list[int]` | Row order of `matrix` |

Guarded by a `threading.Lock`. Never exposed directly — API reads snapshots.

### IndexStatus (same registry)

| Field | Type | Values / Notes |
|-------|------|----------------|
| `state` | `str` | `idle` → `indexing` → `ready`; terminal alternatives `unavailable`, `error` |
| `done` | `int` | Events embedded so far (monotonic within a run) |
| `total` | `int` | Events to embed this run |
| `reason` | `str` | Human-readable, non-empty when `unavailable`/`error` |

### QueryResult (transient — response body only, never stored)

| Field | Type | Notes |
|-------|------|-------|
| `event_index` | `int` | Matches session event `event_index` |
| `score` | `float` | Raw cosine similarity in [-1, 1]; UI renders `round(max(score,0)*100)`% |

Results sorted by `score` desc, tiebreak `event_index` asc. Events without a
vector (embed failed) are omitted (FR-012).

### Embedding sidecar (on disk — existing artifact, unchanged format)

`<JOBS_DIR>/<job_id>/thumbnails/<event_index>.clip.npy` — `float32 (512,)`
L2-normalized, written by `ClipIndexer.embed()`. Shared by Intelligence
Report and Search (FR-008). Derived artifact, not job state (Constitution
Principle I note in plan.md).

## State machine

```
                +--------------------- job change / detection re-run ---------------------+
                v                                                                          |
  idle ──start_background_index()──> indexing ──all events attempted──> ready ──query()──> (stays ready)
   |                                    |                                   
   |                                    ├── CLIP unavailable at start ──> unavailable(reason)
   |                                    └── unexpected exception ───────> error(reason)
   └── CLIP unavailable at start ─────> unavailable(reason)
```

- `start_background_index()` is idempotent: returns `False` (no new thread)
  when `state == indexing` for the same job (FR-009).
- Staleness: a request whose `(job_id, event_count)` differs from the stored
  pair resets to `idle` and rebuilds (FR-010 + detection re-run edge case).
- Per-event embed failure: logged, event skipped, `done` still advances —
  the run still ends `ready` (FR-012); `ready` with 0 vectors is legal and
  yields empty query results.

## Relationships

- `event_index` is the join key across: session events list ↔ thumbnails
  ↔ sidecars ↔ index vectors ↔ query results ↔ UI badges.
- The index NEVER mutates session state; the API layer reads
  `session.snapshot()` and passes `(job_id, source_path, events)` in.
