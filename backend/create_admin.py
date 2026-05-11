#!/usr/bin/env python3
"""Create admin user if not exists. Runs before gunicorn starts."""

import bcrypt
import os
import sys
import time
import psycopg2

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'change-me-in-production')

# Parse DATABASE_URL
db_url = os.environ.get('DATABASE_URL', 'postgresql://dwar:change-me-in-production@postgres:5432/dwar_rater')
parts = db_url.replace('postgresql://', '').split('@')
user_pass = parts[0].split(':')
host_db = parts[1].split('/')
host_port = host_db[0].split(':')

host = host_port[0]
port = int(host_port[1]) if len(host_port) > 1 else 5432
dbname = host_db[1]
user = user_pass[0]
password = user_pass[1]

print(f'Connecting to PostgreSQL: {host}:{port}/{dbname}')

# Retry connection up to 30 seconds
for attempt in range(30):
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password
        )
        conn.autocommit = True
        break
    except psycopg2.OperationalError as e:
        if attempt < 29:
            print(f'Database not ready, retrying in 1s... ({e})')
            time.sleep(1)
        else:
            print(f'Failed to connect to database after 30s: {e}')
            sys.exit(1)

with conn.cursor() as cur:
    # Check if app_user table exists
    cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'app_user')")
    table_exists = cur.fetchone()[0]

    if not table_exists:
        print('app_user table does not exist yet. Waiting for migrations...')
        # Wait for migrations to complete
        for attempt in range(60):
            time.sleep(2)
            cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'app_user')")
            if cur.fetchone()[0]:
                print('app_user table created by migrations')
                break
        else:
            print('app_user table still does not exist after 120s. Creating it manually...')
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_user (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(80) UNIQUE NOT NULL,
                    password_hash VARCHAR(256) NOT NULL,
                    role VARCHAR(30) DEFAULT 'user',
                    is_active BOOLEAN DEFAULT true,
                    must_change_password BOOLEAN DEFAULT false,
                    last_login_at TIMESTAMP,
                    totp_secret VARCHAR(64),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
            print('app_user table created manually')

    # Check if admin exists
    cur.execute("SELECT id FROM app_user WHERE username = %s", (ADMIN_USER,))
    if cur.fetchone():
        print(f'Admin user already exists: {ADMIN_USER}')
    else:
        h = bcrypt.hashpw(ADMIN_PASS.encode(), bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT INTO app_user (username, password_hash, role, is_active, must_change_password, created_at) VALUES (%s, %s, 'admin', true, false, NOW())",
            (ADMIN_USER, h)
        )
        conn.commit()
        print(f'Admin user created: {ADMIN_USER}')

conn.close()
