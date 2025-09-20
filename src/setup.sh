# LLM Text Queue GPU - Environment Setup Script
# This script validates system dependencies, creates a virtual environment using uv,
# and installs project dependencies from requirements.txt to prepare the environment
# for running the LLM text queue system.
#!/bin/bash
set -euo pipefail

# Validate environment
check_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Error: $1 is required but not installed"
        exit 1
    }
}

check_command python
check_command redis-server

# Create uv venv if missing
if [ ! -d ".venv" ]; then
    python -m uv venv .venv
    .venv/Scripts/python.exe -m ensurepip || true
    .venv/Scripts/python.exe -m pip install uv
fi

# Install dependencies into venv
.venv/Scripts/python.exe -m uv pip install -r requirements.txt

echo "Setup complete."