#!/bin/bash
set -e

MODEL_DIR="/app/models/deberta-coherence"
DATA_DIR="/app/data"

# Ensure data directory exists (persistent volume may be empty on first deploy)
mkdir -p "$DATA_DIR"

# Download model if not present (first deploy only — persistent volume is empty)
if [ ! -f "$MODEL_DIR/model.safetensors" ]; then
    echo "Model not found at $MODEL_DIR. Downloading from GitHub..."
    mkdir -p /tmp/model-download
    cd /tmp/model-download
    git lfs install
    git clone --filter=blob:none --no-checkout --depth 1 \
        https://github.com/koher-architecture/coherence-diagnostic.git .
    git sparse-checkout init --cone
    git sparse-checkout set models
    git checkout main
    mkdir -p "$MODEL_DIR"
    cp -r models/deberta-coherence/* "$MODEL_DIR/"
    cd /app
    rm -rf /tmp/model-download
    echo "Model downloaded successfully."
else
    echo "Model found at $MODEL_DIR (persistent)."
fi

# Start application
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
