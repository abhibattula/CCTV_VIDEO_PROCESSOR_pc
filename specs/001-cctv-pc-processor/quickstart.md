# Quickstart: CCTV Video Processor PC (Developer Setup)

**Date**: 2026-06-19 | **Branch**: `001-cctv-pc-processor`

---

## Prerequisites

- Python 3.11 or newer (`python --version`)
- Git
- ~500 MB free disk space (for pip packages including PyQt6-WebEngine)
- A test video file (any CCTV recording in MP4/MKV/AVI/MOV/TS format)

---

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

This installs PyQt6, FastAPI, OpenCV, imageio-ffmpeg (bundled FFmpeg), and all
other dependencies. No system FFmpeg or other external tool is required.

**Verify FFmpeg bundle**:
```bash
python -c "from app.utils.ffmpeg_path import get_ffmpeg; print(get_ffmpeg())"
```
Expected: an absolute path to a binary that exists on disk.

---

## 2. Run the tests

```bash
pytest tests/ -v
```

All tests should pass or skip (video-dependent tests skip if the test video is absent).
Zero failures is the baseline; fix any failures before proceeding.

---

## 3. Launch the app

```bash
python launcher.py
```

The app window opens, loads the Home page, and shows the drop zone. The terminal
shows uvicorn startup logs at WARNING level only.

**Backend health check** (in a separate terminal):
```bash
curl http://127.0.0.1:5151/api/health
```
Expected: `{"status":"ok"}`

---

## 4. End-to-end smoke test

1. Drop any CCTV video file onto the drop zone (or click Browse)
2. Confirm video info appears (resolution, codec, duration)
3. Optionally enter a recording start time (e.g., `08:00:00`)
4. Select detection mode (MOG2 or Object Detection) and sensitivity
5. Click **Start Detection**
6. Watch the Processing page — live log lines and progress bar update in real time
7. When detection completes, the Timeline page loads automatically
8. Event cards appear — click Preview on any card to watch the clip
9. Toggle events on/off as needed
10. Click **Export Selected** → Export page
11. Select Merged MP4, Original quality, Desktop as output folder
12. Click **Export Now**
13. Confirm the output file appears on your Desktop

---

## 5. Optional: YOLO / Object Detection mode

Object detection mode requires `ultralytics`. Install it separately:

```bash
pip install ultralytics
```

On first use, the YOLOv8n model (~6 MB) downloads automatically to
`~/.cctv_processor/models/yolov8n.pt`. Subsequent runs are fully offline.

---

## 6. Development workflow

- **Run a specific test**: `pytest tests/test_detection_engine.py -v`
- **Backend only** (no PyQt6): `python -m uvicorn app.main:app --port 5151 --reload`
  then open `http://localhost:5151` in a browser
- **Frontend only** (while backend runs): edit `static/js/pages/home.js` and reload
  the browser — no restart needed
- **Add a new API endpoint**: add to `app/api/job.py`, write a test in
  `tests/test_api_job.py` first, run pytest, then implement

---

## Validation checklist (confirms spec is met)

| SC | Check | How to verify |
|----|-------|---------------|
| SC-01 | 1h H.264 → export in <10 min | Time full workflow with `time` |
| SC-02 | H.264 export in <30s | Check export page ETA |
| SC-03 | Timestamps ±1s | Compare event start_s to actual motion in VLC |
| SC-04 | Works on Win/Mac/Linux | Run on each platform |
| SC-05 | 0-event hint appears | Use a static video (no motion) |
| SC-06 | Preview clip in <5s | Click Preview, measure time to playback |
| SC-07 | App ready in <5s | Time from `python launcher.py` to drop zone visible |
| SC-08 | Object detection ≥90% | Run on 10 clips with known walking person |
