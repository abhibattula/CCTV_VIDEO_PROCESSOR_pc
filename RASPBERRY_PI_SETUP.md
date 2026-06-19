# Running on Raspberry Pi 5 (2 GB / 4 GB)

This app runs on Pi 5 with a few system packages installed first.
The Python code is identical — no separate Pi branch needed.

---

## What works / what's different

| Feature | PC (Windows) | Pi 5 (Linux ARM64) |
|---------|-------------|-------------------|
| MOG2 detection | ✅ | ✅ (slower — ~1× real-time) |
| YOLO detection | ✅ | ✅ (`pip install ultralytics`) |
| FFmpeg export | ✅ bundled binary | ✅ uses system `ffmpeg` |
| Web UI (PyQt6 + WebEngine) | ✅ | ✅ but uses ~500 MB RAM |
| System tray | ✅ | ✅ (needs desktop environment) |
| Temperature readout | ❌ (Windows) | ✅ via `vcgencmd` fallback |

**RAM usage estimate on Pi 5 (2 GB):**

| Component | ~RAM |
|-----------|------|
| Pi OS + desktop | ~400 MB |
| Python + FastAPI backend | ~120 MB |
| PyQt6 + Chromium WebEngine | ~500 MB |
| OpenCV detection (320×180) | ~80 MB |
| **Total** | **~1.1 GB** — fits in 2 GB with headroom |

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
pip install -r requirements.txt
```

> **PyQt6-WebEngine on Pi:** The pip wheel for `PyQt6-WebEngine` is available for Linux aarch64 from PyPI since PyQt6 6.6. If pip can't find it, install from the system:
> ```bash
> sudo apt install python3-pyqt6.qtwebengine
> # then use system Python instead of a venv, or:
> pip install PyQt6-WebEngine --extra-index-url https://www.piwheels.org/simple/
> ```

---

## Step 3 — Run

```bash
source .venv/bin/activate
python launcher.py
```

The window opens in about 10 seconds on Pi 5 (Chromium-based WebEngine starts slowly on first launch).

---

## Headless / SSH use (no desktop)

If you're running the Pi headlessly and want to access the UI from another computer, change one line in `app/config.py`:

```python
BACKEND_HOST: str = "0.0.0.0"   # was "127.0.0.1"
```

Then run only the backend (no Qt window):

```bash
python -c "
import uvicorn
from app.main import create_app
uvicorn.run(create_app(), host='0.0.0.0', port=5151)
"
```

Open `http://<pi-ip-address>:5151` in a browser on your PC. The file browse button won't work (it needs the Qt shell), but drag-and-drop via the web browser will. For headless use, add the video path by entering it directly in the browser address bar as a query: after loading the page type the path into the file input.

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
| `PyQt6-WebEngine` wheel not found | Use piwheels: `pip install --extra-index-url https://www.piwheels.org/simple/ PyQt6-WebEngine` |
| Window opens but stays white > 30s | Chromium first-run takes longer on Pi — wait or restart |
| `DISPLAY` environment variable not set | Must run from a desktop session, not raw SSH — use `ssh -X` or VNC |
| Detection extremely slow | Normal on Pi — a 1h video takes ~30 min; let it run |
| Export fails with codec error | System FFmpeg might be older than bundled Windows one; try `sudo apt upgrade ffmpeg` |
