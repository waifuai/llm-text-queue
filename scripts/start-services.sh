#!/bin/bash
set -euo pipefail

echo "Starting LLM Text Queue GPU - Consolidated Service"
echo "=================================================="

# Ensure uv venv exists
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python -m uv venv .venv
  .venv/Scripts/python.exe -m ensurepip || true
  .venv/Scripts/python.exe -m pip install uv
  .venv/Scripts/python.exe -m uv pip install -r requirements.txt
  echo "Virtual environment created and dependencies installed."
fi

# Use venv python explicitly
PY=".venv/bin/python"
[ -x "$PY" ] || PY=".venv/Scripts/python.exe"

# Check if Redis is already running
if redis-cli ping > /dev/null 2>&1; then
  echo "Redis server is already running."
else
  echo "Starting Redis server..."
  redis-server --daemonize yes
  echo "Redis server started."
fi

# Start worker.py for queue processing
echo "Starting worker service..."
nohup "$PY" src/worker.py >/tmp/worker.log 2>&1 &
echo "Worker service started (log: /tmp/worker.log)"

# Start the consolidated main service
echo "Starting main service..."
PORT=${PORT:-8000}
nohup "$PY" src/main.py >/tmp/main.log 2>&1 &
echo "Main service started on port $PORT (log: /tmp/main.log)"

# Legacy services for backward compatibility (optional)
if [ "${START_LEGACY_SERVICES:-false}" = "true" ]; then
  echo "Starting legacy services for backward compatibility..."

  # Start queue service
  QUEUE_PORT=${QUEUE_PORT:-5000}
  FLASK_APP=src/api_queue.py FLASK_ENV=production nohup "$PY" -m flask run --host=0.0.0.0 --port="${QUEUE_PORT}" >/tmp/queue.log 2>&1 &
  echo "Legacy queue service started on port $QUEUE_PORT (log: /tmp/queue.log)"

  # Start response service
  RESPOND_PORT=${RESPOND_PORT:-5001}
  FLASK_APP=src/respond.py FLASK_ENV=production nohup "$PY" -m flask run --host=0.0.0.0 --port="${RESPOND_PORT}" >/tmp/respond.log 2>&1 &
  echo "Legacy response service started on port $RESPOND_PORT (log: /tmp/respond.log)"
fi

echo ""
echo "Services started successfully!"
echo "Main service: http://localhost:$PORT"
echo "Health check: http://localhost:$PORT/health"
echo "Direct generation: http://localhost:$PORT/generate"
echo "Queue generation: http://localhost:$PORT/queue/generate"
echo "Metrics: http://localhost:$PORT/metrics"
echo ""
echo "To start legacy services, set START_LEGACY_SERVICES=true"
