#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/command_nexus"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   DataBossX Command Nexus — Local Boot   ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Backend ────────────────────────────────────
echo "[1/3] Installing backend dependencies…"
cd "$BACKEND"
pip install -r requirements.txt -q

echo "[2/3] Starting FastAPI backend on http://localhost:8001 …"
uvicorn server:app --host 0.0.0.0 --port 8001 --reload &
BACK_PID=$!
echo "      Backend PID: $BACK_PID"

# Wait for backend to be ready
echo "      Waiting for backend to respond…"
for i in $(seq 1 20); do
  if curl -s http://localhost:8001/api/health >/dev/null 2>&1; then
    echo "      ✓ Backend is up"
    break
  fi
  sleep 1
done

# ── Frontend ───────────────────────────────────
echo "[3/3] Starting Command Nexus frontend on http://localhost:5173 …"
cd "$FRONTEND"
if [ ! -d "node_modules" ]; then
  echo "      Installing npm packages (first run)…"
  npm install
fi
npx vite --host --port 5173 &
FRONT_PID=$!
echo "      Frontend PID: $FRONT_PID"

echo ""
echo "══════════════════════════════════════════"
echo "  App:     http://localhost:5173"
echo "  API:     http://localhost:8001"
echo "  Docs:    http://localhost:8001/docs"
echo "══════════════════════════════════════════"
echo "  Ctrl+C to stop all services"
echo ""

trap 'echo ""; echo "Shutting down…"; kill $BACK_PID $FRONT_PID 2>/dev/null; exit 0' SIGINT SIGTERM

wait
