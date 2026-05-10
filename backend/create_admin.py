#!/usr/bin/env python3
"""Create admin user if not exists. Runs before gunicorn starts."""

import bcrypt
import os
import psycopg2

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'change-me-in-production')

# Parse DATABASE_URL
db_url = os.environ.get('DATABASE_URL', 'postgresql://dwar:change-me-in-production@postgres:5432/dwar_rater')
# postgresql://user:pass@host:port/dbname
parts = db_url.replace('postgresql://', '').split('@')
user_pass = parts[0].split(':')
host_db = parts[1].split('/')
host_port = host_db[0].split(':')

print(f'Connecting to PostgreSQL: {host_port[0]}:{host_port[1] if len(host_port) > 1 else 5432}/{host_db[1]}')

conn = psycopg2.connect(
    host=host_port[0],
    port=int(host_port[1]) if len(host_port) > 1 else 5432,
    dbname=host_db[1],
    user=user_pass[0],
    password=user_pass[1]
)
conn.autocommit = True

with conn.cursor() as cur:
    cur.execute("SELECT id FROM app_user WHERE username = %s", (ADMIN_USER,))
    if cur.fetchone():
        print(f'Admin user already exists: {ADMIN_USER}')
    else:
        h = bcrypt.hashpw(ADMIN_PASS.encode(), bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO app_user (username, password_hash, role, is_active, must_change_password, created_at) VALUES (%s, %s, 'admin', true, false, NOW())",
            (ADMIN_USER, h)
        )
        print(f'Admin user created: {ADMIN_USER}')

conn.close()
