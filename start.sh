#!/usr/bin/env bash
# start.sh - Render start script

echo "Starting application..."

# Create uploads directory if it doesn't exist
mkdir -p static/uploads

# Set proper permissions
chmod -R 755 static/uploads

# Start Gunicorn
gunicorn app:app --workers 4 --bind 0.0.0.0:$PORT --timeout 120