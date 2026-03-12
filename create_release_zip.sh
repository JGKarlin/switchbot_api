#!/bin/bash
# Create a release zip for Home Assistant custom_components installation.
# The zip contains switchbot_api/ with all integration files.
# Run from the repository root (the folder containing this script).

set -e
cd "$(dirname "$0")"

OUTPUT_ZIP="switchbot_api.zip"
TEMP_DIR="switchbot_api"

echo "Creating $OUTPUT_ZIP for Home Assistant custom_components..."

# Clean previous build
rm -rf "$TEMP_DIR" "$OUTPUT_ZIP"
mkdir -p "$TEMP_DIR"

# Copy integration files (exclude scripts and docs)
cp __init__.py config_flow.py const.py sensor.py services.py api.py manifest.json services.yaml icons.json "$TEMP_DIR/" 2>/dev/null || true
cp -r translations "$TEMP_DIR/" 2>/dev/null || true
cp -r brand "$TEMP_DIR/" 2>/dev/null || true
cp icon.png "$TEMP_DIR/" 2>/dev/null || true

# Create zip
zip -r "$OUTPUT_ZIP" "$TEMP_DIR" -x "*.git*" -x "*__pycache__*" -x "*.pyc"

# Cleanup
rm -rf "$TEMP_DIR"

echo "Done. Install by extracting $OUTPUT_ZIP and copying the switchbot_api folder to config/custom_components/"
