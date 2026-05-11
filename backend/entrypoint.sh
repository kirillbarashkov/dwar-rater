#!/bin/bash
# Backend entrypoint script
# Runs migrations, seed data, and admin creation BEFORE gunicorn forks workers.
# This ensures all DB operations happen in a single process.

set -e

echo "=== Pre-start: Creating test database ==="
PGPASSWORD="${POSTGRES_PASSWORD:-change-me-in-production}" psql -h postgres -p 5432 -U "${POSTGRES_USER:-dwar}" -d postgres -c "DROP DATABASE IF EXISTS dwar_rater_test"
PGPASSWORD="${POSTGRES_PASSWORD:-change-me-in-production}" psql -h postgres -p 5432 -U "${POSTGRES_USER:-dwar}" -d postgres -c "CREATE DATABASE dwar_rater_test"
echo "Test database ready"

echo "=== Pre-start: Running migrations, seed, and admin creation ==="

python3 -c "
import os, sys, bcrypt, logging, psycopg2

sys.path.insert(0, '/app')

# Set up minimal env for imports
os.environ.setdefault('DATABASE_URL', 'postgresql://dwar:change-me-in-production@postgres:5432/dwar_rater')
os.environ.setdefault('AUTH_ENABLED', 'false')
os.environ.setdefault('SECRET_KEY', 'pre-start-key')

from app import create_app
from shared.models import db
from shared.rbac.seed import seed_all

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('pre-start')

# Create app (runs migrations)
app = create_app()

with app.app_context():
    # Run seed data
    seed_all(db)
    db.session.commit()
    logger.info('Pre-start: seed data committed')

    # Create admin user via direct psycopg2 with autocommit
    admin_user = os.environ.get('ADMIN_USER', 'admin')
    admin_pass = os.environ.get('ADMIN_PASS', 'change-me-in-production')

    db_url = os.environ.get('DATABASE_URL')
    parts = db_url.replace('postgresql://', '').split('@')
    user_pass = parts[0].split(':')
    host_db = parts[1].split('/')
    host_port = host_db[0].split(':')

    conn = psycopg2.connect(
        host=host_port[0],
        port=int(host_port[1]) if len(host_port) > 1 else 5432,
        dbname=host_db[1],
        user=user_pass[0],
        password=user_pass[1]
    )
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute('SELECT id FROM app_user WHERE username = %s', (admin_user,))
        if cur.fetchone():
            logger.info(f'Pre-start: admin user already exists: {admin_user}')
        else:
            h = bcrypt.hashpw(admin_pass.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                'INSERT INTO app_user (username, password_hash, role, is_active, must_change_password, created_at) VALUES (%s, %s, %s, true, false, NOW())',
                (admin_user, h, 'admin')
            )
            cur.execute('SELECT id, username FROM app_user WHERE username = %s', (admin_user,))
            row = cur.fetchone()
            if row:
                logger.info(f'Pre-start: admin user created: id={row[0]}, username={row[1]}')
            else:
                logger.error('Pre-start: admin INSERT succeeded but verification failed')

    conn.close()
    logger.info('Pre-start: complete')
"

echo "=== Starting gunicorn ==="
exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 30 app:app
