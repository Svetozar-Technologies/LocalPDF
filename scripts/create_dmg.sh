#!/bin/bash
# Create a DMG installer for LocalPDF
set -e

APP_NAME="LocalPDF"
DMG_NAME="LocalPDF-1.1.0-macOS"
DIST_DIR="$(cd "$(dirname "$0")/.." && pwd)/dist"
APP_PATH="${DIST_DIR}/${APP_NAME}.app"
DMG_PATH="${DIST_DIR}/${DMG_NAME}.dmg"
STAGING_DIR="${DIST_DIR}/dmg_staging"

echo "=== Creating DMG for ${APP_NAME} ==="

# Verify .app exists
if [ ! -d "${APP_PATH}" ]; then
    echo "ERROR: ${APP_PATH} not found. Build the app first."
    exit 1
fi

# Clean up previous artifacts
rm -f "${DMG_PATH}"
rm -rf "${STAGING_DIR}"

# Create staging directory with app + Applications alias
echo "Setting up staging directory..."
mkdir -p "${STAGING_DIR}"
cp -R "${APP_PATH}" "${STAGING_DIR}/"
ln -s /Applications "${STAGING_DIR}/Applications"

# Copy volume icon
ICNS_PATH="$(cd "$(dirname "$0")/.." && pwd)/assets/icon.icns"
if [ -f "${ICNS_PATH}" ]; then
    cp "${ICNS_PATH}" "${STAGING_DIR}/.VolumeIcon.icns"
fi

APP_SIZE_KB=$(du -sk "${APP_PATH}" | cut -f1)
echo "App size: $((APP_SIZE_KB / 1024)) MB"

# Create compressed DMG directly from staging folder
echo "Creating compressed DMG..."
hdiutil create \
    -volname "${APP_NAME}" \
    -srcfolder "${STAGING_DIR}" \
    -ov \
    -format UDZO \
    -imagekey zlib-level=9 \
    "${DMG_PATH}"

# Clean up staging
rm -rf "${STAGING_DIR}"

# Show result
DMG_SIZE=$(du -sh "${DMG_PATH}" | cut -f1)
echo ""
echo "=== DMG created successfully ==="
echo "Path: ${DMG_PATH}"
echo "Size: ${DMG_SIZE}"
