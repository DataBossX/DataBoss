#!/usr/bin/env bash
# Starts the real Command Center server against synthetic sandbox roots and
# runs the Playwright/axe viewport suite against it. Linux/macOS dev+CI
# helper (the real Windows launcher acceptance lives in the PowerShell
# script under command_center/qa/windows-acceptance.ps1). No client/share
# path is ever touched -- everything lives under a fresh temp sandbox.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CC_DIR="$(dirname "$SCRIPT_DIR")"
SANDBOX_ROOT="$(mktemp -d /tmp/databossx_qa_sandbox.XXXXXX)"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -rf "$SANDBOX_ROOT"
}
trap cleanup EXIT

export DATABOSSX_SANDBOX_MODE=1
export DATABOSSX_DB_PATH="$SANDBOX_ROOT/runtime/databossx.db"
export DATABOSSX_PENTERRA_ROOT="$SANDBOX_ROOT/SyntheticPenterra"
export DATABOSSX_HORIZON_ROOT="$SANDBOX_ROOT/SyntheticHorizon"
mkdir -p "$DATABOSSX_PENTERRA_ROOT/SyntheticProject-01" "$DATABOSSX_HORIZON_ROOT"
cat > "$DATABOSSX_PENTERRA_ROOT/SyntheticProject-01/Runsheet_sample.txt" <<'EOF'
This is a harmless synthetic sandbox file. NO CLIENT DATA.
EOF

cd "$CC_DIR"
python3 server.py > "$SANDBOX_ROOT/server.log" 2>&1 &
SERVER_PID=$!

RUNTIME_DIR="$(dirname "$DATABOSSX_DB_PATH")"
PORT=""
for _ in $(seq 1 30); do
  if [[ -f "$RUNTIME_DIR/port.txt" ]]; then
    PORT="$(cat "$RUNTIME_DIR/port.txt")"
    if curl -sf "http://127.0.0.1:$PORT/api/health" > /dev/null 2>&1; then
      break
    fi
  fi
  sleep 1
done

if [[ -z "$PORT" ]]; then
  echo "Server did not become healthy within 30s. Log:"
  cat "$SANDBOX_ROOT/server.log"
  exit 1
fi

echo "Server healthy on port $PORT (sandbox: $SANDBOX_ROOT)"
export DATABOSSX_QA_BASE_URL="http://127.0.0.1:$PORT"

cd "$SCRIPT_DIR"
export DATABOSSX_QA_CHROMIUM_PATH="${DATABOSSX_QA_CHROMIUM_PATH:-}"
npx playwright test "$@"
