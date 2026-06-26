# API Contracts — Phase 7: UI/UX Overhaul & Enhanced AI Analysis

## Existing Endpoints (unchanged behaviour, extended)

### GET /api/stream

**Existing contract**: Server-Sent Events (text/event-stream); polls `session.snapshot()` every ~500 ms.

**Phase 7 additions** — new event shapes emitted when `report_stage != ""`:

```json
// Emitted once per polling cycle while report is generating
{
  "type": "report_stage",
  "stage": "thumbnails" | "ai_analysis" | "markdown" | "pdf",
  "current": 0,
  "total": 12,
  "ts": "00:01:23"
}
```

```json
// Emitted once when report generation completes
{
  "type": "report_done",
  "md_path": "/path/to/report.md",
  "pdf_path": "/path/to/report.pdf"
}
```

**Field semantics for `report_stage` event** (L2 FIX — clarifies FR-009 mapping):
- `current` = the frame number currently being analysed (1-based during `ai_analysis` stage)
- `total` = total number of frames to analyse in this stage
- `ts` = source video timestamp of the frame being analysed (e.g. "00:01:23")
- For single-step stages (`markdown`, `pdf`): `current=0`, `total=0`, `ts=""` — the stage simply appears active then completes

**Backwards compatibility**: New event types are additive. Existing consumers that
only handle `progress`, `event`, `complete` events are unaffected — unknown event
types MUST be silently ignored by all clients.

---

### GET /api/job/status

**Existing contract**: Returns current job state snapshot.

**Phase 7 additions** — new fields in response body:

```json
{
  "...": "existing fields unchanged",
  "report_stage": "",
  "report_stage_current": 0,
  "report_stage_total": 0,
  "report_stage_timestamp": "",
  "report_done_pending": false,
  "florence_available": true,
  "llm_available": false
}
```

- `florence_available`: `true` if `transformers` is installed and `Florence-2-base` model weights are cached
- `llm_available`: `true` if `anthropic` is installed and `ANTHROPIC_API_KEY` env var is set

---

### POST /api/job/intel-report/export

**Existing contract**: Generates and writes intelligence report. Returns paths.

**Phase 7 changes**:

**Request body** (JSON):
```json
{
  "formats": ["md", "pdf"]
}
```

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `formats` | `list[str]` | No | `["md", "pdf"]` | Each element must be `"md"` or `"pdf"`. At least one required. |

**Response body** (JSON):
```json
{
  "md_path": "/path/to/report.md",
  "pdf_path": "/path/to/report.pdf",
  "florence_available": true,
  "llm_used": false,
  "llm_notice": ""
}
```

| Field | Type | Always present | Notes |
|---|---|---|---|
| `md_path` | `str \| null` | Yes | `null` if `"md"` not in `formats` |
| `pdf_path` | `str \| null` | Yes | `null` if `"pdf"` not in `formats` or PDF generation failed |
| `florence_available` | `bool` | Yes | Was Florence-2 used for AI descriptions? |
| `llm_used` | `bool` | Yes | Was Claude Haiku API used for executive summary? |
| `llm_notice` | `str` | Yes | `""` if LLM used; notice text if fallback used (e.g. "rule-based synthesis — LLM API unavailable") |

**Error responses**:

| Status | Condition |
|---|---|
| `400 Bad Request` | `formats` is empty list or contains invalid values |
| `409 Conflict` | Job not in `complete` state (no events to report on) |
| `500 Internal Server Error` | Unexpected exception during generation |

**Backwards compatibility**: Clients that call without a body (no `formats`) continue
to receive both `md_path` and `pdf_path` as before. The `moondream_available` field
from Phase 6 is REMOVED and replaced by `florence_available`. Any client checking
`moondream_available` must be updated.

**Breaking change**: `moondream_available` → `florence_available`. (Affects only
`export.js` which is updated in T009.)

---

### POST /api/job/intel-report/preview

**Existing contract**: Generates HTML preview for Qt WebEngine. Unchanged in Phase 7
behaviour — it generates the HTML only, no PDF, no `formats` param.

**Phase 7 additions**: HTML output gains Scene Breakdown section, SVG activity
timeline, and bounding-box thumbnails. No API contract change.

---

## New Session State Fields (internal, exposed via /api/job/status)

See `data-model.md` → Session State Extensions for full field list.

These are internal fields managed by `app/session.py`; they are exposed as-is
in the `/api/job/status` snapshot and in the SSE stream events.

---

## AI Readiness Check Contract

Frontend uses these two fields from `/api/job/status` to render AI badges:

```
florence_available = true  →  badge: "Florence-2 ready" (green)
florence_available = false →  badge: "AI analysis unavailable" (red/grey)
llm_available = true       →  badge: "LLM synthesis on" (blue)
llm_available = false      →  (no LLM badge shown)
```

---

## Deprecated Fields

| Field | Replaced By | Removed In |
|---|---|---|
| `moondream_available` (on intel-report/export response) | `florence_available` | Phase 7 (T009) |
