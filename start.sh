#!/usr/bin/env bash
# start.sh - Render start script

echo "Starting application..."
echo "Python version: $(python --version)"

# Create necessary directories
mkdir -p static/uploads
chmod -R 755 static/uploads

# Check if templates exist
if [ ! -d "templates" ]; then
    echo "ERROR: templates directory not found!"
    exit 1
fi

# Start Gunicorn
echo "Starting Gunicorn..."
gunicorn app:app \
    --workers 4 \
    --bind 0.0.0.0:$PORT \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -