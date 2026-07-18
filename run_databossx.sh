#!/usr/bin/env bash
# DataBossX Command Center -- launcher for macOS / Linux / CI.
#
#   ./run_databossx.sh doctor
#   ./run_databossx.sh demo
#   ./run_databossx.sh run --project horizon --root /path/to/files
#   ./run_databossx.sh calc --wi 1 --royalty 1/8
#
# On first run it creates a private .dbxvenv and installs dependencies.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
VENV=".dbxvenv"
VPY="$VENV/bin/python"

if [ ! -x "$VPY" ]; then
  echo "Setting up DataBossX (first run only)..."
  "$PY" -m venv "$VENV"
fi

"$VPY" -m pip install --quiet --disable-pip-version-check \
  pydantic openpyxl reportlab python-docx >/dev/null 2>&1 || {
    echo "[PROBLEM] Could not install components (check your connection)." >&2
    exit 1
  }

if [ "$#" -eq 0 ]; then
  "$VPY" -m databossx doctor
  echo
  echo "Usage: ./run_databossx.sh [doctor|demo|list|run|calc] ..."
  exit 0
fi

exec "$VPY" -m databossx "$@"
