#!/bin/bash
set -euo pipefail

# Ensure uv venv exists
if [ ! -d ".venv" ]; then
  python -m uv venv .venv
  .venv/Scripts/python.exe -m ensurepip || true
  .venv/Scripts/python.exe -m pip install uv
  .venv/Scripts/python.exe -m uv pip install -r requirements.txt
fi

# Use venv python explicitly
PY=".venv/bin/python"
[ -x "$PY" ] || PY=".venv/Scripts/python.exe"

# Check if Redis is already running
if redis-cli ping > /dev/null 2>&1; then
  echo "Redis server is already running."
else
  echo "Starting Redis server"
  redis-server --daemonize yes
fi

# Start worker.py
echo "Starting worker.py"
nohup "$PY" src/worker.py >/tmp/worker.log 2>&1 &

# Start queue service
echo "Starting queue service"
FLASK_APP=src/api_queue.py FLASK_ENV=production QUEUE_PORT=${QUEUE_PORT:-5000} nohup "$PY" -m flask run --host=0.0.0.0 --port="${QUEUE_PORT}" >/tmp/queue.log 2>&1 &

# Start response service
echo "Starting response service"
FLASK_APP=src/respond.py FLASK_ENV=production RESPOND_PORT=${RESPOND_PORT:-5001} nohup "$PY" -m flask run --host=0.0.0.0 --port="${RESPOND_PORT}" >/tmp/respond.log 2>&1 &

echo "Services started."
