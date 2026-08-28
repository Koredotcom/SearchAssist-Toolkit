#!/bin/bash

# Exit on any error
set -e

echo "Setting up DOCLING_SERVICES..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating required directories..."
mkdir -p logs


echo "Setup completed successfully!"
echo ""


# Start the Markdown service
echo "Starting Markdown service..."
python -m app.main 