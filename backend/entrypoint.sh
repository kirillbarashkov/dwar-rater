#!/bin/bash
# Backend entrypoint script

set -e

echo "Starting gunicorn..."
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 30 app:app &
GUNICORN_PID=$!

echo "Initializing admin user..."
python3 /app/init_admin.py || echo "WARNING: Admin initialization failed, but gunicorn is running"

# Wait for gunicorn
wait $GUNICORN_PID
