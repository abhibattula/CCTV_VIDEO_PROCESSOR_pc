#!/usr/bin/env bash
# Build a Linux AppImage from the PyInstaller --onedir output.
# Requires appimagetool (downloaded automatically if not found).
#
# Usage (from project root, on Linux x86_64):
#   APP_VERSION=1.0.0 bash build/linux/create_appimage.sh
#
# Prerequisite:
#   pyinstaller build/cctv_processor_linux.spec
set -euo pipefail

APP_VERSION="${APP_VERSION:-dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DIST_DIR="${PROJECT_ROOT}/dist/CCTV-Video-Processor"
APPDIR="${PROJECT_ROOT}/dist/AppDir"
OUTPUT_NAME="CCTV-Video-Processor-${APP_VERSION}-linux-x86_64.AppImage"

echo "[appimage] Checking PyInstaller output…"
if [ ! -d "${DIST_DIR}" ]; then
  echo "ERROR: dist/CCTV-Video-Processor not found. Run PyInstaller first."
  exit 1
fi

echo "[appimage] Preparing AppDir…"
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# Copy entire PyInstaller onedir output
cp -R "${DIST_DIR}/." "${APPDIR}/usr/bin/"

# Desktop entry
cat > "${APPDIR}/usr/share/applications/cctv-video-processor.desktop" <<'DESKEOF'
[Desktop Entry]
Name=CCTV Video Processor
Comment=AI-powered CCTV video analysis
Exec=CCTV-Video-Processor
Icon=cctv-video-processor
Type=Application
Categories=Video;Science;
Terminal=false
DESKEOF

# Copy .desktop to AppDir root (required by AppImage spec)
cp "${APPDIR}/usr/share/applications/cctv-video-processor.desktop" "${APPDIR}/"

# Placeholder icon (replace with real icon if available)
if [ -f "${PROJECT_ROOT}/static/favicon.png" ]; then
  cp "${PROJECT_ROOT}/static/favicon.png" \
     "${APPDIR}/usr/share/icons/hicolor/256x256/apps/cctv-video-processor.png"
else
  # Create a 1x1 pixel placeholder PNG
  printf '\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82' \
    > "${APPDIR}/usr/share/icons/hicolor/256x256/apps/cctv-video-processor.png"
fi
# appimagetool refuses to build unless the icon named by the .desktop file's
# Icon= key also exists at the AppDir root; .DirIcon is the thumbnail.
cp "${APPDIR}/usr/share/icons/hicolor/256x256/apps/cctv-video-processor.png" \
   "${APPDIR}/cctv-video-processor.png"
cp "${APPDIR}/usr/share/icons/hicolor/256x256/apps/cctv-video-processor.png" \
   "${APPDIR}/.DirIcon"

# AppRun entry point
cat > "${APPDIR}/AppRun" <<'APPRUNEOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/CCTV-Video-Processor" "$@"
APPRUNEOF
chmod +x "${APPDIR}/AppRun"

# Download appimagetool if not present. The maintained build lives in
# AppImage/appimagetool; AppImage/AppImageKit hosts an obsolete 2023 build
# kept only as a fallback mirror.
APPIMAGETOOL="${PROJECT_ROOT}/dist/appimagetool-x86_64.AppImage"
if [ ! -f "${APPIMAGETOOL}" ]; then
  echo "[appimage] Downloading appimagetool…"
  curl -fsSL -o "${APPIMAGETOOL}" \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage" \
  || curl -fsSL -o "${APPIMAGETOOL}" \
    "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
  chmod +x "${APPIMAGETOOL}"
fi

echo "[appimage] Building AppImage…"
# APPIMAGE_EXTRACT_AND_RUN=1: appimagetool is itself an AppImage and needs
# libfuse2 to mount; CI runners and Docker containers don't have FUSE.
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "${APPIMAGETOOL}" "${APPDIR}" "${PROJECT_ROOT}/dist/${OUTPUT_NAME}"

echo "[appimage] Done: dist/${OUTPUT_NAME}"
