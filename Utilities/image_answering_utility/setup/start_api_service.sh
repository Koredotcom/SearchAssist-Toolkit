#!/bin/bash

# Start API Service Script
echo "Starting API Service..."

# Check for nvm and install/use Node.js v16
if [ -f "$HOME/.nvm/nvm.sh" ]; then
    # Load nvm
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    
    # Install Node.js v16 if not already installed
    if ! nvm list | grep -q "v16"; then
        echo "Installing Node.js v16..."
        nvm install 16
    fi
    
    # Use Node.js v16
    echo "Switching to Node.js v16..."
    nvm use 16
else
    # Check if node version is less than 16
    NODE_VERSION=$(node --version | cut -d. -f1 | tr -d 'v')
    if [ "$NODE_VERSION" -lt "16" ]; then
        echo "Error: Node.js version 16 or higher is required."
        echo "Please install nvm or upgrade Node.js manually."
        exit 1
    fi
fi

# Navigate to project root
cd "$(dirname "$0")/.."

# Check if node_modules exists and run setup if needed
if [ ! -d "node_modules" ]; then
    echo "Running initial setup..."
    npm run setup
else
    # Check MongoDB installation
    if ! command -v mongod &> /dev/null; then
        echo "MongoDB not found. Installing MongoDB..."
        npm run install-mongodb
    fi
fi

# Check if MongoDB is running
if ! pgrep mongod > /dev/null; then
    echo "MongoDB is not running. Starting MongoDB..."
    sudo systemctl start mongod
    sleep 5  # Wait for MongoDB to start
fi

# Initialize MongoDB if needed
echo "Initializing MongoDB..."
npm run init-mongodb

# Check if Redis is running
if ! pgrep redis-server > /dev/null; then
    echo "Redis server is not running. Starting Redis..."
    redis-server &
    sleep 2
fi

# Create required directories
mkdir -p logs storage/processing

# Check if GraphicsMagick is installed
if ! command -v gm &> /dev/null; then
    echo "GraphicsMagick is not installed. Please install it first:"
    echo "Ubuntu/Debian: sudo apt-get install graphicsmagick"
    echo "macOS: brew install graphicsmagick"
    echo "Windows: Download from https://sourceforge.net/projects/graphicsmagick/"
    exit 1
fi

# Check if config/.env exists
if [ ! -f "config/.env" ]; then
    echo "Error: config/.env file not found!"
    echo "Please create config/.env file with your configuration settings."
    exit 1
fi

# Start the API service
echo "Starting API service..."
node src/api/server.js 
