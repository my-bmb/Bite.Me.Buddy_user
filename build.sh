#!/usr/bin/env bash
# build.sh - Render build script

echo "Starting build process..."

# Upgrade pip to latest version
python -m pip install --upgrade pip

# Install Python dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p static/uploads

echo "Build completed successfully!"