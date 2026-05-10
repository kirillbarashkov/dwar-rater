#!/bin/bash
# Backend entrypoint script
# Creates admin user before starting gunicorn

set -e

echo "Waiting for database..."
sleep 3

echo "Creating admin user if not exists..."
python3 /app/create_admin.py

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 30 app:app
