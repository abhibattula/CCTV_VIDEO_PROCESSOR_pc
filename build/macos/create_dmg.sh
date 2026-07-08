#!/usr/bin/env bash
# Build a macOS DMG containing the PyInstaller app bundle.
# Performs ad-hoc code signing (codesign --sign -) so macOS Gatekeeper
# can be bypassed with right-click → Open.
#
# Usage (from project root):
#   APP_VERSION=1.0.0 bash build/macos/create_dmg.sh
#
# Prerequisites:
#   - PyInstaller has been run: pyinstaller build/cctv_processor_macos.spec
#   - xattr, codesign, hdiutil available (macOS CI / dev machine)
set -euo pipefail

APP_VERSION="${APP_VERSION:-dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
APP_BUNDLE="${PROJECT_ROOT}/dist/CCTV Video Processor.app"
DMG_NAME="CCTV-Video-Processor-${APP_VERSION}-macos.dmg"
STAGING_DIR="/tmp/cctv_dmg_staging"

echo "[dmg] Checking app bundle…"
if [ ! -d "${APP_BUNDLE}" ]; then
  echo "ERROR: App bundle not found at: ${APP_BUNDLE}"
  echo "Run: pyinstaller build/cctv_processor_macos.spec"
  exit 1
fi

echo "[dmg] Removing quarantine attributes…"
xattr -cr "${APP_BUNDLE}" || true

echo "[dmg] Ad-hoc code signing (no Apple Developer account needed)…"
codesign --force --deep --sign - "${APP_BUNDLE}"

echo "[dmg] Verifying signature…"
codesign --verify --deep --strict "${APP_BUNDLE}" && echo "  Signature OK"

echo "[dmg] Creating staging directory…"
rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}"
cp -R "${APP_BUNDLE}" "${STAGING_DIR}/"

# Create a symlink to /Applications for drag-install UX
ln -s /Applications "${STAGING_DIR}/Applications"

# Add a README explaining Gatekeeper bypass
cat > "${STAGING_DIR}/README.txt" <<'READMEOF'
CCTV Video Processor — macOS Installation

1. Drag "CCTV Video Processor.app" to Applications.
2. First launch: right-click the app → Open → Open (to bypass Gatekeeper).
   Only required once; subsequent launches work normally.
3. The app downloads AI model weights on first run (~1 GB).
READMEOF

echo "[dmg] Building DMG…"
hdiutil create \
  -volname "CCTV Video Processor ${APP_VERSION}" \
  -srcfolder "${STAGING_DIR}" \
  -ov \
  -format UDZO \
  -o "${PROJECT_ROOT}/dist/${DMG_NAME}"

echo "[dmg] Cleaning up staging…"
rm -rf "${STAGING_DIR}"

echo "[dmg] Done: dist/${DMG_NAME}"
