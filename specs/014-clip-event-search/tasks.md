# Tasks: CLIP Natural-Language Event Search

**Feature**: `014-clip-event-search` | **Plan**: [plan.md](plan.md) | **Contracts**: [contracts/search-api.md](contracts/search-api.md)
**TDD**: constitution Principle III — every backend task pairs a failing-test task before its implementation task. Frontend JS tasks cite the exemption and map to quickstart scenarios.

## Phase 1: Setup

- [ ] T001 Verify baseline: run `python -m pytest tests/ -q` from repo root and confirm the pre-feature suite passes (record count; expect ≥ 240 passed/2 skipped) so later regressions are attributable.

## Phase 2: Foundational (blocking prerequisites for all user stories)

- [ ] T002 [P] Write failing tests for `ClipIndexer.embed_text()` in `tests/test_clip_indexer.py`: returns float32 shape (512,) unit-norm vector for a query when open_clip present (monkeypatched fake model); returns None when open_clip import fails; returns None (never raises) when the model call throws; long text (>77 tokens) does not raise.
- [ ] T003 Implement `embed_text(query: str)` in `app/core/clip_indexer.py`: lazy tokenizer via `open_clip.get_tokenizer("ViT-B-32-quickgelu")`, same singleton model as `_do_embed`, `encode_text` → L2-normalize → float32 (512,); guard clauses mirror `embed()`; add `unavailable_reason` classmethod/attr mirroring `FrameAnalyzer` so the API can report why. Run T002 tests to green.
- [ ] T004 [P] Write failing tests for the index registry in `tests/test_search_index.py`: initial status idle; `start_background_index()` transitions idle→indexing→ready (threads joined via polling with timeout); second start while indexing returns False (no second thread); staleness — different `job_id` OR different event count discards old index and rebuilds; per-event embed failure (monkeypatched `ClipIndexer.embed` raising for one event) still ends ready with that event absent; CLIP unavailable at start → state unavailable with non-empty reason; `rank(query_vec)` returns results sorted score-desc with event_index-asc tiebreak (synthetic normalized vectors with known cosine order); ready-with-zero-vectors yields empty results.
- [ ] T005 Implement `app/core/search_index.py`: module-level `_index`/`_status` dicts + `threading.Lock` (model: `app/core/model_downloader.py`); `get_status()`; `start_background_index(job_id, source_path, events)` idempotent daemon thread that (a) generates missing thumbnails via existing `app.core.thumbnail_gen.run`, (b) loads existing `<thumbnails>/<event_index>.clip.npy` sidecars, (c) calls `ClipIndexer.embed()` for missing ones, (d) builds the `(N,512)` matrix, updating done/total; `rank(text: str) -> list[tuple[int, float]]` embedding the query once and dot-producting; `reset_index()` for job change; `_reset_for_tests()`. Run T004 to green.
- [ ] T006 Mount the search router: create `app/api/search.py` with router + `GET /search/status` returning the registry snapshot; include it in `app/main.py` (`app.include_router(search_router, prefix="/api")`). Write the status-endpoint test first in `tests/test_api_search.py` (shape: state/done/total/reason keys), then implement to green.

**Checkpoint**: registry + text embedding fully tested; `/api/search/status` live.

## Phase 3: User Story 1 — Find events by describing them (P1)

**Goal**: text query → per-event relevance, sorted results, Timeline badges/sort/slider.
**Independent test**: with a ready index (fixtures inject synthetic vectors), POST a query and assert ranked results; UI via quickstart #2–6, #11.

- [ ] T007 [P] [US1] Write failing endpoint tests in `tests/test_api_search.py` for `POST /api/search/query`: 400 when no active job; 400 on empty/whitespace text; 409 with attached status when state is idle/indexing/error; 409 when unavailable; 200 `{"results":[{event_index, score}]}` sorted desc with tiebreak when ready (inject a ready index via `search_index._reset_for_tests()` + direct registry population); results omit events without vectors.
- [ ] T008 [US1] Implement `POST /api/search/query` in `app/api/search.py` per `contracts/search-api.md`, delegating ranking to `search_index.rank()`; exactly one `embed_text` call per query (assert via monkeypatch counter in a T007 test). Run T007 to green.
- [ ] T009 [US1] Timeline search UI in `static/js/pages/timeline.js` + styles in `static/css/`: search box above the event list; Enter/debounced submit → `/api/search/query`; render `round(max(score,0)*100)%` badge on each event card; Sort toggle Relevance ⇄ Chronological (view-only reorder of rendered cards; include/exclude, canvas strip, selection untouched); relevance slider that adds a `.search-dimmed` class (opacity) — never `display:none`; clear (×/empty) removes badges/dimming and restores chronological order; composes with existing label-chip + score-slider pipeline (both AND). Frontend exemption: verify via quickstart #2–6, #11.

**Checkpoint**: US1 delivers end-to-end search on any job whose index is ready.

## Phase 4: User Story 2 — First-use indexing without manual setup (P2)

**Goal**: first search-box focus builds the index automatically with progress; reuse cached sidecars.
**Independent test**: POST /index on a fresh job (fixtures), poll status to ready; UI via quickstart #1, #7, #8, #10.

- [ ] T010 [P] [US2] Write failing endpoint tests in `tests/test_api_search.py` for `POST /api/search/index`: 400 no active job; 400 while `status == "detecting"`; 200 `{started: true}` on first call (monkeypatched `start_background_index`); 200 `{started: false}` when already running/ready; staleness — changed event count triggers a fresh `started: true`.
- [ ] T011 [US2] Implement `POST /api/search/index` in `app/api/search.py` per contract, reading `session.snapshot()` for `(job_id, source_path, events, status)` guards. Run T010 to green.
- [ ] T012 [P] [US2] Write failing sidecar-reuse test in `tests/test_search_index.py`: pre-write a valid `.clip.npy` for one event (synthetic 512-vector), monkeypatch `ClipIndexer.embed` with a call counter → build index → embed called only for the events lacking sidecars; pre-written vector present in the matrix.
- [ ] T013 [US2] Implement sidecar reuse in `search_index` (load-before-embed ordering) if T005's implementation doesn't already satisfy T012; run to green.
- [ ] T014 [US2] Timeline indexing UX in `static/js/pages/timeline.js`: first focus of the search box → `POST /api/search/index`, poll `/api/search/status` every 1 s rendering "Indexing {done} of {total} events…", enable input on ready; disable with reason while job status is `detecting` or event count is 0; reset search UI state (query, results, sort mode, threshold) on New Project / new job via the existing `session-state.js` reset hook. Frontend exemption: quickstart #1, #7, #8, #10.

**Checkpoint**: search works on a fresh job with zero manual setup.

## Phase 5: User Story 3 — Graceful behavior when AI search isn't possible (P3)

**Goal**: CLIP-absent machines see a disabled search box with a pointer, nothing else degrades.
**Independent test**: monkeypatched-unavailable registry → status/query behave per contract; UI via quickstart #9.

- [ ] T015 [P] [US3] Write failing tests in `tests/test_search_index.py` + `tests/test_api_search.py`: when `ClipIndexer.is_available()` is False, `start_background_index` sets state unavailable with non-empty reason (no thread, no crash); `/api/search/status` surfaces it; `/api/search/query` returns 409 with that status; after `model_downloader.reset_ai_availability_caches()`-style cache reset (add ClipIndexer to that reset if not already), a subsequent index start can proceed (monkeypatch availability flipping False→True).
- [ ] T016 [US3] Implement the unavailable paths in `search_index` / `ClipIndexer.unavailable_reason`; extend `app/core/model_downloader.reset_ai_availability_caches()` to also clear ClipIndexer/search-index caches so models downloaded mid-session activate search without restart (US3-AC3). Run T015 to green.
- [ ] T017 [US3] Frontend disabled states in `static/js/pages/timeline.js`: on `state: "unavailable"`, disable the box with tooltip = reason + "download from the Home page AI Models card"; zero-event jobs show "no events to search". Frontend exemption: quickstart #9.

**Checkpoint**: all three stories complete and independently verifiable.

## Phase 6: Polish & Cross-Cutting

- [ ] T018 Run the full suite `python -m pytest tests/ -q`: everything green, ≥ 12 new tests total (SC-006), zero pre-existing failures (SC-005).
- [ ] T019 [P] Execute quickstart.md scenarios 1–11 against the running app (scenario 12 optional/hardware) and record PASS/FAIL in the PR description; fix any UI defects found and re-verify.
- [ ] T020 [P] Documentation: README.md Features list + USER_MANUAL.md new "Searching events by description" section (search box, badges, sort toggle, slider, indexing wait, unavailable state); note thumbnails-only scope.

## Dependencies & Execution Order

- Phase 2 blocks everything (T002→T003, T004→T005, then T006).
- US1 (T007→T008→T009) and US2 (T010→T011, T012→T013, T014) both depend on Phase 2; T007/T010/T012 are parallelizable [P] after Phase 2; T009 depends on T008; T014 depends on T011.
- US3 (T015→T016→T017) depends on Phase 2 only; parallelizable with US1/US2 backend work.
- Polish (T018–T020) last; T019 requires T009+T014+T017.

**MVP scope**: Phase 2 + US1 (assumes an index built by a prior Intelligence Report run) — but US2 is required for the spec's headline UX, so the target increment is Phases 2–4.

## Implementation strategy

Strict TDD per constitution: each test task must FAIL before its paired
implementation task starts, and pass after. Superpowers skills in effect
during implementation: test-driven-development, verification-before-completion.
