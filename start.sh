#!/bin/bash

set -u

BACKEND_PID=""
FRONTEND_PID=""
SIDURI_PYTHON=".venv/bin/python"

if [[ ! -x "$SIDURI_PYTHON" ]]; then
  echo "Siduri requires its Python environment. Run: python -m venv .venv"
  echo "Then install dependencies with: .venv/bin/pip install -e '.[platforms]'"
  exit 1
fi

cleanup() {
  trap - EXIT INT TERM
  if [[ -n "$BACKEND_PID" ]]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [[ -n "$FRONTEND_PID" ]]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

port_is_open() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

children_are_alive() {
  kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null
}

wait_for_url() {
  local label="$1"
  local url="$2"
  local origin="${3:-}"
  local attempt
  for attempt in {1..60}; do
    if ! children_are_alive; then
      echo "$label could not become ready because one Siduri process exited."
      return 1
    fi
    if [[ -n "$origin" ]]; then
      if curl --fail --silent --show-error --output /dev/null --header "Origin: $origin" "$url" 2>/dev/null; then
        sleep 0.1
        children_are_alive && return 0
      fi
    else
      if curl --fail --silent --show-error --output /dev/null "$url" 2>/dev/null; then
        sleep 0.1
        children_are_alive && return 0
      fi
    fi
    sleep 0.25
  done
  echo "$label did not become ready within 15 seconds."
  return 1
}

trap cleanup EXIT INT TERM

if port_is_open 8765 || port_is_open 3000; then
  echo "Siduri cannot start because port 8765 or 3000 is already in use."
  echo "If Siduri is already running, open http://localhost:3000/chat instead of starting a second stack."
  exit 1
fi

echo "Starting Siduri backend (Python)..."
# The orchestrator loads the ignored .env file itself. Do not export model
# credentials into the frontend process.
"$SIDURI_PYTHON" -m apps.orchestrator.src.siduri_orchestrator.server &
BACKEND_PID=$!

echo "Starting Siduri frontend (Next.js)..."
npm run dev &
FRONTEND_PID=$!

if ! wait_for_url "Orchestrator" "http://127.0.0.1:8765/health" "http://127.0.0.1:3000"; then exit 1; fi
if ! wait_for_url "Web client" "http://127.0.0.1:3000/chat"; then exit 1; fi

echo "Siduri is ready."
echo "- Operator Console: http://localhost:3000/operator"
echo "- Private Chat:     http://localhost:3000/chat"
echo "Press Ctrl+C to stop both."

# If either process exits, stop the other one instead of leaving a deceptive
# frontend that can only return 502 responses.
set +e
wait -n "$BACKEND_PID" "$FRONTEND_PID"
STATUS=$?
set -e
echo "A Siduri process stopped (status $STATUS); shutting down the remaining process."
exit "$STATUS"
