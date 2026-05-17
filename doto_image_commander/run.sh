#!/usr/bin/env bash
# DOTO Image Commander launcher
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create venv if needed
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install / upgrade dependencies
pip install -q -r requirements.txt

# Load .env if present
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

echo "Starting DOTO Image Commander..."
streamlit run app.py \
    --server.headless false \
    --server.port 8501 \
    --browser.gatherUsageStats false \
    "$@"
