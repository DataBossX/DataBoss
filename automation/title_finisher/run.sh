#!/usr/bin/env bash
# TitleFinisher launcher (macOS/Linux). Installs deps on first run, then dispatches.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if [ ! -d .venv ]; then
  echo "[setup] creating venv + installing requirements…"
  "$PY" -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r requirements.txt
fi
exec ./.venv/bin/python -m titlefinisher "$@"
