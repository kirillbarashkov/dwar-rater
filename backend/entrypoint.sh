#!/bin/bash
# Backend entrypoint script
# Creates admin user before starting gunicorn

set -e

echo "Waiting for database..."
sleep 3

echo "Creating admin user if not exists..."
python3 -c "
import bcrypt, os, sys
sys.path.insert(0, '/app')
os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL', 'postgresql://dwar:change-me-in-production@postgres:5432/dwar_rater')
os.environ['AUTH_ENABLED'] = 'false'
os.environ['SECRET_KEY'] = 'init-key'

from shared.models import db
from app import create_app

app = create_app()
with app.app_context():
    result = db.session.execute(
        db.text(\"SELECT id FROM app_user WHERE username = :u\"),
        {'u': os.environ.get('ADMIN_USER', 'admin')}
    ).first()
    if not result:
        h = bcrypt.hashpw(os.environ.get('ADMIN_PASS', 'change-me-in-production').encode(), bcrypt.gensalt()).decode()
        db.session.execute(
            db.text(\"INSERT INTO app_user (username, password_hash, role, is_active, must_change_password, created_at) VALUES (:u, :h, 'admin', true, false, NOW())\"),
            {'u': os.environ.get('ADMIN_USER', 'admin'), 'h': h}
        )
        db.session.commit()
        print('Admin user created')
    else:
        print('Admin user already exists')
"

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 30 app:app
