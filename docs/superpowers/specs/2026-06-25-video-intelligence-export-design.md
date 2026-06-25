# Design: Video Intelligence Export (Phase 6)

**Date**: 2026-06-25  
**Branch**: `006-video-intel-export`  
**Status**: Approved — ready for speckit pipeline

---

## Problem Statement

After running detection, the user has structured event data (timestamps, labels, scores,
thumbnails, heatmap) but no way to understand *what happened* in the video without watching
it. This phase adds a "Video Intelligence Report" that translates detection data into natural
language, making the video's content readable and queryable without playback. It also
produces the RAG context document for Phase 7's in-app AI chatbot.

---

## Confirmed Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Vision model | Moondream2 local (~2GB) | Private/offline, no API key, acceptable quality |
| Audio | None for Phase 6 | Keeps scope clean; audio in future phase |
| Chatbot (Phase 7) | Built into the app | FastAPI + SPA Chat page |
| First-run model download | Inline block | Simplest, matches Phase 5 pattern |
| Output formats | Markdown + PDF | Markdown for AI, PDF for humans |
| moondream dependency | Optional (pip install) | Graceful fallback if not installed |

---

## Architecture

### New Components

#### `app/core/frame_describer.py`
Wraps Moondream2 with a class-level singleton (model loaded once per process).
Graceful `ImportError` fallback: returns `""` so reports still generate without descriptions.

```
FrameDescriber
├── is_available() → bool              # checks if moondream is importable
├── _model: ClassVar = None            # singleton loaded on first describe() call
└── describe(image_path: Path) → str  # returns caption or "" on any error
```

On first call when moondream IS installed:
- `md.vl()` triggers the ~2GB model download to `~/.cache/huggingface/`
- The HTTP endpoint blocks with an indeterminate spinner in the frontend
- Subsequent calls reuse the in-memory model (~0.1s GPU / 1-3s CPU per frame)

CCTV-context prompt used with `model.query()` (not `model.caption()`):
> "Briefly describe what is happening in this security camera frame. Focus on people, vehicles, and any notable actions."

#### `app/core/narrative_synthesizer.py`
Pure functions — no external dependencies. Generates natural language from event dicts.

| Function | Output |
|----------|--------|
| `executive_summary(events, source_info, settings)` | 2-3 sentence paragraph |
| `activity_stats(events, source_info)` | dict: count, active_s, active_pct, busiest_period |
| `object_inventory(events)` | list[dict] per class (YOLO only) |
| `timeline_entries(events, descriptions)` | merged list[dict] for table rows |

#### `app/core/intel_report_renderer.py`
Jinja2-based HTML renderer. Mirrors `app/core/report_renderer.py` exactly.
`render(context: dict) → str` — pure function, no I/O.

#### `app/templates/intel_report.html`
Self-contained HTML (inline `<style>`, all images as base64 data URIs).
Print-ready layout matching `report.html`'s existing style.

Sections: header → executive summary → activity stats → object inventory (YOLO) →
chronological timeline → key moments → heatmap → detection config → data appendix (JSON)

### Modified Components

#### `app/api/job.py` — 2 new endpoints

```
GET  /job/intel-report.html    → HTMLResponse (for Qt printToPdf)
POST /job/intel-report/export  → {"md_path": str, "moondream_available": bool}
```

Both require: active job, ≥1 included event, status not in {detecting, exporting}.
Both call `thumbnail_gen.run()` lazily (idempotent, skips existing files).
The export endpoint writes Markdown to `output_dir` and returns the path.

#### `shell/main_window.py` — fifth flag + handler

Follows Phase 5's PDF incident report pattern exactly:
- JS bridge flag: `window._cctvGenerateIntelReport = false`
- Event listener: `cctv:generate-intel-report` sets it to `true`
- `_handle_browse_flags()` gains a fifth check → calls `_generate_intel_report_pdf()`
- `_generate_intel_report_pdf()`: hidden `QWebEnginePage`, loads `/api/job/intel-report.html`,
  `printToPdf(pdf_path)` on `loadFinished`, `deleteLater()` + `_pending_report_pages.remove()`

#### `static/js/pages/export.js` — new card

After the existing incident report card:
- Button: "Generate Intelligence Report (Markdown + PDF)"
- Click: POST `/api/job/intel-report/export` → write Markdown, dispatch Qt PDF event
- Status: "Markdown saved to {md_path}. PDF generating to same folder."
- If `moondream_available: false`: append "Install moondream for visual descriptions."
- If moondream installed but model not yet downloaded: button status shows
  "Downloading Moondream2 model (~2GB, first time only)..." during the long block

---

## Output File Formats

### Markdown (`{stem}_intelligence_{timestamp}.md`)
Optimised for Phase 7 chatbot RAG context. Key invariants:
- Timestamps appear in BOTH seconds and clock format
- JSON appendix is valid `json.loads()`-parseable (no trailing commas)
- File size < 100KB for typical sessions (fits any LLM context window)
- `event_index` in JSON appendix cross-references thumbnails by number

### PDF (`{stem}_intelligence_{timestamp}.pdf`)
Generated by Qt's `printToPdf` from the HTML endpoint. Contains:
- All Markdown content
- Embedded thumbnails (base64 inline, 320×180 JPEG)
- Embedded heatmap image
- Styled tables and typography

---

## Markdown Structure (Phase 7 RAG Design)

```markdown
# Video Intelligence Report: {filename}
**Generated**: {datetime}  **Mode**: YOLO/MOG2  **Duration**: Xm Ys

## Executive Summary
{2-3 sentences: what happened, object counts, activity level}

## Activity Statistics
| Metric | Value |
| Total Events | N |
| Active Duration | Xs (X%) |
| ...

## Object Inventory  ← YOLO only
| Class | Count | First Seen | Last Seen |

## Chronological Timeline
| # | Time | Duration | Activity | Confidence | Zone | Description |

## Key Moments
### Event N — {time} · {class} · {confidence}%
**Visual**: {Moondream2 description or "N/A"}

## Activity Heatmap
{interpretation text}

## Detection Configuration
{settings table}

## Data Appendix (JSON)
```json
[{"event_index": 0, "start_s": 15.0, "start_clock": "14:00:15", ...}, ...]
```
```

---

## Moondream2 Integration

- **Install**: `pip install moondream` (optional — app works without it)
- **Model download**: ~1.9GB, HuggingFace hub, cached at `~/.cache/huggingface/`
- **First-run UX**: endpoint blocks (inline), frontend spinner shown, no timeout set
- **CUDA**: auto-detected by moondream/torch — fast on GPU, ~1-3s/frame on CPU
- **Singleton**: `FrameDescriber._model` lives for app process lifetime
- **Failure handling**: any exception in `describe()` returns `""` silently
- **requirements.txt**: documented as optional comment, not a hard dependency

---

## Test Strategy

All new `app/core/` code: TDD (tests written first, must fail before implementation).

### `tests/test_intel_report.py` (fail-first):
- `test_executive_summary_yolo_mentions_objects` — "person" in output for YOLO events
- `test_executive_summary_mog2_mentions_motion` — "motion" in output for MOG2 events
- `test_executive_summary_no_events_safe_fallback` — no crash, non-empty string
- `test_object_inventory_counts_classes` — person×3 + car×2 → correct dict
- `test_object_inventory_empty_for_mog2` — None zone_label events → empty list
- `test_activity_stats_correct_percentages` — math verified against fixture
- `test_frame_describer_absent_returns_empty` — monkeypatch moondream → None
- `test_frame_describer_missing_file_returns_empty` — non-existent path, no crash
- `test_intel_report_html_400_no_job` — endpoint guard
- `test_intel_report_html_400_no_included_events` — endpoint guard
- `test_intel_report_export_writes_md_file` — file exists at returned md_path
- `test_intel_report_markdown_has_json_appendix` — `json.loads()` succeeds on appendix

### Shell/Qt code: tested via driving script (same approach as Phase 4 Stop App / Phase 5 PDF)
### Frontend JS: verified by running the real app (Phase 3 constitution amendment exemption)

---

## Phase 7 Chatbot Implications

The Markdown format is chosen to support Phase 7's in-app chatbot:
1. Intelligence report Markdown loaded as LLM system context
2. LLM (claude-haiku-4-5 via Anthropic API, or local Ollama — Phase 7 decision) answers user questions
3. Questions the document must support:
   - "When was the first person detected?" → Timeline + JSON appendix
   - "How many events involved vehicles?" → Object inventory
   - "What happened around 2:30 PM?" → Timeline clock format
   - "What was the person in Event 3 doing?" → Key Moments descriptions

Phase 7 will add: a `/chat` SPA route, a `POST /api/chat` endpoint, and the LLM backend.
The intelligence report document is produced by Phase 6 and consumed by Phase 7 unchanged.

---

## Files Summary

| File | Action |
|------|--------|
| `app/core/frame_describer.py` | Create |
| `app/core/narrative_synthesizer.py` | Create |
| `app/core/intel_report_renderer.py` | Create |
| `app/templates/intel_report.html` | Create |
| `tests/test_intel_report.py` | Create |
| `app/api/job.py` | Modify (2 endpoints) |
| `shell/main_window.py` | Modify (1 flag + 1 method) |
| `static/js/pages/export.js` | Modify (1 card) |
| `requirements.txt` | Modify (optional moondream comment) |
| `ROADMAP.md` | Update (Phase 6 shipped) |

---

## Verification Checklist

- [ ] `pytest tests/ -v` — all existing 93+ tests green + all 12 new intel_report tests pass
- [ ] MOG2 mode: Markdown generated, JSON appendix parses cleanly
- [ ] YOLO mode: Object inventory section populated with class counts
- [ ] With moondream: descriptions column has natural language text
- [ ] Without moondream: report generates cleanly, descriptions "N/A", frontend note shown
- [ ] Zero included events: 400 response, no crash
- [ ] PDF visual check: thumbnails embedded, tables render, heatmap visible
- [ ] Chatbot smoke test: paste Markdown into Claude → answers "When first person detected?"
