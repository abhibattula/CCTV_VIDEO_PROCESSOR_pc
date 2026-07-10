# Running on Raspberry Pi 4 / 5

This app runs on Raspberry Pi OS Bookworm (64-bit). The Python code is
identical to the desktop version — no separate Pi branch needed.

**Recommended: the pre-built .deb installer** (no Python required):
Download `cctv-video-processor_*_arm64.deb` from [GitHub Releases](https://github.com/abhibattula/CCTV_VIDEO_PROCESSOR_pc/releases) and run:
```bash
sudo apt install ./cctv-video-processor_*_arm64.deb
cctv-video-processor
```

**The Pi version is headless.** PyQt6 publishes no ARM64 wheels compatible with
Pi OS Bookworm (they require glibc ≥ 2.39; Bookworm has 2.36), so instead of an
embedded desktop window the launcher starts the backend and opens the web UI in
the Pi's own browser (Chromium). Everything else — detection, timeline review,
export, reports — works exactly like the desktop version. Press Ctrl+C in the
terminal to quit; if the browser doesn't open automatically, browse to
`http://127.0.0.1:5151`.

There is no first-run wizard on the Pi (it was a Qt dialog) — download AI models
from the **AI Models card on the Home page** instead. On Pis with less than 5 GB
RAM the card explains that AI captions are disabled; YOLO and MOG2 detection
still work fully.

---

## What works / what's different

| Feature | PC (Windows) | Pi 4/5 (Linux ARM64) |
|---------|-------------|-------------------|
| MOG2 detection | ✅ | ✅ (slower — ~1× real-time) |
| YOLO detection | ✅ | ✅ (~6 MB model via the AI Models card) |
| FFmpeg export | ✅ bundled binary | ✅ uses system `ffmpeg` |
| UI | ✅ embedded Qt window | ✅ same web UI, in the system browser (headless) |
| System tray | ✅ | ❌ (no Qt shell) |
| Temperature readout | ❌ (Windows) | ✅ via `vcgencmd` fallback |
| Florence-2 AI captions | ✅ (≥5 GB RAM) | ✅ on 8 GB Pi; ❌ below 5 GB RAM |
| First-run setup wizard | ✅ | ❌ (Qt dialog) — use the Home page AI Models card |

**RAM usage estimate on Pi 5 (2 GB):**

| Component | ~RAM |
|-----------|------|
| Pi OS + desktop | ~400 MB |
| Python + FastAPI backend | ~120 MB |
| Chromium browser tab (web UI) | ~300–400 MB |
| OpenCV detection (320×180) | ~80 MB |
| **Total** | **~1 GB** — fits in 2 GB with headroom |

---

## Step 1 — System packages

```bash
sudo apt update && sudo apt install -y \
    ffmpeg \
    python3-pip \
    python3-venv \
    libgl1 \
    libglib2.0-0
```

`ffmpeg` from apt is the critical one — `imageio-ffmpeg` only bundles Windows/macOS/x86_64 Linux binaries, so the Pi always uses the system copy.

---

## Step 2 — Python environment

```bash
cd ~/CCTV-VIDEO-PROCESSOR
python3 -m venv .venv
source .venv/bin/activate
grep -viE '^pyqt6' requirements.txt > /tmp/requirements-pi.txt
pip install -r /tmp/requirements-pi.txt
```

> **Why skip PyQt6?** Its aarch64 wheels on PyPI require glibc ≥ 2.39, but Pi OS
> Bookworm has 2.36 — pip would fail (or try a hopeless source build). The
> launcher detects the missing Qt automatically and runs headless, serving the
> web UI to your browser. If you specifically want the embedded Qt window, the
> only route is Debian's own packages (`sudo apt install python3-pyqt6.qtwebengine`
> with the **system** Python, not a venv) — unsupported, but it works.

---

## Step 3 — Run

```bash
source .venv/bin/activate
python launcher.py
```

The backend starts in a few seconds and the web UI opens in the Pi's browser.

---

## SSH use (no desktop — access the UI from another computer)

The app is already headless on the Pi; to reach the UI from a different machine on
your network, bind the backend to all interfaces. Change one line in `app/config.py`
(source install) or run the backend directly:

```bash
python -c "
import uvicorn
from app.main import create_app
uvicorn.run(create_app(), host='0.0.0.0', port=5151)
"
```

Open `http://<pi-ip-address>:5151` in a browser on your PC. The file browse button
won't work (it needs a local shell), but drag-and-drop into the browser will.

---

## Performance tips for Pi 5

**Detection is the bottleneck.** A 1-hour 1080p video takes roughly:
- Pi 5 (4 GB): ~20–30 minutes (2–3× real-time)
- Pi 5 (2 GB): ~25–35 minutes (slightly slower due to memory pressure)
- PC (i5/Ryzen 5): ~5–10 minutes

Ways to speed it up:

1. **Use 720p or 480p source files.** Detection downscales internally to 320×180 on a 2 GB Pi, so a pre-downscaled input saves disk I/O.

2. **Increase `frame_skip` in the settings.** The detection UI exposes padding/sensitivity; `frame_skip=2` checks every other frame — nearly 2× faster at the cost of potentially missing very short events.

3. **Close other apps** before starting detection. Chromium (WebEngine) can be closed via the tray icon after detection starts — the SSE stream will reconnect.

4. **Export is fast** — it's stream-copy (no re-encoding) by default. A 1-hour source exports in under 2 minutes even on Pi 5.

---

## Temperature display

On Pi 5 the Status page shows CPU temperature. `psutil.sensors_temperatures()` works on Pi OS. If it returns `None`, install the vcgencmd fallback (already handled in `app/utils/system.py` via the `sensors_temperatures` dict lookup for `cpu_thermal`).

---

## Installing YOLO (optional)

```bash
pip install ultralytics
```

The YOLOv8n model (~6 MB) downloads automatically on first use. On Pi 5 with 2 GB, YOLO inference takes ~0.3–0.5 seconds per frame, so a 1-hour video would take many hours — **not recommended on 2 GB Pi**. Use MOG2 mode (the default) for Pi.

---

## Troubleshooting Pi-specific issues

| Problem | Fix |
|---------|-----|
| `ffmpeg: command not found` | `sudo apt install ffmpeg` |
| pip fails installing `PyQt6` | Expected — skip it (see Step 2); the app runs headless without it |
| App starts but no browser opens | Browse to `http://127.0.0.1:5151` manually; check `xdg-utils` is installed (`sudo apt install xdg-utils`) |
| AI captions unavailable | On Pis with < 5 GB RAM this is by design; on an 8 GB Pi, download the models from the Home page AI Models card |
| Detection extremely slow | Normal on Pi — a 1h video takes ~30 min; let it run |
| Export fails with codec error | System FFmpeg might be older than bundled Windows one; try `sudo apt upgrade ffmpeg` |
