# Phase 1 Contracts: Phase 5 — Professional Reporting & Activity Insights

Four new endpoints on the existing `app/api/job.py` router. All follow this
project's established conventions: JSON bodies for `POST`, `FileResponse`/
`HTMLResponse` for `GET`, `JSONResponse({"error": ...}, status_code=...)` for
client errors — no new error-handling pattern introduced.

## `GET /api/job/heatmap`

Serves the cached activity heatmap for the current job, if one exists.
Mirrors `/api/job/preview-frame`'s existing shape, except it never generates
on demand (a heatmap requires a detection pass, not a single-frame grab).

| | |
|---|---|
| **Request** | No body. |
| **200** | `image/png` — the heatmap image at source resolution. |
| **400** | `{"error": "No active job"}` — no job loaded at all. |
| **404** | `{"error": "Heatmap not available yet"}` — job exists, but no detection has completed for it, or the completed run detected zero activity. |

## `GET /api/job/report.html`

Renders the Incident Report as a standalone HTML document. Called directly
by the frontend (`fetch`, for inline preview if ever added) and by the Qt
shell's hidden `QWebEnginePage` (for PDF conversion). Has a side effect:
lazily generates thumbnails for any included event that doesn't have one
cached yet.

| | |
|---|---|
| **Request** | No body. Always reflects the current `included` set — no `label_filter` parameter in this version (see plan's "Explicitly Not in This Plan"). |
| **200** | `text/html` — the full standalone report document (CSS inlined, images base64-inlined). |
| **400** | `{"error": "No active job"}` — no job loaded, or no source file recorded. |
| **400** | `{"error": "..."}` (exact wording TBD by `/speckit.tasks`) — zero included events (FR-P5-008). |

## `POST /api/job/export/csv`

Writes the included events to a CSV file in the user's output folder.

**Request body**:
```json
{ "output_dir": "C:\\Users\\...\\Desktop" /* optional */, "label_filter": ["Person"] /* optional, default [] */ }
```

| | |
|---|---|
| **200** | `{"output_path": "C:\\...\\source_events_20260623_151234.csv"}` |
| **400** | `{"detail": "Cannot export from status '...' — run detection first."}` — wrong job status. |
| **400** | `{"detail": "No events match the current filter."}` — zero events after `included`/`label_filter` narrowing (FR-P5-017). |

`output_dir` resolution order: explicit request value → session's existing
`output_dir` → `Path.home() / "Desktop"` fallback — identical to
`export_job()`'s existing resolution order.

## `POST /api/job/export/json`

Identical contract to `/api/job/export/csv` above, except the written file
is `.json` (a JSON array of event objects) instead of `.csv`.

| | |
|---|---|
| **200** | `{"output_path": "C:\\...\\source_events_20260623_151234.json"}` |
| **400** | Same two error cases as the CSV endpoint. |

## Not a new HTTP endpoint: PDF generation trigger

PDF generation is **not** a new backend route — it's triggered via the
existing JS-flag-bridge mechanism (`window._cctvSaveReportPdf`, mirroring
`window._cctvShutdown` from Phase 4), handled entirely inside
`shell/main_window.py`'s Qt-side polling loop, which itself calls
`GET /api/job/report.html` internally (via a hidden `QWebEnginePage`) before
writing the PDF to disk. No contract entry is needed for this — it's
Qt-internal orchestration, not a new API surface.
