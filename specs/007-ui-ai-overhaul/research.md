# Research — Phase 7: UI/UX Overhaul & Enhanced AI Analysis

## Florence-2-base (replaces BLIP-base)

**Decision**: Use `microsoft/Florence-2-base` via HuggingFace `transformers`

**Rationale**: Multi-task vision model with instruction-following capability. Supports
`<MORE_DETAILED_CAPTION>`, `<OD>`, `<REGION_CAPTION>` tasks. Smaller than BLIP
(~230 MB vs ~1.9 GB BLIP had on disk due to no-symlink duplication). Same pip install.

**Exact API**:
```python
from transformers import AutoProcessor, Florence2ForConditionalGeneration
import torch
from PIL import Image

# Load (class-level singleton, loads once)
model = Florence2ForConditionalGeneration.from_pretrained(
    "microsoft/Florence-2-base",
    torch_dtype=torch.float32,
    device_map="cpu"          # explicit — "auto" can fail on Windows CPU-only
)
processor = AutoProcessor.from_pretrained("microsoft/Florence-2-base")
model.eval()

# MORE_DETAILED_CAPTION
task = "<MORE_DETAILED_CAPTION>"
inputs = processor(text=task, images=image, return_tensors="pt").to("cpu")
ids = model.generate(**inputs, max_new_tokens=1024, num_beams=3)
raw = processor.batch_decode(ids, skip_special_tokens=False)[0]
parsed = processor.post_process_generation(raw, task=task, image_size=image.size)
caption = parsed["<MORE_DETAILED_CAPTION>"]   # key matches task string

# OD (object detection)
task = "<OD>"
# ... same pattern ...
parsed = processor.post_process_generation(raw, task=task, image_size=image.size)
detections = parsed["<OD>"]
# detections = {"bboxes": [[x1,y1,x2,y2], ...], "labels": ["person", ...]}

# REGION_CAPTION (crop description for YOLO bounding box)
task = "<REGION_CAPTION>"
# Note: pass the cropped sub-image directly, not a region prompt
crop = image.crop((x1, y1, x2, y2))
inputs = processor(text=task, images=crop, return_tensors="pt").to("cpu")
# ... generate, decode, post_process ...
object_caption = parsed["<REGION_CAPTION>"]
```

**Windows/CPU gotchas**:
- `device_map="cpu"` must be explicit — `"auto"` fails on CPU-only Windows
- `trust_remote_code=True` NOT needed for official `microsoft/*` models
- `num_beams=3` gives better quality vs greedy decoding at moderate cost
- First run downloads ~230 MB to `~/.cache/huggingface/hub/models--microsoft--Florence-2-base`

---

## CLIP ViT-B/32 (open-clip-torch, Phase 8 foundation)

**Decision**: Use `open_clip` library with `ViT-B-32-quickgelu` and `openai` weights

**Rationale**: 512-dim embeddings enable semantic frame search in Phase 8 chatbot.
~600 MB one-time download. CPU-compatible. Embeddings stored as `.npy` sidecars.

**Critical gotcha**: Model name MUST be `'ViT-B-32-quickgelu'` (with `-quickgelu` suffix)
when using `pretrained='openai'` — plain `'ViT-B-32'` loads different weights.

**Exact API**:
```python
import open_clip
import torch
import numpy as np
from PIL import Image

model, _, preprocess = open_clip.create_model_and_transforms(
    'ViT-B-32-quickgelu',   # REQUIRED: -quickgelu for openai pretrained weights
    pretrained='openai'
)
model.eval()

# Embed one image
img_tensor = preprocess(Image.open(str(image_path))).unsqueeze(0)  # (1, 3, 224, 224)
with torch.no_grad():
    features = model.encode_image(img_tensor)     # (1, 512)
    features /= features.norm(dim=-1, keepdim=True)  # L2 normalize

# Save
np.save(str(npy_path), features.squeeze().numpy())  # shape (512,)
```

---

## Claude Haiku API (anthropic SDK, optional LLM executive summary)

**Decision**: Use `anthropic` Python SDK with `claude-haiku-4-5-20251001`

**Rationale**: Cheapest Claude model (~$0.01/report). Produces analyst-quality prose
from structured event JSON. Graceful fallback when key absent or API error.

**Exact API**:
```python
import os
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

response = client.messages.create(
    model="claude-haiku-4-5-20251001",  # pinned snapshot ID — do NOT use alias
    max_tokens=512,                      # executive summary ~200-300 words
    messages=[{"role": "user", "content": prompt}]
)
summary = response.content[0].text
```

**Fallback triggers**: `ANTHROPIC_API_KEY` not set → skip entirely. Any exception
from `client.messages.create` → catch, log, fall back to rule-based synthesis.
Report header note: "Executive summary: rule-based synthesis — LLM API unavailable"

---

## SSE Stage Progress Architecture

**Decision**: Report generation updates session state; existing SSE stream picks it up

**Rationale**: POST `/job/intel-report/export` runs in FastAPI's sync thread pool.
The async SSE endpoint (`/api/stream`) polls `session.snapshot()` continuously.
No new endpoint needed — session state extension is sufficient.

**New session fields**:
```python
"report_stage": "",           # "" | "thumbnails" | "ai_analysis" | "markdown" | "pdf"
"report_stage_current": 0,    # current item count
"report_stage_total": 0,      # total item count  
"report_stage_timestamp": "", # video timestamp of current frame (e.g. "00:01:23")
```

SSE stream adds these fields to the emitted JSON when `report_stage` is non-empty.
Frontend export.js listens for `type: "report_stage"` events on the SSE connection.

---

## SVG Activity Timeline

**Decision**: Pure Python SVG string generation — no library dependency

**Rationale**: The timeline is a simple horizontal bar with tick marks. PIL/Pillow draws
bitmaps; for a scalable inline SVG in HTML+PDF, we generate the SVG string directly.

**Structure**:
```
<svg width="100%" height="48" viewBox="0 0 800 48">
  <rect x="0" y="20" width="800" height="8" fill="#2e3147" rx="4"/>
  <!-- one rect per event, x = (start_s/duration_s)*800, height = confidence*32 -->
  <rect x="{x}" y="{20 - h/2}" width="4" height="{h}" fill="{colour}" rx="2"/>
</svg>
```

Tick height scales with confidence: low (8px) → high (32px).
Tick colour matches detection mode: blue (YOLO person), orange (car), grey (MOG2).

---

## Bounding Box Annotation on Thumbnails

**Decision**: PIL/Pillow `ImageDraw` overlay on JPEG thumbnail at report generation time

**Rationale**: Thumbnails are already 320×180 JPEG. Drawing bounding boxes requires only
Pillow (already installed). Output is a new in-memory JPEG bytes object (not saved to disk)
that replaces the base64 thumbnail in the HTML template for Scene Breakdown cards only.

```python
from PIL import Image, ImageDraw, ImageFont
img = Image.open(str(thumb_path)).convert("RGB")
draw = ImageDraw.Draw(img)
for det in detections:  # from OD task
    x1, y1, x2, y2 = det["bbox"]  # already pixel coords from Florence-2
    draw.rectangle([x1, y1, x2, y2], outline="#4f8ef7", width=2)
    draw.text((x1 + 2, y1 + 2), det["label"], fill="#ffffff")
```

---

## Alternatives Considered

| Decision | Alternative | Rejected Because |
|---|---|---|
| Florence-2-base | BLIP-2 with Flan-T5 | 3-4 GB, doesn't fit on disk |
| Florence-2-base | LLaVA-1.5-7b | 7+ GB, requires GPU for reasonable speed |
| open-clip-torch | sentence-transformers CLIP | Different API, no advantage |
| Session-based SSE stages | New SSE endpoint on POST | Would require architectural change to stream.py |
| PIL bbox overlay | SVG overlay in HTML template | PIL approach works identically in PDF export |
