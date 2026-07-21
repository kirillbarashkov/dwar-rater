"""Diagnostic script for admin login issues.

Run via: docker compose exec postgres psql -U dwar -d dwar_rater -f /tmp/_diag.sql

Or directly inline from VM. Pure SQL - no Flask context, no create_app.
"""
import hashlib
import os
import sys
import json
import urllib.request
import psycopg2

ACTION = os.environ.get('DIAG_ACTION', 'check')
NEWPASS = os.environ.get('DIAG_NEWPASS', '')
ADMIN_PASS = os.environ.get('ADMIN_PASS', 'change-me')
DB_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://dwar:change-me-in-production@postgres:5432/dwar_rater',
)


def parse_db_url(url):
    parts = url.replace('postgresql://', '').split('@')
    user_pass = parts[0].split(':')
    host_db = parts[1].split('/')
    host_port = host_db[0].split(':')
    return {
        'host': host_port[0],
        'port': int(host_port[1]) if len(host_port) > 1 else 5432,
        'dbname': host_db[1],
        'user': user_pass[0],
        'password': user_pass[1],
    }


def main():
    params = parse_db_url(DB_URL)
    print(f"Connecting to postgres host={params['host']} db={params['dbname']}", flush=True)
    conn = psycopg2.connect(**params)
    conn.autocommit = True
    cur = conn.cursor()

    print("=== 1. session_token schema ===", flush=True)
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='session_token' ORDER BY ordinal_position"
    )
    cols = cur.fetchall()
    for r in cols:
        print(f"  {r[0]}: {r[1]}", flush=True)
    if not cols:
        print("  (session_token table does not exist)", flush=True)

    print("=== 2. alembic_version ===", flush=True)
    try:
        cur.execute("SELECT version_num FROM alembic_version")
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(f"  {r[0]}", flush=True)
        else:
            print("  (empty)", flush=True)
    except psycopg2.Error as e:
        print(f"  ERROR: {e}", flush=True)
        conn.rollback()

    print("=== 3. Admin user ===", flush=True)
    try:
        cur.execute(
            "SELECT id, username, role, is_active, must_change_password, "
            "LENGTH(password_hash) FROM app_user WHERE username='admin'"
        )
        row = cur.fetchone()
        if row:
            print(f"  id={row[0]} username={row[1]} role={row[2]} "
                  f"active={row[3]} must_change={row[4]} hash_len={row[5]}", flush=True)
        else:
            print("  NOT FOUND in DB", flush=True)
    except psycopg2.Error as e:
        print(f"  ERROR: {e}", flush=True)
        conn.rollback()

    print("=== 4. Tables present ===", flush=True)
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name"
    )
    tables = [r[0] for r in cur.fetchall()]
    print(f"  total: {len(tables)}", flush=True)
    print(f"  tables: {tables}", flush=True)

    if ACTION == 'fix-schema':
        print("=== 5. FIX-SCHEMA ===", flush=True)
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='session_token'"
        )
        col_names = [r[0] for r in cur.fetchall()]
        has_hash = 'token_hash' in col_names
        has_token = 'token' in col_names
        print(f"  token_hash exists: {has_hash}, token exists: {has_token}", flush=True)

        if has_token and not has_hash:
            print("  Adding token_hash column, backfilling, dropping token...", flush=True)
            cur.execute("ALTER TABLE session_token ADD COLUMN IF NOT EXISTS token_hash VARCHAR(64)")
            cur.execute("SELECT id, token FROM session_token WHERE token IS NOT NULL")
            existing = cur.fetchall()
            print(f"  Found {len(existing)} rows with token to backfill", flush=True)
            for sid, tok in existing:
                h = hashlib.sha256((tok or '').encode()).hexdigest()
                cur.execute(
                    "UPDATE session_token SET token_hash = %s WHERE id = %s",
                    (h, sid),
                )
            cur.execute("UPDATE session_token SET token_hash = '0' WHERE token_hash IS NULL")
            cur.execute("ALTER TABLE session_token ALTER COLUMN token_hash SET NOT NULL")
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_session_token_token_hash "
                "ON session_token (token_hash)"
            )
            cur.execute("DROP INDEX IF EXISTS ix_session_token_token")
            cur.execute("ALTER TABLE session_token DROP COLUMN IF EXISTS token")
            print("  Schema fix applied.", flush=True)
        elif has_hash:
            print("  token_hash already present.", flush=True)

        print("  Stamping alembic_version to 006...", flush=True)
        try:
            cur.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
            cur.execute("DELETE FROM alembic_version")
            cur.execute(
                "INSERT INTO alembic_version (version_num) "
                "VALUES ('006_hash_session_tokens')"
            )
            print("  Alembic stamped to 006.", flush=True)
        except psycopg2.Error as e:
            print(f"  Stamp failed: {e}", flush=True)
            conn.rollback()

    if ACTION in ('reset-password', 'set-password'):
        import bcrypt as _bcrypt
        if ACTION == 'reset-password':
            pwd = ADMIN_PASS
            print(f"  reset-password: using ADMIN_PASS (len={len(pwd)})", flush=True)
        else:
            pwd = NEWPASS
            print(f"  set-password: using DIAG_NEWPASS (len={len(pwd)})", flush=True)
        if len(pwd) < 8:
            print(f"  ERROR: password too short (len={len(pwd)})", flush=True)
        else:
            h = _bcrypt.hashpw(pwd.encode(), _bcrypt.gensalt()).decode()
            cur.execute(
                "UPDATE app_user SET password_hash=%s, must_change_password=false "
                "WHERE username='admin'",
                (h,),
            )
            print(f"  Password updated (rows affected: {cur.rowcount})", flush=True)

    print("=== 6. Login test ===", flush=True)
    pwd = ADMIN_PASS
    if ACTION == 'set-password' and NEWPASS:
        pwd = NEWPASS
    body = json.dumps({'username': 'admin', 'password': pwd}).encode()
    req = urllib.request.Request(
        'http://localhost:5000/api/auth/login',
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        r = urllib.request.urlopen(req, timeout=10)
        d = json.loads(r.read())
        print(f"  Login OK: status={r.status} "
              f"user={d.get('user', {}).get('username')} "
              f"role={d.get('user', {}).get('role')}", flush=True)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"  Login FAILED: HTTP {e.code} - {body}", flush=True)
    except Exception as e:
        print(f"  Login ERROR: {type(e).__name__}: {str(e)[:200]}", flush=True)

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()