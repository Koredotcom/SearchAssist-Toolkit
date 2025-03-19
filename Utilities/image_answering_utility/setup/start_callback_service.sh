#!/bin/bash

# Start Callback Service Script
echo "Starting Callback Service..."

# Navigate to project root
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

# Check if Python virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies for callback service
echo "Installing Python dependencies..."
cd python
pip install -r requirements.txt
cd ..  # Return to project root

# Create logs directory if it doesn't exist
mkdir -p logs

# Create symbolic link for logs directory in python directory if it doesn't exist
if [ ! -L "python/logs" ] && [ ! -d "python/logs" ]; then
    ln -s ../logs python/logs
fi

# Start the Callback service
echo "Starting Callback service..."
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"
python python/services/callback_server.py 