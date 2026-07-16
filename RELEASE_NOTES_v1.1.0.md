# v1.1.0 — Natural-Language Search + Fast Scan

## ✨ New: Fast Scan — long recordings finish several times faster

- New **Scan Speed** control on the Home page: **Balanced** (default, samples
  5 frames/sec), **Fast** (2 frames/sec), or **Thorough** (every frame, the
  classic behavior).
- Video decoding now runs through an optimized FFmpeg pipeline that uses your
  **graphics chip's hardware decoder automatically** (Intel Quick Sync /
  NVIDIA), verified per file with graceful software fallback.
- Measured on heavy 1080p60 HEVC footage: **5.2× faster** end-to-end with the
  same events found. A 24-hour recording drops from overnight to ~3 hours.
- The Home page shows which acceleration is active (video decode method + AI
  compute device). Set `CCTV_FORCE_SW_DECODE=1` to force software decoding.
- On machines with a CUDA GPU and CUDA PyTorch, AI analysis (YOLO, Florence-2,
  CLIP) runs on the GPU automatically; CPU-only machines are unaffected.

## ✨ New: Search events by describing them

- Type a plain-English description on the Timeline page — "person in a red
  jacket", "white van at the gate" — and every event gets a **relevance badge**
  from CLIP visual similarity.
- Sort by relevance or keep chronological order; dim weak matches with a
  threshold slider. The index builds itself in the background on first use.
- Works fully offline once the AI models are downloaded; the search box
  explains itself when they aren't.

## 🔧 Fixes

- **CLIP model download was broken in v1.0.x** (the upstream CDN was retired)
  — downloads now come from the Hugging Face Hub and availability detection is
  fixed. If AI search/embeddings never activated for you, this release fixes it.
- Detection settings are now correctly recorded with each job (report
  "Detection Configuration" tables were rendering empty).
- Malformed videos longer than 30 minutes now warn clearly before their
  one-time repair instead of appearing to hang.
- Cancelling a scan always terminates the decoding process (no orphaned
  ffmpeg, files never stay locked).

**Test suite: 323 passed.** Upgrading from v1.0.x: install over the top — no
settings migration needed.
