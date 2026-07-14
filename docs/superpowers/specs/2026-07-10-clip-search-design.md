# Phase 14 — CLIP Natural-Language Event Search — Design

**Date:** 2026-07-10
**Status:** Approved (user Q&A 2026-07-10)
**Scope decision:** Search first; batch processing deferred to Phase 15.

## Goal

Let a user type a plain-English description ("person in a red jacket", "white van
at the gate") into a search box on the Timeline page and rank the current job's
detected events by visual similarity to that text — using the CLIP ViT-B/32
embeddings the app already knows how to generate.

## Approved decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Phase scope | CLIP search only; batch = Phase 15 | Search rides on existing `.clip.npy` infrastructure — high value, no architecture change. Batch breaks the single-session model and deserves its own phase. |
| Embedding timing | On-demand when the search box is first opened | Doesn't slow detection; no dependency on the 5–20 min Intelligence Report; one-time "indexing…" wait only on first use; reuses embeddings a report pass already wrote. |
| Result display | Relevance % badge + Sort toggle (Relevance / Chronological) + relevance slider that dims weak matches | Semantic similarity is a ranking, not yes/no. Time order matters in CCTV review, so reordering is opt-in; dimming (not hiding) matches the existing filter behavior. |
| Search corpus | Event thumbnails only (one per event) | That's what's embedded today. Frame-by-frame or cross-video search waits for Phase 15+. |
| Dependencies | None new | open-clip-torch already optional; numpy already pinned. |

## Architecture — 4 units

### 1. `ClipIndexer.embed_text(query: str) -> Optional[np.ndarray]`
`app/core/clip_indexer.py` (extend existing class)

- Symmetric to the existing `embed()` (image): tokenize with open_clip's
  tokenizer, `encode_text`, L2-normalize, return float32 `(512,)` vector.
- Same lazy singleton model; returns `None` when CLIP unavailable; never raises.

### 2. On-demand index builder — `app/core/search_index.py` (new)

- `ensure_index(job_id, source_path, events) -> None` (runs in background thread):
  1. Generate missing thumbnails via existing `thumbnail_gen.run()`.
  2. For each event thumbnail without a `.clip.npy` sidecar, call
     `ClipIndexer.embed()` (skips ones already written by a report pass).
  3. Load all sidecars into an in-memory `{event_index: vector}` map.
- Thread-safe status registry, modeled on `model_downloader.py`'s proven
  pattern: `{state: idle|indexing|ready|unavailable|error, done, total, reason}`
  behind a lock; `start_background_index()` idempotent (returns False if running).
- Index invalidated on `session.reset()` / new job (keyed by `job_id`).

### 3. Search endpoints — `app/api/search.py` (new router, mounted at `/api`)

- `POST /api/search/index` — start/refresh index for the current job.
  Idempotent; returns `{started, status}` immediately.
- `GET /api/search/status` — status registry snapshot.
- `POST /api/search/query` `{"text": "..."}` →
  `{"results": [{"event_index": int, "score": float}, ...]}` sorted by score
  descending. Score = raw cosine similarity (dot product; vectors are
  normalized), a float in [-1, 1] — the frontend converts to a 0–100% badge
  via `round(max(score, 0) * 100)`. Guards: no active job → 400; index not ready →
  409 with status; CLIP unavailable → 200 with `state: unavailable` + reason
  (mirrors `/api/system/ai-status` conventions).

### 4. Search UI — Timeline page

`static/js/pages/timeline.js` (+ shared session-state as needed)

- Search box above the event list.
  - First focus → `POST /api/search/index`, poll `/status`, show
    "Indexing N of M events…" progress line until ready.
  - Enter / debounced input → `/query`; each event card gets a relevance badge
    (e.g. `84%`).
  - **Sort toggle:** Relevance ⇄ Chronological (view-only; include/exclude
    state and the canvas strip untouched).
  - **Relevance slider:** dims events below the chosen relevance (same
    dim-not-hide behavior as the label filter).
  - Clear (× / empty box) → restores normal timeline view.
- Composes with existing filters: label chips and score-threshold slider still
  apply; relevance is an additional dimension.
- CLIP unavailable → disabled search box with tooltip pointing at the Home
  page AI Models card (same voice as the AI card).

## Error handling

- All CLIP failures degrade to "search unavailable" with a reason string —
  never a crash, never a blocked timeline (pattern: `FrameAnalyzer.unavailable_reason`).
- Indexing failures on individual events skip that event (logged); query works
  over whatever subset embedded successfully.
- Session reset / New Project clears the in-memory index and status.

## Testing (~12–15 new backend tests)

- `embed_text`: shape (512,), unit norm, None when open_clip missing (monkeypatched).
- Ranking: synthetic normalized vectors → known cosine order; ties stable.
- Index builder: skips existing sidecars; status transitions idle→indexing→ready;
  concurrent start rejected; unavailable path when CLIP missing.
- Endpoints: guards (no job, not ready), query contract shape, idempotent index start.
- No GUI/needed-video tests; frontend verified by driving the real app (project convention).

## Out of scope (YAGNI)

- Frame-by-frame (non-thumbnail) search; cross-video search; persisted search
  history; vector database (in-memory dict is enough for one job's events);
  batch processing (Phase 15).
