#!/bin/bash
# Build a signed Mac App Store .pkg for LocalPDF.
#
# Prerequisites (one-time):
#   1. Apple Developer Program enrollment (active).
#   2. In Keychain.app, the following two Distribution certificates installed:
#        - "Apple Distribution: <Name> (TEAM_ID)"
#          OR "3rd Party Mac Developer Application: <Name> (TEAM_ID)"
#        - "3rd Party Mac Developer Installer: <Name> (TEAM_ID)"
#      Create them in https://developer.apple.com → Certificates, IDs & Profiles.
#   3. Mac App Store provisioning profile for bundle ID `ai.localpdf.desktop`
#      downloaded as `embedded.provisionprofile`.
#   4. PyInstaller installed in the venv:  ./venv/bin/pip install pyinstaller
#
# Usage:
#   LOCALPDF_APP_IDENTITY="Apple Distribution: Name (TEAMID)" \
#   LOCALPDF_INSTALLER_IDENTITY="3rd Party Mac Developer Installer: Name (TEAMID)" \
#   LOCALPDF_PROVISIONING_PROFILE=./embedded.provisionprofile \
#   bash scripts/build_mas.sh
#
# Output:
#   dist/LocalPDF.app                       — signed .app bundle
#   dist/LocalPDF-<version>-mas.pkg         — signed .pkg ready for upload
#
# Upload to App Store Connect:
#   open -a Transporter dist/LocalPDF-*-mas.pkg
# or
#   xcrun altool --upload-app --type osx --file dist/LocalPDF-*-mas.pkg \
#                --apiKey <KEY> --apiIssuer <ISSUER>

set -euo pipefail

# ---- Required env vars ------------------------------------------------------
: "${LOCALPDF_APP_IDENTITY:?Set LOCALPDF_APP_IDENTITY (e.g. \"Apple Distribution: Your Name (TEAM_ID)\")}"
: "${LOCALPDF_INSTALLER_IDENTITY:?Set LOCALPDF_INSTALLER_IDENTITY (e.g. \"3rd Party Mac Developer Installer: Your Name (TEAM_ID)\")}"

# ---- Optional env vars ------------------------------------------------------
LOCALPDF_VERSION="${LOCALPDF_VERSION:-1.2.0}"
LOCALPDF_BUNDLE_ID="${LOCALPDF_BUNDLE_ID:-ai.localpdf.desktop}"
LOCALPDF_TARGET_ARCH="${LOCALPDF_TARGET_ARCH:-universal2}"
LOCALPDF_PROVISIONING_PROFILE="${LOCALPDF_PROVISIONING_PROFILE:-}"

# ---- Paths ------------------------------------------------------------------
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP="dist/LocalPDF.app"
PKG="dist/LocalPDF-${LOCALPDF_VERSION}-mas.pkg"
ENTITLEMENTS="$ROOT/assets/entitlements/mas.entitlements"
PYINSTALLER="${PYINSTALLER:-./venv/bin/pyinstaller}"

if [ ! -f "$ENTITLEMENTS" ]; then
    echo "ERROR: entitlements file not found: $ENTITLEMENTS"
    exit 1
fi

if [ ! -x "$PYINSTALLER" ]; then
    # Fall back to system pyinstaller if venv version missing.
    if command -v pyinstaller >/dev/null 2>&1; then
        PYINSTALLER=pyinstaller
    else
        echo "ERROR: pyinstaller not found at $PYINSTALLER and not on PATH."
        echo "       Install it:  ./venv/bin/pip install pyinstaller"
        exit 1
    fi
fi

echo "============================================================"
echo "LocalPDF — Mac App Store build"
echo "------------------------------------------------------------"
echo "  Version              : $LOCALPDF_VERSION"
echo "  Bundle ID            : $LOCALPDF_BUNDLE_ID"
echo "  Target arch          : $LOCALPDF_TARGET_ARCH"
echo "  App identity         : $LOCALPDF_APP_IDENTITY"
echo "  Installer identity   : $LOCALPDF_INSTALLER_IDENTITY"
echo "  Provisioning profile : ${LOCALPDF_PROVISIONING_PROFILE:-<none>}"
echo "============================================================"

# ---- 1. Clean previous build -----------------------------------------------
echo ""
echo "==> Cleaning previous build artifacts..."
rm -rf build dist

# ---- 2. Run PyInstaller -----------------------------------------------------
echo ""
echo "==> Building app bundle with PyInstaller..."
export LOCALPDF_VERSION LOCALPDF_BUNDLE_ID LOCALPDF_TARGET_ARCH
"$PYINSTALLER" LocalPDF.spec --clean --noconfirm

if [ ! -d "$APP" ]; then
    echo "ERROR: PyInstaller did not produce $APP"
    exit 1
fi

# ---- 3. Embed provisioning profile ------------------------------------------
if [ -n "$LOCALPDF_PROVISIONING_PROFILE" ]; then
    if [ ! -f "$LOCALPDF_PROVISIONING_PROFILE" ]; then
        echo "ERROR: provisioning profile not found: $LOCALPDF_PROVISIONING_PROFILE"
        exit 1
    fi
    echo ""
    echo "==> Embedding provisioning profile..."
    cp "$LOCALPDF_PROVISIONING_PROFILE" "$APP/Contents/embedded.provisionprofile"
else
    echo ""
    echo "WARNING: No provisioning profile embedded. Submission to App Store"
    echo "         Connect requires one — set LOCALPDF_PROVISIONING_PROFILE."
fi

# ---- 4. Sign every Mach-O binary inside the bundle --------------------------
# Apple's rule: sign nested code before the outer container. We do this in
# two phases:
#   Phase 1 — loose Mach-O files (dylibs, .so, executables). Use depth-first
#             traversal. Skip the .app main executable (handled by signing
#             the .app), and skip files immediately inside a *.framework
#             directory (those are framework main binaries — codesign errors
#             with "bundle format is ambiguous" if signed by file path).
#   Phase 2 — sign each *.framework directory as a bundle, deepest first.
echo ""
echo "==> Signing nested binaries (phase 1)..."
MAIN_EXEC="$APP/Contents/MacOS/LocalPDF"
SIGN_COUNT=0
while IFS= read -r -d '' target; do
    [ "$target" = "$MAIN_EXEC" ] && continue
    parent_base=$(basename "$(dirname "$target")")
    if [[ "$parent_base" == *.framework ]]; then
        continue
    fi
    if file "$target" 2>/dev/null | grep -q "Mach-O"; then
        codesign --force --options runtime --timestamp \
            --sign "$LOCALPDF_APP_IDENTITY" \
            --entitlements "$ENTITLEMENTS" \
            "$target" >/dev/null
        SIGN_COUNT=$((SIGN_COUNT + 1))
    fi
done < <(find "$APP/Contents" -depth -type f -print0)
echo "    Signed $SIGN_COUNT loose Mach-O files."

echo ""
echo "==> Signing frameworks (phase 2)..."
# Pass --identifier matching the framework's own CFBundleIdentifier — App
# Store Connect's validator rejects packages where signature identifier
# doesn't match the bundle identifier.
FW_COUNT=0
while IFS= read -r -d '' fw; do
    fw_name=$(basename "$fw" .framework)
    fw_id=""
    for candidate in \
        "$fw/Versions/Current/Resources/Info.plist" \
        "$fw/Resources/Info.plist" \
        "$fw/Contents/Info.plist"; do
        if [ -f "$candidate" ]; then
            id=$(/usr/libexec/PlistBuddy -c "Print :CFBundleIdentifier" "$candidate" 2>/dev/null || echo "")
            if [ -n "$id" ]; then
                fw_id="$id"
                break
            fi
        fi
    done
    if [ -z "$fw_id" ]; then
        fw_id="ai.localpdf.framework.${fw_name}"
    fi
    codesign --force --options runtime --timestamp \
        --sign "$LOCALPDF_APP_IDENTITY" \
        --entitlements "$ENTITLEMENTS" \
        --identifier "$fw_id" \
        "$fw" >/dev/null
    FW_COUNT=$((FW_COUNT + 1))
done < <(find "$APP/Contents" -depth -name "*.framework" -type d -print0)
echo "    Signed $FW_COUNT frameworks."

# ---- 5. Sign the outer .app ------------------------------------------------
echo ""
echo "==> Signing $APP..."
codesign --force --options runtime --timestamp \
    --sign "$LOCALPDF_APP_IDENTITY" \
    --entitlements "$ENTITLEMENTS" \
    "$APP"

# ---- 6. Verify signing ------------------------------------------------------
echo ""
echo "==> Verifying app signature..."
codesign --verify --deep --strict --verbose=2 "$APP"
codesign --display --entitlements - "$APP" | head -40

# ---- 7. Build the .pkg ------------------------------------------------------
echo ""
echo "==> Building signed .pkg..."
productbuild \
    --component "$APP" /Applications \
    --sign "$LOCALPDF_INSTALLER_IDENTITY" \
    "$PKG"

# ---- 8. Verify .pkg --------------------------------------------------------
echo ""
echo "==> Verifying .pkg signature..."
pkgutil --check-signature "$PKG"

# ---- Done ------------------------------------------------------------------
echo ""
echo "============================================================"
echo "Build complete."
echo "  App: $APP"
echo "  Pkg: $PKG"
echo ""
echo "Next: upload to App Store Connect."
echo "  - Transporter (GUI):   open -a Transporter \"$PKG\""
echo "  - altool (CLI):"
echo "      xcrun altool --upload-app --type osx --file \"$PKG\" \\"
echo "                   --apiKey <KEY_ID> --apiIssuer <ISSUER_ID>"
echo "============================================================"
