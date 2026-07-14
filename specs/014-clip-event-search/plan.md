# Implementation Plan: CLIP Natural-Language Event Search

**Branch**: `014-clip-event-search` | **Date**: 2026-07-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/014-clip-event-search/spec.md`
**Design**: `docs/superpowers/specs/2026-07-10-clip-search-design.md` (user-approved 2026-07-10)

## Summary

Add a natural-language search box to the Timeline page: the user types a
plain-English description; every event card gets a relevance badge computed as
the cosine similarity between the CLIP text embedding of the query and the
CLIP image embedding of that event's thumbnail. Embeddings are built on demand
(first search-box focus) in a background thread and reuse `.clip.npy` sidecars
already written by Intelligence Report runs. Three new backend units
(`ClipIndexer.embed_text`, `app/core/search_index.py`, `app/api/search.py`)
plus Timeline UI additions. No new dependencies.

## Technical Context

**Language/Version**: Python 3.12 (3.11+ supported)
**Primary Dependencies**: FastAPI 0.118 (existing), numpy 1.26 (existing), open-clip-torch + torch (existing *optional* AI extras — feature degrades gracefully without them)
**Storage**: none new — in-memory index dict (session-scoped); `.clip.npy` sidecar files continue to live in the job's thumbnails dir (existing pattern)
**Testing**: pytest (existing suite, 240 tests); ~15 new backend tests; frontend via quickstart scenarios (constitution Principle III frontend exemption)
**Target Platform**: Windows/macOS/Linux desktop + headless Raspberry Pi (search available only where the optional AI extras + CLIP weights exist)
**Project Type**: desktop app — FastAPI backend + vanilla-JS SPA in Qt WebEngine (or system browser on Pi)
**Performance Goals**: query over ready index < 2 s for 50 events (SC-001); first index of 50 events < 90 s desktop CPU (SC-002); warm re-open < 2 s (SC-004)
**Constraints**: zero regressions when CLIP absent (SC-005); no model inference at query time except one text encode (FR-013); index memory ≤ ~2 KB/event (512 × float32)
**Scale/Scope**: single job, ≤ a few hundred events; 3 new backend files + 1 extended, Timeline JS + CSS touches

## Constitution Check

*GATE: evaluated pre-Phase-0 and re-checked post-Phase-1 — PASS (no violations).*

1. **Principle I (session-first, no persistence)**: PASS. The index is an
   in-memory dict keyed by `job_id`, discarded on job change. `.clip.npy`
   sidecars are derived artifacts in the existing job thumbnails directory
   (same category as thumbnails/heatmaps written today), not job *state* — the
   session dict remains the single source of truth, and no `_DEFAULTS` key is
   persisted. No new session fields are required (index status lives in the
   search module's own registry, mirroring `model_downloader._status`).
2. **Principle II (cross-platform)**: PASS. All paths via `pathlib.Path`;
   no ffmpeg use beyond the existing `thumbnail_gen` (which already resolves
   via `ffmpeg_path`); no OS detection.
3. **Principle III (test-first)**: PASS. All backend logic (`embed_text`,
   `search_index`, `api/search`) gets failing tests before implementation.
   Timeline JS cites the frontend exemption — verification scenarios are in
   `quickstart.md`.
4. **Principle IV (callback-driven engines)**: PASS. `search_index` follows
   the `model_downloader` pattern (status registry + callbacks), does not
   import `app.session` for writes; the API layer passes the event list in.
   (Read-only `session.snapshot()` from the API layer, as all routers do.)
5. **Principle V (simplicity/YAGNI)**: PASS. In-memory dict instead of a
   vector DB; brute-force dot product (≤ few hundred 512-dim vectors — µs);
   no persistence of queries; no new dependencies.

## Project Structure

### Documentation (this feature)

```text
specs/014-clip-event-search/
├── spec.md              # Feature specification (done)
├── plan.md              # This file
├── research.md          # Phase 0 — decisions & rationale
├── data-model.md        # Phase 1 — entities & lifecycle
├── quickstart.md        # Phase 1 — manual verification scenarios (frontend)
├── contracts/
│   └── search-api.md    # Phase 1 — endpoint contracts
├── checklists/
│   └── requirements.md  # Spec quality checklist (done)
└── tasks.md             # Phase 2 (/speckit.tasks — not created by plan)
```

### Source Code (repository root)

```text
app/
├── core/
│   ├── clip_indexer.py      # EXTEND: add embed_text() + unavailable_reason
│   └── search_index.py      # NEW: on-demand index builder + status registry
├── api/
│   └── search.py            # NEW: /api/search/index, /status, /query
└── main.py                  # EXTEND: mount search router

static/
├── js/pages/timeline.js     # EXTEND: search box, badges, sort toggle, slider
├── js/session-state.js      # EXTEND (if needed): search UI state reset on new job
└── css/                     # EXTEND: search box + badge + dimming styles

tests/
├── test_clip_indexer.py     # EXTEND: embed_text tests
├── test_search_index.py     # NEW: builder/status/ranking tests
└── test_api_search.py       # NEW: endpoint contract tests
```

**Structure Decision**: follows the established backend layout exactly —
`core/` for engine logic, `api/` for routers, mirrored `tests/`. The search
module copies the proven `model_downloader.py` shape (module-level status
dict + lock + idempotent `start_background_*`), which the team (and tests)
already understand.

## Phase 0 — Research

See [research.md](research.md). All NEEDS CLARIFICATION: none (design
pre-approved). Key decisions recorded: open_clip text-encoding API usage,
cosine-via-dot-product on normalized vectors, index keyed by `job_id` with
staleness check on event count, reuse of `.clip.npy` sidecars, 409-vs-200
status codes for not-ready vs unavailable.

## Phase 1 — Design artifacts

- [data-model.md](data-model.md) — SearchIndex, IndexStatus, QueryResult
  entities, lifecycle state machine, invalidation rules.
- [contracts/search-api.md](contracts/search-api.md) — request/response
  schemas and status codes for the three endpoints.
- [quickstart.md](quickstart.md) — 10 manual verification scenarios covering
  the frontend exemption (search flow, sort toggle, dimming, compose-with-
  filters, unavailable state, Pi headless).

## Complexity Tracking

No constitution violations — table intentionally empty.
