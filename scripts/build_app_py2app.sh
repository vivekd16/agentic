#!/bin/bash
set -e

# Build script for Agentic macOS application using py2app in alias mode
echo "=== Building Agentic macOS App with py2app ==="

# Create directories
mkdir -p runtime resources/dashboard resources/examples



echo "Building dashboard..."
if [ -d "src/agentic/dashboard" ]; then
    cd src/agentic/dashboard
    npm install
    npm run build
    
    # Create dashboard directory in resources
    mkdir -p ../../resources/dashboard
    
    # Copy all exported files to resources/dashboard
    cp -r out/* ../../resources/dashboard/
    
    cd ../../..
    pwd
    # Create symlink for compatibility with older code
    # First make sure the directory exists
    mkdir -p resources/dashboard/_next/static/chunks
    
    # Find the main JS file
    MAIN_JS_FILE=$(find resources/dashboard/_next/static/chunks -name "main-*.js" | head -n 1)
    
    if [ -n "$MAIN_JS_FILE" ]; then
        # Get just the filename without the path
        MAIN_JS_BASENAME=$(basename "$MAIN_JS_FILE")
        echo "Found main JS file: $MAIN_JS_BASENAME"
        
        # Create the symlink in the correct directory
        cd resources/dashboard/_next/static/chunks
        ln -sf "$MAIN_JS_BASENAME" "main.js"
        echo "Created symlink: main.js -> $MAIN_JS_BASENAME"
        cd ../../../../..
    else
        echo "Warning: Could not find main-*.js file in resources/dashboard/_next/static/chunks"
    fi
fi


pwd

# Copy examples

echo "Copying examples..."
cp examples/*.py resources/examples/

echo "Examples copied to resources/examples:"
ls -l resources/examples

# Copy Qt plugins
echo "Copying Qt plugins..."
#QT_PLUGINS_PATH=$(uv run python -c "from PyQt5.QtCore import QLibraryInfo; print(QLibraryInfo.location(QLibraryInfo.PluginsPath))")
QT_PLUGINS_PATH=$(uv run --active python -c "from PyQt5.QtCore import QLibraryInfo; print(QLibraryInfo.location(QLibraryInfo.PluginsPath))")

if [ -n "$QT_PLUGINS_PATH" ]; then
    mkdir -p resources/plugins/platforms
    cp "$QT_PLUGINS_PATH/platforms/libqcocoa.dylib" resources/plugins/platforms/
fi

echo "Cleaning previous build artifacts..."
rm -rf build dist

# Build app (now using the permanent setup.py file)
echo "Building app ..."
uv run --active python setup.py py2app

# === Copying standard library modules that py2app skips ===
BUNDLED_PYTHON="dist/Agentic.app/Contents/Resources/lib/python3.12"

echo "Copying standard library modules that py2app skips..."

HTML_SRC_DIR="/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/html"
HTML_DST_DIR="$BUNDLED_PYTHON/html"

if [ -d "$HTML_SRC_DIR" ]; then
    echo "Copying html module..."
    mkdir -p "$HTML_DST_DIR"
    cp -R "$HTML_SRC_DIR/"* "$HTML_DST_DIR/"
else
    echo "WARNING: html module not found at $HTML_SRC_DIR"
fi

SOCKETSERVER_SRC_FILE="/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/socketserver.py"
if [ -f "$SOCKETSERVER_SRC_FILE" ]; then
    echo "Copying socketserver module..."
    cp "$SOCKETSERVER_SRC_FILE" "$BUNDLED_PYTHON/"
else
    echo "WARNING: socketserver.py not found at $SOCKETSERVER_SRC_FILE"
fi


echo "Copying Qt plugins to PyQt5 location..."
mkdir -p "dist/Agentic.app/Contents/Resources/lib/python3.11/PyQt5/Qt5/plugins/platforms"
cp "$QT_PLUGINS_PATH/platforms/libqcocoa.dylib" "dist/Agentic.app/Contents/Resources/lib/python3.11/PyQt5/Qt5/plugins/platforms/"

# Now manually copy the resources into the app bundle
echo "Copying resources into app bundle..."
mkdir -p "dist/Agentic.app/Contents/Resources/resources"
cp -r resources/* "dist/Agentic.app/Contents/Resources/resources/"
mkdir -p "dist/Agentic.app/Contents/Resources/plugins"
cp -r resources/plugins/* "dist/Agentic.app/Contents/Resources/plugins/"




# Create runtime directory in app bundle
mkdir -p "dist/Agentic.app/Contents/Resources/runtime"

# Patch __boot__.py to fix sys.path issue
BOOT_PATH="dist/Agentic.app/Contents/Resources/__boot__.py"
if [ -f "$BOOT_PATH" ]; then
    sed -i '' '1i\
import os, sys; bundle_lib = os.path.join(os.path.dirname(__file__), "lib", "python3.12"); site_pkgs = os.path.join(bundle_lib, "site-packages"); sys.path = [p for p in sys.path if "site-packages.zip" not in p]; \
sys.path.insert(0, site_pkgs) if os.path.isdir(site_pkgs) else sys.path.insert(0, bundle_lib)
' "$BOOT_PATH"
    echo "Patched __boot__.py to use bundled libraries correctly."
else
    echo "Error: __boot__.py not found in the bundle."
    exit 1
fi

SITE_PACKAGES="dist/Agentic.app/Contents/Resources/lib/python3.12/site-packages"
if [ ! -d "$SITE_PACKAGES/agentic" ]; then
    echo "Copying agentic module to site-packages..."
    mkdir -p "$SITE_PACKAGES"
    cp -r "src/agentic" "$SITE_PACKAGES/"
fi

echo "Final location check:"
ls -l dist/Agentic.app/Contents/Resources/resources/examples || echo "Missing examples in final app bundle"

echo "=== Build complete ==="
echo "Application is available at: dist/Agentic.app"
