#!/bin/bash
# Start the EPIC Demo Server (extends epic_runtime_server with /generate and /evaluate)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_SCRIPT="$SCRIPT_DIR/InteractiveEPIC/epic_demo_server.py"

# Activate conda environment
CONDA_BASE="$(conda info --base 2>/dev/null || echo "$HOME/miniconda3")"
source "$CONDA_BASE/etc/profile.d/conda.sh" 2>/dev/null || true
conda activate epic 2>/dev/null || true

# Check vLLM (port 8008 for Qwen3-8B)
echo "Checking vLLM at http://127.0.0.1:8008..."
if ! curl -sf http://127.0.0.1:8008/health > /dev/null 2>&1; then
    echo "WARNING: vLLM not available at port 8008."
    echo "  Start the SSH tunnel: ssh <H200> -L 8008:localhost:8008"
    echo "  Or run vLLM locally."
    exit 1
fi
echo "vLLM ready."

# Start the demo server
echo "Starting EPIC Demo Server..."
python3 "$SERVER_SCRIPT" \
    --host 127.0.0.1 \
    --port 8765 \
    --llm-model "Qwen/Qwen3-8B" \
    --llm-server-url "http://127.0.0.1:8008" \
    --llm-timeout 180
