#!/usr/bin/env bash
# Raspberry Pi ARM64 .deb build entrypoint — runs inside cctv-pi-build container.
# Called automatically as ENTRYPOINT when the container starts.
#
# Environment:
#   APP_VERSION  — semver string (e.g. 1.0.0); passed via -e APP_VERSION=x.y.z
#
# Volume:
#   /output  — bind-mounted to Windows dist/ folder; artifact written here
set -euo pipefail

APP_VERSION="${APP_VERSION:-1.0.0}"
echo "[build] CCTV Video Processor v${APP_VERSION} — Raspberry Pi ARM64 .deb"

# Step 1: PyInstaller onedir build (reuses linux spec — supports both x86_64 and arm64)
cd /app
echo "[build] Running PyInstaller (ARM64)..."
python -m PyInstaller build/cctv_processor_linux.spec \
    --distpath /app/dist --workpath /tmp/work --noconfirm

# Step 2: Package as .deb (writes to /app/dist/cctv-video-processor_{ver}_arm64.deb)
echo "[build] Packaging .deb..."
APP_VERSION="${APP_VERSION}" bash build/pi/create_deb.sh

# Step 3: Copy to /output with canonical artifact name
mkdir -p /output
SRC="/app/dist/cctv-video-processor_${APP_VERSION}_arm64.deb"
DEST="/output/CCTV-Processor-${APP_VERSION}-pi-arm64.deb"
cp "${SRC}" "${DEST}"

echo "[build] Done: ${DEST}"
