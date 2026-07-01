#!/usr/bin/env bash
# Build a Debian/ARM64 .deb package for Raspberry Pi 4/5.
# Wraps the PyInstaller --onedir output from the Pi QEMU build.
#
# Usage (from project root, on aarch64 Linux):
#   APP_VERSION=1.0.0 bash build/pi/create_deb.sh
#
# Prerequisite:
#   pyinstaller build/cctv_processor_linux.spec   (run inside QEMU ARM64)
set -euo pipefail

APP_VERSION="${APP_VERSION:-dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist/CCTV-Video-Processor"
PKG_DIR="/tmp/cctv_deb_pkg"
DEB_NAME="cctv-video-processor_${APP_VERSION}_arm64.deb"

echo "[deb] Checking PyInstaller output…"
if [ ! -d "${DIST_DIR}" ]; then
  echo "ERROR: dist/CCTV-Video-Processor not found. Run PyInstaller first."
  exit 1
fi

echo "[deb] Preparing package structure…"
rm -rf "${PKG_DIR}"
mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/opt/cctv-video-processor"
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/local/bin"

# Copy PyInstaller output
cp -R "${DIST_DIR}/." "${PKG_DIR}/opt/cctv-video-processor/"

# Control file
cat > "${PKG_DIR}/DEBIAN/control" <<CTRLEOF
Package: cctv-video-processor
Version: ${APP_VERSION}
Architecture: arm64
Maintainer: CCTV Video Processor Project
Description: AI-powered CCTV video analysis for Raspberry Pi
 Processes CCTV footage with YOLOv8 object detection and optional
 Florence-2 AI captions (requires 5 GB+ RAM). Includes a web UI.
Depends: libgl1, libglib2.0-0
Homepage: https://github.com/your-repo/cctv-video-processor
CTRLEOF

# Post-install script: create a launcher symlink
cat > "${PKG_DIR}/DEBIAN/postinst" <<'POSTEOF'
#!/bin/bash
set -e
ln -sf /opt/cctv-video-processor/CCTV-Video-Processor /usr/local/bin/cctv-video-processor
echo "CCTV Video Processor installed. Run: cctv-video-processor"
POSTEOF
chmod 755 "${PKG_DIR}/DEBIAN/postinst"

# Pre-remove script: remove symlink
cat > "${PKG_DIR}/DEBIAN/prerm" <<'PRERMEOF'
#!/bin/bash
set -e
rm -f /usr/local/bin/cctv-video-processor
# NOTE: ~/.cctv_processor (user data, model weights) is intentionally NOT removed.
PRERMEOF
chmod 755 "${PKG_DIR}/DEBIAN/prerm"

# Desktop entry
cat > "${PKG_DIR}/usr/share/applications/cctv-video-processor.desktop" <<'DESKEOF'
[Desktop Entry]
Name=CCTV Video Processor
Comment=AI-powered CCTV video analysis
Exec=/opt/cctv-video-processor/CCTV-Video-Processor
Icon=utilities-terminal
Type=Application
Categories=Video;Science;
Terminal=false
DESKEOF

echo "[deb] Building .deb…"
dpkg-deb --build --root-owner-group "${PKG_DIR}" "${PROJECT_ROOT}/dist/${DEB_NAME}"

echo "[deb] Verifying package…"
dpkg-deb --info "${PROJECT_ROOT}/dist/${DEB_NAME}"

echo "[deb] Done: dist/${DEB_NAME}"
