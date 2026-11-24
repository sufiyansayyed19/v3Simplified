#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UVICORN="$ROOT_DIR/.venv/bin/uvicorn"
if [[ ! -x "$UVICORN" ]]; then
  UVICORN="$ROOT_DIR/.venv/Scripts/uvicorn.exe"
fi

echo "Starting all 4 microservices in the background..."

(cd "$ROOT_DIR/services/user-auth-service" && "$UVICORN" app.main:app --port 8001 --reload) &
(cd "$ROOT_DIR/services/vehicle-service"   && "$UVICORN" app.main:app --port 8002 --reload) &
(cd "$ROOT_DIR/services/parking-service"   && "$UVICORN" app.main:app --port 8003 --reload) &
(cd "$ROOT_DIR/services/payment-service"   && "$UVICORN" app.main:app --port 8004 --reload) &

echo "All 4 microservices started (ports 8001-8004). Press Ctrl+C to stop."
wait
