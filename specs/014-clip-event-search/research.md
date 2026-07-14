# Research — CLIP Natural-Language Event Search (014)

No open NEEDS CLARIFICATION items (design pre-approved via user Q&A,
2026-07-10). This file records the technical decisions and their rationale.

## D1 — Text encoding API

**Decision**: `open_clip.get_tokenizer("ViT-B-32-quickgelu")` +
`model.encode_text(tokens)`, L2-normalized, `float32 (512,)` — symmetric with
the existing `ClipIndexer._do_embed()` image path, same lazy singleton model.

**Rationale**: `ClipIndexer` already creates the model via
`open_clip.create_model_and_transforms("ViT-B-32-quickgelu", pretrained="openai")`;
`encode_text` on the same model guarantees the two embedding spaces match
(mismatched checkpoints silently destroy ranking quality). The tokenizer
truncates long queries internally (77-token context) — no length guard needed.

**Alternatives considered**: sentence-transformers CLIP wrappers (new
dependency — rejected, YAGNI); caching per-query text embeddings (queries are
one `encode_text` call ≈ tens of ms on CPU — not worth cache complexity).

## D2 — Similarity & ranking

**Decision**: cosine similarity computed as a dot product (both sides
L2-normalized), brute force over an `(N, 512)` numpy matrix; sort descending,
stable tiebreak by `event_index` ascending.

**Rationale**: N ≤ a few hundred events → one matrix-vector product is
microseconds. A vector database or ANN index would be pure overhead
(Principle V).

**Alternatives considered**: FAISS / sqlite-vec — rejected (new dependency,
zero benefit at this scale).

## D3 — Index storage & lifecycle

**Decision**: module-level registry in `app/core/search_index.py`:
`{job_id, vectors: dict[int, np.ndarray], matrix, event_indices, state, done,
total, reason}` behind a `threading.Lock`, plus an idempotent
`start_background_index()` — a direct copy of the proven
`model_downloader.py` pattern. The index is considered stale (and is rebuilt)
when the requesting job_id differs from the stored one **or** the stored
event count differs from the current event list (covers detection re-runs on
the same job_id).

**Rationale**: same concurrency shape the codebase already tests and
understands; no session schema changes (Principle I untouched).

**Alternatives considered**: storing the index in `app/session.py` — rejected
(numpy arrays in the session dict break `copy.deepcopy` cheapness in
`snapshot()` and add job-state fields for what is a derived cache).

## D4 — Embedding reuse

**Decision**: an event's sidecar path is
`<job_dir>/thumbnails/<event_index>.clip.npy` (what `ClipIndexer.embed()`
already writes next to `<event_index>.jpg`). Index build loads the sidecar if
present, else generates the thumbnail (via existing `thumbnail_gen.run`, which
itself skips existing files) and calls `ClipIndexer.embed()`.

**Rationale**: FR-008 for free; Intelligence Report and Search share one
artifact.

## D5 — HTTP status semantics

**Decision**:
- `POST /api/search/query` with no active job → **400** (matches every other
  router's "No active job" guard).
- Query while index not ready → **409 Conflict** with the status payload (the
  client shows indexing progress; 409 signals "valid request, wrong state").
- CLIP unavailable → **200** on `/status` with `state: "unavailable"` +
  `reason` (mirrors `/api/system/ai-status` which reports degraded capability
  as data, not as an HTTP error).

**Rationale**: consistency with existing endpoints beats REST purity debates.

## D6 — Frontend integration point

**Decision**: search UI lives in `timeline.js` (search box, badge render,
sort toggle, relevance slider); transient search state (query, results map,
sort mode, threshold) lives in module scope in `timeline.js` and resets on
page re-entry / New Project via the existing `session-state.js` reset hook.
Relevance badge = `round(max(score, 0) * 100)` + `%`.

**Rationale**: all Timeline features (filters, selection, undo) already live
there; search composes with — never replaces — the existing filter pipeline.

## D7 — Search-box availability gating

**Decision**: the box is enabled only when: job status is
`completed`/`cancelled`/`export_done`-family (events final), event count > 0,
and `/api/search/status` does not report `unavailable`. Otherwise disabled
with a reason tooltip (detecting → "available after detection"; no events →
"no events to search"; CLIP missing → pointer to Home AI Models card).

**Rationale**: spec edge cases; prevents indexing a moving event set.
