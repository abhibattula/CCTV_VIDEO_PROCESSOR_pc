# Feature Specification: CLIP Natural-Language Event Search

**Feature Branch**: `014-clip-event-search`
**Created**: 2026-07-10
**Status**: Draft
**Input**: User description: "Phase 14 — CLIP Natural-Language Event Search: type a plain-English description into a search box on the Timeline page and rank the current job's detected events by visual similarity, using the CLIP embeddings the app already generates. Approved design: docs/superpowers/specs/2026-07-10-clip-search-design.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find events by describing them (Priority: P1)

A reviewer has finished detection on an hour of CCTV footage and has 40 events
on the Timeline. Instead of previewing each one, they type "person in a red
jacket" into a search box. Each event card gains a relevance percentage for
that description, and the reviewer can immediately see which events are worth
opening first.

**Why this priority**: This is the feature — turning the already-generated
visual embeddings into a working search delivers the entire user value of the
phase. Everything else supports it.

**Independent Test**: Load a video, run detection, type a query describing
something visible in one event's thumbnail; that event receives a visibly
higher relevance percentage than unrelated events.

**Acceptance Scenarios**:

1. **Given** a completed detection with events and a ready search index,
   **When** the user submits a text query, **Then** every event card shows a
   relevance percentage for that query within 2 seconds.
2. **Given** a submitted query, **When** the user switches the sort toggle to
   "Relevance", **Then** events reorder best-match-first; switching back to
   "Chronological" restores time order while keeping the badges.
3. **Given** a submitted query, **When** the user moves the relevance slider,
   **Then** events below the chosen relevance dim (they are not removed and
   their include/exclude state is untouched).
4. **Given** an active query, **When** the user clears the search box,
   **Then** the timeline returns to its normal appearance (no badges, no
   relevance dimming, chronological order).
5. **Given** an active label-chip filter, **When** the user also submits a
   search query, **Then** both apply together (the query never un-hides events
   the label filter hides).

---

### User Story 2 - First-use indexing without manual setup (Priority: P2)

The first time the reviewer opens the search box for a job, the app prepares
the search data itself (creating any missing event thumbnails and their visual
embeddings in the background), shows "Indexing N of M events…" progress, and
enables search when done. Embeddings already produced by a previous
Intelligence Report run are reused instead of recomputed.

**Why this priority**: Without automatic indexing the search box would only
work after a 5–20 minute AI report pass. This story makes P1 usable on any
job, but P1 defines the behavior once an index exists.

**Independent Test**: On a fresh job (no report run), focus the search box;
progress reaches N of N and search becomes usable without running anything
else.

**Acceptance Scenarios**:

1. **Given** a completed detection whose events have no embeddings yet,
   **When** the user first focuses the search box, **Then** indexing starts
   automatically and shows "Indexing N of M events…" progress until ready.
2. **Given** some events already have embeddings from an Intelligence Report,
   **When** indexing runs, **Then** those events are skipped (not recomputed)
   and only missing ones are embedded.
3. **Given** indexing is already running, **When** the user focuses the search
   box again (or another indexing request arrives), **Then** no second
   indexing run starts.
4. **Given** the user starts a New Project or loads a different video,
   **When** they open search on the new job, **Then** the previous job's index
   is not reused; indexing reflects the new job's events.

---

### User Story 3 - Graceful behavior when AI search isn't possible (Priority: P3)

On a machine without the AI models (CLIP not downloaded, or the optional AI
packages not installed), the search box appears disabled with a short
explanation pointing at the Home page AI Models card — the Timeline otherwise
works exactly as before.

**Why this priority**: Protects the baseline experience; the app must never
error or block review because an optional AI capability is absent.

**Independent Test**: With CLIP unavailable, open the Timeline: search is
visibly disabled with an explanation, and all existing Timeline features work
unchanged.

**Acceptance Scenarios**:

1. **Given** CLIP is unavailable, **When** the Timeline loads, **Then** the
   search box is disabled with a tooltip/message explaining why and pointing
   to the Home page AI Models card.
2. **Given** an individual event's embedding failed during indexing, **When**
   the user searches, **Then** results cover the successfully indexed events
   and the failed event simply shows no relevance badge.
3. **Given** CLIP models are downloaded via the AI Models card while the app
   is running, **When** the user next focuses the search box, **Then**
   indexing can start without restarting the app.

---

### Edge Cases

- Detection still running → the search box is disabled until the run
  completes; the index is always built over the final event set.
- Query submitted while indexing is still running → user sees the indexing
  progress state, not an error; query runs when ready (or user retries).
- Empty or whitespace-only query → treated as clearing the search, never sent.
- Job with zero events → search box disabled with "no events to search".
- Very long query text → accepted (model truncates internally); no crash.
- All events' relevance below the slider threshold → all cards dim, none
  disappear; the existing "no events match" empty-state does NOT trigger
  (dimming is not filtering).
- Detection re-run on the same job → previous index discarded; next search
  re-indexes the new events.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to enter a free-text description on the
  Timeline page and receive a per-event relevance score for the current job's
  events.
- **FR-002**: Relevance MUST be displayed on each event card as a percentage
  badge (0–100), where higher means visually closer to the description.
- **FR-003**: Users MUST be able to toggle between relevance-ordered and
  chronological ordering; the toggle is view-only and MUST NOT alter event
  include/exclude state, the canvas strip semantics, or export behavior.
- **FR-004**: Users MUST be able to set a minimum-relevance threshold that
  visually dims (never removes) events below it.
- **FR-005**: Clearing the search MUST restore the timeline's normal
  appearance and ordering.
- **FR-006**: Search MUST compose with the existing label-chip filter and
  score-threshold slider (all conditions apply simultaneously).
- **FR-007**: The system MUST build the search index on demand the first time
  search is used for a job: creating missing event thumbnails and their
  visual embeddings in the background while showing per-event progress.
- **FR-008**: Indexing MUST reuse embeddings already stored for an event
  (e.g., from an Intelligence Report run) rather than recomputing them.
- **FR-009**: Only one indexing run MUST be active at a time; duplicate
  requests join the in-progress run.
- **FR-010**: The index MUST be scoped to the current job and discarded when
  the job changes (new video, New Project, detection re-run).
- **FR-011**: When the AI search capability is unavailable, the search box
  MUST be disabled with a reason message pointing to the Home page AI Models
  card, and no Timeline functionality may degrade.
- **FR-012**: Failures embedding individual events MUST NOT fail indexing or
  querying; affected events are excluded from results.
- **FR-013**: Query evaluation over an existing index MUST NOT re-run any
  model inference on images (text is encoded once per query; ranking is a
  vector comparison).

### Key Entities

- **Search index**: per-job, in-memory collection mapping each event to its
  visual embedding vector; has a lifecycle state (idle → indexing → ready /
  unavailable / error) with progress (done/total) and a human-readable reason
  when unavailable.
- **Query result**: ordered list of (event, relevance score) pairs for one
  query text; transient — not persisted.
- **Embedding sidecar**: the stored per-thumbnail embedding file that
  survives between features (report ↔ search) so work is never repeated.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a job of 50 events with a ready index, submitting a query
  updates every event's relevance badge in under 2 seconds.
- **SC-002**: First-time indexing of 50 events completes in under 90 seconds
  on a typical desktop CPU, with visible progress throughout.
- **SC-003**: A query describing distinctive visible content in one event
  ranks that event in the top 3 of 50 in at least 8 of 10 trial queries
  (manual acceptance trial on real footage).
- **SC-004**: Re-opening search on a job whose events were already indexed
  reaches "ready" in under 2 seconds (no recomputation).
- **SC-005**: With AI models absent, the Timeline renders and all pre-existing
  features behave identically to v1.0.1 (zero regressions in the existing
  test suite).
- **SC-006**: The full automated test suite passes with ≥ 12 new tests
  covering ranking, indexing lifecycle, and unavailability paths.

## Assumptions

- Search operates on one event thumbnail per event (the representative frame
  already used by reports); frame-by-frame and cross-video search are out of
  scope (deferred to the batch-processing phase).
- The optional AI packages and CLIP weights follow the existing AI Models
  card flow; this feature adds no new dependencies or downloads.
- Relevance quality is bounded by CLIP ViT-B/32's capability on CCTV-style
  thumbnails; SC-003's manual trial is the acceptance bar, not a model
  benchmark.
- Search history, saved queries, and persistence of query results across
  sessions are out of scope.
- The existing single-job session model is unchanged; multi-job/batch search
  belongs to Phase 15.
