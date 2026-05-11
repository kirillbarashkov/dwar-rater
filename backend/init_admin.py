#!/usr/bin/env python3
"""
Bulletproof admin user creation.
Runs AFTER gunicorn has started and migrations are complete.
Uses direct psycopg2 connection with autocommit.
Retries until admin exists or timeout.
"""

import bcrypt
import os
import sys
import time
import psycopg2

ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'change-me-in-production')
MAX_RETRIES = 30
RETRY_DELAY = 2

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

print(f'Admin init: connecting to {host}:{port}/{dbname}')

for attempt in range(MAX_RETRIES):
    try:
        conn = psycopg2.connect(
            host=host, port=port, dbname=dbname,
            user=user, password=password
        )
        conn.autocommit = True

        with conn.cursor() as cur:
            # Check if table exists
            cur.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'app_user')")
            if not cur.fetchone()[0]:
                print(f'Admin init: app_user table not yet created, retrying... ({attempt+1}/{MAX_RETRIES})')
                conn.close()
                time.sleep(RETRY_DELAY)
                continue

            # Check if admin exists
            cur.execute("SELECT id FROM app_user WHERE username = %s", (ADMIN_USER,))
            if cur.fetchone():
                print(f'Admin init: admin user already exists')
                conn.close()
                sys.exit(0)

            # Create admin
            h = bcrypt.hashpw(ADMIN_PASS.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                "INSERT INTO app_user (username, password_hash, role, is_active, must_change_password, created_at) VALUES (%s, %s, 'admin', true, false, NOW())",
                (ADMIN_USER, h)
            )
            conn.commit()

            # Verify
            cur.execute("SELECT id, username FROM app_user WHERE username = %s", (ADMIN_USER,))
            row = cur.fetchone()
            if row:
                print(f'Admin init: admin user created (id={row[0]}, username={row[1]})')
                conn.close()
                sys.exit(0)
            else:
                print(f'Admin init: INSERT succeeded but SELECT returned nothing, retrying...')
                conn.close()
                time.sleep(RETRY_DELAY)

    except psycopg2.OperationalError as e:
        print(f'Admin init: connection error, retrying... ({e})')
        time.sleep(RETRY_DELAY)
    except Exception as e:
        print(f'Admin init: error: {e}')
        time.sleep(RETRY_DELAY)

print(f'Admin init: FAILED after {MAX_RETRIES} retries')
sys.exit(1)
