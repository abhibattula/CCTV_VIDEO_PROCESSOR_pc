# API Contracts — CLIP Natural-Language Event Search (014)

All routes mounted under the existing `/api` prefix. JSON in/out. No auth
(localhost app, matches all existing routers).

## POST /api/search/index

Start (or join) the on-demand index build for the current job.

**Request body**: none.

**Responses**:

| Case | Status | Body |
|------|--------|------|
| No active job (no `job_id`/`source_path`) | 400 | `{"detail": "No active job"}` |
| Detection running | 400 | `{"detail": "Detection is still in progress"}` |
| Started new build | 200 | `{"started": true,  "status": {…IndexStatus}}` |
| Build already running / already ready for this job | 200 | `{"started": false, "status": {…IndexStatus}}` |
| CLIP unavailable | 200 | `{"started": false, "status": {"state": "unavailable", "reason": "...", …}}` |

Idempotent: any number of calls yields at most one build thread per job.
A call for a job whose `(job_id, event_count)` differs from the stored index
discards the old index and starts a fresh build.

## GET /api/search/status

**Response 200** (always, mirroring `/api/system/ai-status` conventions):

```json
{
  "state": "idle | indexing | ready | unavailable | error",
  "done": 12,
  "total": 40,
  "reason": ""            // non-empty when unavailable/error
}
```

## POST /api/search/query

**Request body**: `{"text": "person in a red jacket"}`
`text` must be non-empty after `strip()`.

**Responses**:

| Case | Status | Body |
|------|--------|------|
| No active job | 400 | `{"detail": "No active job"}` |
| Empty/whitespace text | 400 | `{"detail": "text must be non-empty"}` |
| Index not ready (`idle`/`indexing`/`error`) | 409 | `{"detail": "Search index not ready", "status": {…IndexStatus}}` |
| CLIP unavailable | 409 | `{"detail": "Search unavailable", "status": {"state": "unavailable", "reason": "..."}}` |
| Ready | 200 | `{"results": [{"event_index": 3, "score": 0.31}, …]}` |

- `results` sorted by `score` desc, tiebreak `event_index` asc.
- Events whose embedding failed are absent from `results`.
- Exactly one `encode_text` model call per query; zero image inference (FR-013).

## Frontend consumption (informative)

- Badge: `round(max(score, 0) * 100)` + `%`.
- On 409 from `/query`: show/refresh the "Indexing N of M…" progress from the
  attached `status`, retry after ready.
- On `unavailable`: disable the search box, tooltip = `reason` + pointer to
  the Home page AI Models card.
