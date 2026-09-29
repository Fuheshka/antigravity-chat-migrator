#!/usr/bin/env bash
# Antigravity Chat Migrator - macOS Build & Packaging Pipeline
# Builds standalone executable and packages into Apple HIG-compliant DMG disk image.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

ARCH="$(uname -m)"
CLEAN=0
BUILD_DMG=1
PYTHON_BIN=""

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --arch <arm64|x86_64|universal2>  Target architecture (default: ${ARCH})
  --clean                           Clean build artifacts before building
  --no-dmg                          Build binary only, skip DMG packaging
  -h, --help                        Show this help message
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --arch)
            ARCH="$2"
            shift 2
            ;;
        --clean)
            CLEAN=1
            shift
            ;;
        --no-dmg)
            BUILD_DMG=0
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            ;;
    esac
done

echo "============================================================"
echo " Antigravity Chat Migrator - macOS Build Pipeline"
echo " Target Architecture: ${ARCH}"
echo "============================================================"

# Detect Python environment
if [ -f "${REPO_ROOT}/.venv/bin/python" ]; then
    PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "Error: Python 3 not found. Please activate virtualenv or install python3." >&2
    exit 1
fi

echo "Using Python: ${PYTHON_BIN} ($(${PYTHON_BIN} --version))"

# Check for PyInstaller
if ! ${PYTHON_BIN} -c "import PyInstaller" &>/dev/null; then
    echo "PyInstaller not found. Installing..."
    if command -v uv &>/dev/null; then
        uv pip install pyinstaller
    else
        ${PYTHON_BIN} -m pip install pyinstaller
    fi
fi

# Clean previous builds if requested
if [ "${CLEAN}" -eq 1 ]; then
    echo "--> Cleaning previous build artifacts..."
    rm -rf "${REPO_ROOT}/build/macos" "${REPO_ROOT}/dist/macos"
fi

mkdir -p "${REPO_ROOT}/dist/macos"
mkdir -p "${REPO_ROOT}/build/macos"
mkdir -p "${REPO_ROOT}/packaging/assets"

# 1. Ensure ICNS and Background Assets are built
if [ ! -f "${REPO_ROOT}/packaging/assets/AppIcon.icns" ]; then
    echo "--> Compiling AppIcon.icns..."
    ${PYTHON_BIN} "${REPO_ROOT}/packaging/macos/generate_icns.py"
fi

echo "--> Generating Retina multi-resolution TIFF background..."
${PYTHON_BIN} "${REPO_ROOT}/packaging/macos/build_dmg_background.py"

# 2. Run PyInstaller compilation
echo "--> Compiling standalone binary with PyInstaller..."
PYI_FLAGS=(
    --distpath "${REPO_ROOT}/dist/macos"
    --workpath "${REPO_ROOT}/build/macos"
    --noconfirm
)

if [ "${ARCH}" != "$(uname -m)" ]; then
    PYI_FLAGS+=(--target-arch "${ARCH}")
fi

${PYTHON_BIN} -m PyInstaller "${PYI_FLAGS[@]}" "${REPO_ROOT}/packaging/macos/migrator.spec"

BIN_PATH="${REPO_ROOT}/dist/macos/agy-migrator"
if [ ! -f "${BIN_PATH}" ]; then
    echo "Error: Binary was not created at ${BIN_PATH}" >&2
    exit 1
fi

chmod +x "${BIN_PATH}"

# Verify architecture
echo "--> Binary compiled:"
file "${BIN_PATH}"

# Ad-hoc sign standalone binary
echo "--> Applying ad-hoc signature to standalone binary..."
codesign --force --deep -s - "${BIN_PATH}"

# 3. Assemble macOS Application Bundle
APP_NAME="Antigravity Chat Migrator"
APP_BUNDLE="${REPO_ROOT}/dist/macos/${APP_NAME}.app"
echo "--> Assembling Application Bundle: ${APP_BUNDLE}..."

rm -rf "${APP_BUNDLE}"
mkdir -p "${APP_BUNDLE}/Contents/MacOS"
mkdir -p "${APP_BUNDLE}/Contents/Resources"

# Copy binary to bundle
cp "${BIN_PATH}" "${APP_BUNDLE}/Contents/MacOS/agy-migrator"
chmod +x "${APP_BUNDLE}/Contents/MacOS/agy-migrator"

# Copy Icon
if [ -f "${REPO_ROOT}/packaging/assets/AppIcon.icns" ]; then
    cp "${REPO_ROOT}/packaging/assets/AppIcon.icns" "${APP_BUNDLE}/Contents/Resources/AppIcon.icns"
fi

# Create Info.plist
cat > "${APP_BUNDLE}/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIdentifier</key>
    <string>com.fuheshka.antigravity-chat-migrator</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleVersion</key>
    <string>0.1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# Create GUI launcher script (opens Terminal for interactive audit or executes command)
cat > "${APP_BUNDLE}/Contents/MacOS/launcher" <<'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="$DIR/agy-migrator"

if [ -t 0 ]; then
    exec "$BIN" "$@"
else
    # Launched from Finder GUI - open Terminal with interactive audit
    osascript -e "tell application \"Terminal\" to do script \"\\\"$BIN\\\" audit; echo ''; echo 'Run \\\"agy-migrator --help\\\" for full command list.'; echo 'Press Enter to exit...'; read\" activate"
fi
EOF
chmod +x "${APP_BUNDLE}/Contents/MacOS/launcher"

# Clean extended attributes and sign app bundle
xattr -cr "${APP_BUNDLE}"
echo "--> Signing Application Bundle..."
codesign --force --deep -s - "${APP_BUNDLE}"

# 4. Create DMG if requested
if [ "${BUILD_DMG}" -eq 1 ]; then
    echo "--> Creating DMG installer image..."
    ${PYTHON_BIN} "${REPO_ROOT}/packaging/macos/create_dmg.py" \
        --app "${APP_BUNDLE}" \
        --output "${REPO_ROOT}/dist/macos/Antigravity-Chat-Migrator-macOS.dmg" \
        --volname "${APP_NAME}" \
        --icon "${REPO_ROOT}/packaging/assets/AppIcon.icns" \
        --background "${REPO_ROOT}/packaging/assets/dmg_background.tiff"
fi

echo ""
echo "============================================================"
echo "🎉 macOS Build Pipeline Finished Successfully!"
echo "Standalone CLI Binary:  ${BIN_PATH}"
echo "Application Bundle:     ${APP_BUNDLE}"
if [ "${BUILD_DMG}" -eq 1 ]; then
    echo "Installer Disk Image:   ${REPO_ROOT}/dist/macos/Antigravity-Chat-Migrator-macOS.dmg"
fi
echo "============================================================"
ls -lh "${REPO_ROOT}/dist/macos"
