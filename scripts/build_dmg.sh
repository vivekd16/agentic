#!/bin/bash
set -e

# build_dmg.sh - Creates DMG installer for Agentic.app
# This script should be run after build_app_py2app.sh has created the app bundle

echo "=== Creating DMG for Agentic.app ==="

# Check if Agentic.app exists
if [ ! -d "dist/Agentic.app" ]; then
    echo "Error: dist/Agentic.app not found!"
    echo "Please run build_app_py2app.sh first to create the app bundle."
    exit 1
fi

# Get the size of the app bundle
APP_SIZE=$(du -sm dist/Agentic.app | cut -f1)
echo "App bundle size: ${APP_SIZE}MB"

# Calculate DMG size with 20% buffer
DMG_SIZE=$((APP_SIZE + APP_SIZE / 5))
echo "Setting DMG size to ${DMG_SIZE}MB"

# Clean up any previous temp directory
rm -rf /tmp/agentic-dmg

# Create a fresh directory
mkdir -p /tmp/agentic-dmg

# Copy Agentic.app to the temporary directory
echo "Copying Agentic.app to staging area..."
cp -R dist/Agentic.app /tmp/agentic-dmg/

# Create symlink to Applications folder
echo "Creating Applications symlink..."
ln -s /Applications /tmp/agentic-dmg/

# Create the DMG
echo "Creating DMG..."
hdiutil create -volname "Agentic Installer" \
    -srcfolder /tmp/agentic-dmg \
    -ov -format UDZO \
    -size ${DMG_SIZE}m \
    dist/Agentic.dmg

# Clean up
rm -rf /tmp/agentic-dmg

echo "=== DMG creation complete ==="
echo "Installer available at: dist/Agentic.dmg"
echo "Size: $(du -h dist/Agentic.dmg | cut -f1)"
