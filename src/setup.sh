#!/bin/bash
set -e

# Validate environment
check_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Error: $1 is required but not installed"
        exit 1
    }
}

check_command python3
check_command pip3
check_command redis-server

# Check if virtual environment already exists
if [ -d "venv" ]; then
    echo "Virtual environment 'venv' already exists."
    echo "Please remove it or use a different name if you want to recreate it."
    exit 1
fi

# Create virtual environment
python3 -m venv venv || {
    echo "Failed to create virtual environment"
    exit 1
}

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install --user -r requirements.txt