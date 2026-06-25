#!/usr/bin/env bash
# ── Title Report Builder — launcher for macOS/Linux (self-setting-up) ──────────
set -euo pipefail
cd "$(dirname "$0")"

PY=""
for c in "python3" "python"; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -z "$PY" ] && { echo "[ERROR] Python 3.11+ not found."; exit 1; }

if [ ! -x ".venv/bin/python" ]; then
  echo "Creating virtual environment..."
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt
command -v soffice >/dev/null 2>&1 || echo "[warn] LibreOffice (soffice) not found - recalc verification skipped."

if [ "${1:-ui}" = "cli" ]; then
  shift; python -m title_report_builder "$@"
else
  python -m streamlit run title_report_builder/app.py
fi
