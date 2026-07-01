#!/usr/bin/env bash
# Linux AppImage build entrypoint — runs inside cctv-linux-build container.
# Called automatically as ENTRYPOINT when the container starts.
#
# Environment:
#   APP_VERSION  — semver string (e.g. 1.0.0); passed via -e APP_VERSION=x.y.z
#
# Volume:
#   /output  — bind-mounted to Windows dist/ folder; artifact written here
set -euo pipefail

APP_VERSION="${APP_VERSION:-1.0.0}"
echo "[build] CCTV Video Processor v${APP_VERSION} — Linux x86_64 AppImage"

# Step 1: PyInstaller onedir build
cd /app
echo "[build] Running PyInstaller..."
python -m PyInstaller build/cctv_processor_linux.spec \
    --distpath /app/dist --workpath /tmp/work --noconfirm

# Step 2: Pre-place appimageTool where create_appimage.sh expects it
# (script checks for dist/appimagetool-x86_64.AppImage before downloading)
mkdir -p /app/dist
cp /usr/local/bin/appimageTool /app/dist/appimagetool-x86_64.AppImage

# Step 3: Package as AppImage (writes to /app/dist/CCTV-Video-Processor-{ver}-linux-x86_64.AppImage)
# APPIMAGE_EXTRACT_AND_RUN=1 prevents appimageTool from trying to mount itself
# via FUSE (which fails in Docker without --privileged). It extracts to a tmpdir instead.
echo "[build] Packaging AppImage..."
APP_VERSION="${APP_VERSION}" APPIMAGE_EXTRACT_AND_RUN=1 bash build/linux/create_appimage.sh

# Step 4: Copy to /output with the canonical artifact name
mkdir -p /output
SRC="/app/dist/CCTV-Video-Processor-${APP_VERSION}-linux-x86_64.AppImage"
DEST="/output/CCTV-Processor-${APP_VERSION}-linux-x86_64.AppImage"
cp "${SRC}" "${DEST}"

echo "[build] Done: ${DEST}"
