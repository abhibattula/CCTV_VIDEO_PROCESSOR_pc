# Research: Video Intelligence Export (Phase 6)

**Date**: 2026-06-25 | **Branch**: `006-video-intel-export`

All decisions were resolved during brainstorming (see
`docs/superpowers/specs/2026-06-25-video-intelligence-export-design.md`) and
confirmed via user Q&A. No NEEDS CLARIFICATION items remain.

---

## Decision 1: Vision Model Selection

**Decision**: Moondream2 local model via `pip install moondream`

**Rationale**:
- Fully offline after initial ~1.9GB download — no API key, no cloud data transfer
- Suitable for security/CCTV footage (privacy: no frames leave the machine)
- ~1-3s per frame on CPU (acceptable for report generation, not real-time)
- Optional dependency — app works fully without it

**Alternatives considered**:
- **OpenAI GPT-4 Vision**: Requires API key + sends CCTV frames to cloud. Rejected (privacy, cost, internet dependency).
- **Google Gemini Vision**: Same cloud concerns. Rejected.
- **BLIP-2**: Larger model, more complex install (requires transformers + accelerate). Rejected in favour of simpler Moondream API.
- **LLaVA / Ollama**: Ollama adds a separate process dependency. Deferred to Phase 7 for chatbot backend consideration.
- **CLIP embeddings**: Generates embedding vectors, not natural language descriptions — not suitable for human-readable reports. Rejected.

---

## Decision 2: Moondream API Call — `query()` vs `caption()`

**Decision**: Use `model.query(img, prompt)` (Q&A mode) with a CCTV-specific prompt

**Prompt used**:
> "Briefly describe what is happening in this security camera frame. Focus on people, vehicles, and any notable actions."

**Rationale**:
- `model.query()` allows a context-specific prompt that steers output toward security-relevant content (people, vehicles, actions)
- `model.caption()` generates generic captions without CCTV context ("a photo of a street")
- Q&A mode produces more informative, actionable descriptions for the report

**Return value handling**: `result.answer` if `hasattr(result, 'answer')` else `str(result)` — handles API version differences gracefully.

---

## Decision 3: PDF Generation — Qt printToPdf (reuse) vs WeasyPrint (new)

**Decision**: Reuse Phase 5's existing Qt `printToPdf` pattern (hidden `QWebEnginePage`)

**Rationale**:
- Already proven in Phase 5 for the incident report — same mechanism, zero new dependencies
- WeasyPrint requires `libpango` / `libcairo` system libraries on Linux — violates Principle II (no system-level dependencies)
- The Qt path adds zero new pip dependencies

**Pattern**: `_generate_intel_report_pdf()` in `shell/main_window.py` follows `_generate_pdf_report()` exactly:
hidden `QWebEnginePage` loads `/api/job/intel-report.html` → `printToPdf(pdf_path)` on
`loadFinished` → `deleteLater()` + list removal on `pdfPrintingFinished`.

---

## Decision 4: Markdown Structure for Phase 7 RAG Context

**Decision**: Dual timestamp format + embedded JSON appendix + < 100KB limit

**Rationale**:
- Dual timestamps (seconds + clock): chatbot can answer "what happened at 14:32?" AND "what happened at 2:15 into the video?" — covering both natural language query styles
- Embedded JSON appendix: machine-readable, enables programmatic queries by Phase 7 chatbot without parsing the Markdown tables
- `event_index` in JSON: enables cross-referencing with Key Moments section and thumbnails
- 100KB limit: conservative upper bound for any LLM context window (even 4K-token windows can hold ~100KB Markdown)

**Implementation for size control**:
- Descriptions truncated to 200 chars in the Markdown table if needed (full description always in JSON appendix)
- JSON appendix excludes `thumb_b64` fields (base64 images stay PDF-only)

---

## Decision 5: Moondream Model Cache Location

**Decision**: Accept HuggingFace default cache (`~/.cache/huggingface/`)

**Rationale**:
- `moondream.vl()` uses HuggingFace Hub's download mechanism; overriding requires setting `HUGGINGFACE_HUB_CACHE` env var or using `local_dir` parameter — adds complexity
- `~/.cache/huggingface/` is cross-platform (`~` resolves via `Path.home()` internally in huggingface_hub)
- This is consistent with how other optional ML tools (PyTorch, transformers) cache their assets
- Constitution's YOLO cache rule (`Path.home() / ".cctv_processor" / "models"`) is YOLO-specific, not a global requirement

**Note**: This means Moondream weights share space with any other HuggingFace models the user may have downloaded. Acceptable trade-off for simplicity.

---

## Decision 6: First-Run Download UX

**Decision**: Inline block — endpoint blocks, frontend shows spinner

**Rationale**:
- Simplest possible UX — same synchronous pattern as Phase 5's thumbnail generation
- No background threads, no progress callbacks, no download state in session
- On first call, `md.vl()` triggers the HuggingFace download internally — endpoint just waits
- Frontend shows "Generating..." spinner (standard fetch loading state) during the block
- One-time operation — subsequent calls use cached model (~0.1s startup)

**Alternative rejected**: Background pre-download on startup — adds complexity, wastes ~1.9GB if user never uses Moondream.

---

## Decision 7: Narrative Synthesis — Rule-Based vs LLM

**Decision**: Rule-based pure Python functions in `narrative_synthesizer.py`

**Rationale**:
- No LLM dependency for synthesis — keeps Phase 6 offline-capable and simple
- Structured event data already contains all the facts needed (counts, times, classes, scores)
- "Executive summary" can be a deterministic template: "During the X-minute video, N events were detected..."
- LLM-generated prose for the executive summary is a Phase 7+ enhancement (can reuse Phase 7's chatbot)

**Functions**:
- `executive_summary(events, source_info, settings) -> str` — 2-3 sentence template-based paragraph
- `activity_stats(events, source_info) -> dict` — computed stats (count, active_s, active_pct, busiest_period)
- `object_inventory(events) -> list[dict]` — YOLO only; empty list for MOG2
- `timeline_entries(events, descriptions) -> list[dict]` — merged rows for Jinja2 table

---

## Summary Table

| Decision | Choice | Status |
|----------|--------|--------|
| Vision model | Moondream2 local | Confirmed by user |
| Audio | None (Phase 6) | Confirmed by user |
| First-run download UX | Inline block | Confirmed by user |
| PDF mechanism | Qt printToPdf (reuse) | Confirmed by design |
| Markdown RAG format | Dual timestamps + JSON appendix | Confirmed by design |
| Moondream cache | HuggingFace default | Architecture decision |
| Narrative synthesis | Rule-based Python | Architecture decision |
| Moondream API | `model.query()` with CCTV prompt | Architecture decision |
