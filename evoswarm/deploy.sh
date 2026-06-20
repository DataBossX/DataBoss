#!/usr/bin/env bash
# One-click deploy. Local default: `./deploy.sh`  |  Cluster: `./deploy.sh k8s`
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-local}"

echo "==> [1/4] Installing package + dev deps"
pip install -e ".[dev]" >/dev/null

echo "==> [2/4] Generating + validating 12 agent specs"
python scripts/gen_specs.py

echo "==> [3/4] Running eval/unit gate (must pass before deploy)"
python -m pytest -q

case "$MODE" in
  local)
    echo "==> [4/4] Booting stack via docker-compose"
    docker compose up -d --build
    echo "API:    http://localhost:8080/healthz"
    echo "Docs:   http://localhost:8080/docs"
    echo "Neo4j:  http://localhost:7474"
    ;;
  k8s)
    echo "==> [4/4] Deploying to Kubernetes via Helm"
    helm upgrade --install evoswarm ./helm/evoswarm --wait
    kubectl get pods -l app=evoswarm
    ;;
  *)
    echo "unknown mode: $MODE (use 'local' or 'k8s')" >&2; exit 1 ;;
esac
echo "==> EvoSwarm up ✅"
