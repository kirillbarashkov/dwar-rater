#!/bin/bash
# Backend entrypoint script

set -e

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 30 app:app
