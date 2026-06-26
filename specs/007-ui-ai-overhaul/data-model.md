# Data Model — Phase 7: UI/UX Overhaul & Enhanced AI Analysis

## Entities

### FrameAnalysis

Structured output from `app/core/frame_analyzer.py` for one event thumbnail.

```python
{
    "caption": str,               # Florence-2 <MORE_DETAILED_CAPTION> — 2-5 sentence paragraph
    "object_caption": str,        # Florence-2 <REGION_CAPTION> on first detected object crop — "" if no detections
    "detections": list[dict],     # Florence-2 <OD> output — [] if no detections or Florence-2 absent
    "clip_embedding_path": str | None   # absolute path to .clip.npy sidecar, or None if CLIP absent
}
```

**Detection element shape**:
```python
{
    "label": str,               # e.g. "person", "car"
    "bbox": [float, float, float, float]   # [x1, y1, x2, y2] in pixel coordinates
}
```

**Validation rules**:
- `caption` may be `""` if Florence-2 is absent — never `None`
- `object_caption` is `""` (not `None`) when YOLO detections are absent or Florence-2 absent
- `detections` is `[]` (not `None`) when no objects detected or Florence-2 absent
- `clip_embedding_path` is `None` when `open-clip-torch` is not installed
- `bbox` values are pixel coordinates matching the thumbnail's actual dimensions (320×180 default)

---

### ReportFormat

User's output format choice for one report generation. Persisted in `localStorage["intelReportFormat"]`.

```typescript
// localStorage value (JSON-serialised)
{
    "md": boolean,   // true = write Markdown file
    "pdf": boolean   // true = generate PDF via Qt bridge
}
```

**Validation rules**:
- At least one of `md` or `pdf` must be `true` before the Generate button enables
- Default on first open: `{"md": true, "pdf": true}`
- POST body: `{"formats": ["md"]}` or `{"formats": ["pdf"]}` or `{"formats": ["md", "pdf"]}`
- API default (backwards compat): if `formats` omitted → `["md", "pdf"]`

---

### ReportStageEvent

SSE event emitted during report generation. Added to `app/api/stream.py`.

```python
# report_stage event (emitted at each stage boundary and periodically during ai_analysis)
{
    "type": "report_stage",
    "stage": str,         # "thumbnails" | "ai_analysis" | "markdown" | "pdf"
    "current": int,       # current item count (0 before stage starts, total when complete)
    "total": int,         # total item count for this stage (0 for single-step stages)
    "ts": str             # source video timestamp "HH:MM:SS" — only present during ai_analysis
}

# report_done event (emitted once, after all stages complete)
{
    "type": "report_done",
    "md_path": str | None,    # absolute path to written .md file, or null
    "pdf_path": str | None    # absolute path to generated .pdf file, or null
}
```

**State transitions**:
```
""  →  "thumbnails"  →  "ai_analysis"  →  "markdown"  →  "pdf"  →  ""
                                                          (pdf omitted if pdf=false)
```

---

### Session State Extensions

New fields added to `app/session.py` `_DEFAULTS` dict:

```python
# Report generation progress (all reset to defaults when session.reset() is called)
"report_stage": "",            # current stage name or "" when not generating
"report_stage_current": 0,
"report_stage_total": 0,
"report_stage_timestamp": "",  # video timestamp of frame currently being analysed
"report_done_pending": False,  # H1 FIX: set True once when generation completes;
                               # SSE loop emits report_done then clears to False
```

These fields are read by `stream.py` in the SSE poll loop:
- `report_stage != ""` → emit `report_stage` event
- `report_done_pending == True` → emit `report_done` event, then `session.update(report_done_pending=False)`

**Setting order in job.py at generation completion** (prevents race condition):
```python
session.update(report_done_pending=True)  # set BEFORE clearing report_stage
session.update(report_stage="")
```

---

### ActivityTimeline

Pure-Python SVG string representing event distribution across video duration.
Returned as a string by `intel_report_renderer.py`; embedded inline in `intel_report.html`.

```python
# Logical structure (not a Python class — just a string rendered from this data)
{
    "events": list[dict],    # from session.snapshot()["events"]
    "duration_s": float,     # from session.snapshot()["duration_s"]
    "width_px": 800,         # fixed viewBox width
    "height_px": 48,         # fixed viewBox height
    "rail_y": 20,            # y-offset of background rail
    "rail_h": 8              # height of background rail
}
```

**Colour mapping** (SVG fill values):
```python
COLOURS = {
    "mog2": "#6b7280",    # grey
    "yolo_person": "#3b82f6",   # blue
    "yolo_vehicle": "#f97316",  # orange
    "yolo_other": "#8b5cf6",    # purple
}
```

**Tick height formula**: `h = max(8, int(confidence * 32))`
**Tick x formula**: `x = int((event_start_s / duration_s) * 800)`

---

### SceneBreakdownEntry

Top-5 highest-confidence events rendered as full-paragraph cards in the intelligence report.

```python
{
    "rank": int,                 # 1–5
    "timestamp": str,            # "HH:MM:SS"
    "confidence": float,         # 0.0–1.0
    "caption": str,              # Florence-2 full paragraph or "" if absent
    "object_caption": str,       # Florence-2 crop description or ""
    "detections": list[dict],    # same shape as FrameAnalysis.detections
    "thumbnail_b64": str,        # base64-encoded JPEG with bounding boxes drawn
    "thumbnail_b64_original": str  # base64-encoded JPEG without boxes (fallback)
}
```

**Selection rule**: top 5 events sorted by `confidence` descending; if fewer than 5 events
exist, show all available events.

---

## CLIP Sidecar Files

### Location

CLIP embeddings are written alongside thumbnails using this naming convention:

```python
# thumbnail:  <output_dir>/thumb_XXXXXXXXX.jpg
# sidecar:    <output_dir>/thumb_XXXXXXXXX.clip.npy
```

Where `output_dir` is the directory returned by `app/core/thumbnail_gen.py`.

### Format

NumPy `.npy` file containing a 1D float32 array of shape `(512,)`.
Values are L2-normalised CLIP ViT-B/32 image embeddings.

```python
# Write
import numpy as np
np.save(str(sidecar_path), embedding)   # shape (512,), float32, L2-normalised

# Read (Phase 8)
embedding = np.load(str(sidecar_path))  # shape (512,)
```

### Lifecycle

- Written by `clip_indexer.py` during report generation (Stage 1: Thumbnails)
- Never deleted automatically; removed with the output folder when user clears results
- Phase 8 chatbot indexes these files to build a searchable FAISS index
