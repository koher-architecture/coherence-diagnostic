#!/bin/bash

# make-deploy-tar.sh
# Creates a CapRover deployment tarball for Coherence Diagnostic

set -e

APP_NAME="coherence-diagnostic"
TMP_DIR="/tmp/${APP_NAME}_deploy_$$"
TAR_FILE="${APP_NAME}.tar"

# Clean up temp dir on exit
trap "rm -rf $TMP_DIR" EXIT

mkdir -p "$TMP_DIR"

echo "[DEBUG] Creating deployment tarball for $APP_NAME"

# Files to include
INCLUDE_FILES=(
    captain-definition
    Dockerfile
    README.md
)

# Directories to include
INCLUDE_DIRS=(
    backend
    frontend
    src
    models
)

for item in "${INCLUDE_FILES[@]}"; do
    if [[ -e "$item" ]]; then
        echo "[DEBUG] Copying $item"
        rsync -a "$item" "$TMP_DIR/"
    else
        echo "[WARNING] $item not found! Skipping."
    fi
done

for dir in "${INCLUDE_DIRS[@]}"; do
    if [[ -d "$dir" ]]; then
        echo "[DEBUG] Copying directory $dir/"
        rsync -a "$dir" "$TMP_DIR/"
    else
        echo "[WARNING] Directory $dir/ not found! Skipping."
    fi
done

echo "[DEBUG] Contents of $TMP_DIR:"
ls -la "$TMP_DIR"

# Create the tar file
TAR_PATH="$(pwd)/$TAR_FILE"
echo "[DEBUG] Creating tar file at $TAR_PATH"
tar -cf "$TAR_PATH" -C "$TMP_DIR" . || { echo "[ERROR] tar command failed"; exit 2; }

# Output result
if [[ -f "$TAR_FILE" ]]; then
    SIZE=$(du -h "$TAR_FILE" | cut -f1)
    echo ""
    echo "✓ Created $TAR_FILE ($SIZE)"
    echo "  Upload to CapRover → coherence-demo.koher.app"
    echo ""
    echo "  Required environment variables:"
    echo "  - ANTHROPIC_API_KEY: Your Anthropic API key"
    echo "  - DEMO_PASSWORD: Password for demo access"
else
    echo "[ERROR] Failed to create $TAR_FILE"
    exit 2
fi
