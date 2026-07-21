"""Diagnostic script for admin login issues.

Run via docker compose exec backend python /app/_diag.py

Env vars:
- DIAG_ACTION: check | reset-password | set-password | fix-schema
- DIAG_NEWPASS: new password (for set-password)
- ADMIN_PASS: from .env (used by reset-password)
"""
import hashlib
import os
import sys
import json
import urllib.request

from sqlalchemy import text
from shared.models import db
from shared.models.user import User
import bcrypt


def run():
    from app import create_app
    app = create_app()
    with app.app_context():
        print("=== 1. session_token schema ===", flush=True)
        rows = db.session.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name='session_token' ORDER BY ordinal_position"
        )).fetchall()
        for r in rows:
            print(f"  {r[0]}: {r[1]}", flush=True)
        if not rows:
            print("  (session_token table does not exist)", flush=True)

        print("=== 2. alembic_version ===", flush=True)
        try:
            rows = db.session.execute(text("SELECT version_num FROM alembic_version")).fetchall()
            if rows:
                for r in rows:
                    print(f"  {r[0]}", flush=True)
            else:
                print("  (empty)", flush=True)
        except Exception as e:
            print(f"  ERROR: {e}", flush=True)

        print("=== 3. Admin user ===", flush=True)
        u = User.query.filter_by(username='admin').first()
        if u:
            print(f"  id={u.id} role={u.role} active={u.is_active} "
                  f"must_change={u.must_change_password} "
                  f"hash_len={len(u.password_hash) if u.password_hash else 0}", flush=True)
        else:
            print("  NOT FOUND", flush=True)

        action = os.environ.get('DIAG_ACTION', 'check')

        if action == 'fix-schema':
            print("=== 4. FIX-SCHEMA ===", flush=True)
            cols = [r[0] for r in db.session.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='session_token'"
            )).fetchall()]
            has_hash = 'token_hash' in cols
            has_token = 'token' in cols
            print(f"  token_hash exists: {has_hash}, token exists: {has_token}", flush=True)

            if has_token and not has_hash:
                print("  Adding token_hash, backfilling sha256, dropping token...", flush=True)
                db.session.execute(text("ALTER TABLE session_token ADD COLUMN token_hash VARCHAR(64)"))
                sessions = db.session.execute(text(
                    "SELECT id, token FROM session_token WHERE token IS NOT NULL"
                )).fetchall()
                for sid, tok in sessions:
                    h = hashlib.sha256((tok or '').encode()).hexdigest()
                    db.session.execute(text(
                        "UPDATE session_token SET token_hash = :h WHERE id = :id"
                    ), {'h': h, 'id': sid})
                db.session.execute(text(
                    "UPDATE session_token SET token_hash = '0' WHERE token_hash IS NULL"
                ))
                db.session.execute(text("ALTER TABLE session_token ALTER COLUMN token_hash SET NOT NULL"))
                db.session.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_session_token_token_hash "
                    "ON session_token (token_hash)"
                ))
                db.session.execute(text("DROP INDEX IF EXISTS ix_session_token_token"))
                db.session.execute(text("ALTER TABLE session_token DROP COLUMN token"))
                db.session.commit()
                print("  Schema fix applied.", flush=True)
            elif has_hash:
                print("  token_hash already present - no schema fix needed.", flush=True)

            print("  Stamping alembic_version to 006_hash_session_tokens...", flush=True)
            try:
                db.session.execute(text("DELETE FROM alembic_version"))
                db.session.execute(text(
                    "INSERT INTO alembic_version (version_num) VALUES ('006_hash_session_tokens')"
                ))
                db.session.commit()
                print("  Alembic stamped.", flush=True)
            except Exception as e:
                print(f"  Stamp failed: {e}", flush=True)
                db.session.rollback()

        newpass = os.environ.get('DIAG_NEWPASS', '')
        if action in ('reset-password', 'set-password'):
            if action == 'reset-password':
                pwd = os.environ.get('ADMIN_PASS', 'change-me')
                print(f"  reset-password: using ADMIN_PASS from env (len={len(pwd)})", flush=True)
            else:
                pwd = newpass
                print(f"  set-password: using DIAG_NEWPASS (len={len(pwd)})", flush=True)
            if len(pwd) < 8:
                print(f"  ERROR: password too short (len={len(pwd)})", flush=True)
            else:
                u = User.query.filter_by(username='admin').first()
                if u:
                    u.password_hash = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
                    u.must_change_password = False
                    db.session.commit()
                    print(f"  Password set (len={len(pwd)})", flush=True)
                else:
                    print("  admin not found", flush=True)

        print("=== 5. Login test ===", flush=True)
        pwd = os.environ.get('ADMIN_PASS', 'change-me')
        if action == 'set-password' and newpass:
            pwd = newpass
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
            print(f"  Login OK: status={r.status}, "
                  f"user={d.get('user', {}).get('username')}, "
                  f"role={d.get('user', {}).get('role')}", flush=True)
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:300]
            print(f"  Login FAILED: HTTP {e.code} - {body}", flush=True)
        except Exception as e:
            print(f"  Login ERROR: {type(e).__name__}: {str(e)[:200]}", flush=True)


if __name__ == '__main__':
    run()