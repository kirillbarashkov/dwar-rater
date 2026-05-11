# Database Persistence Analysis

## Problem Statement
Admin login fails after container restarts because the database appears to be wiped.

## Root Cause Analysis (Historical)

### Attempt 1: `create_admin.py` in entrypoint.sh (FAILED)
- **What:** `create_admin.py` ran BEFORE gunicorn started
- **Why it failed:** Ran before Alembic migrations completed. Admin was inserted into a table that was then recreated by migrations, losing the admin user.

### Attempt 2: `_ensure_admin()` in `app.py` (FAILED)
- **What:** SQLAlchemy session-based admin creation inside `create_app()`
- **Why it failed:** Gunicorn worker forking caused SQLAlchemy session to not properly commit. The INSERT appeared to succeed but was rolled back when the worker process forked.

### Attempt 3: `init_admin.py` with psycopg2 autocommit (WORKS)
- **What:** Direct psycopg2 connection with `autocommit=True`, runs AFTER gunicorn starts
- **Why it works:** 
  - No ORM session to interfere with commits
  - Runs after migrations are complete (gunicorn has started)
  - Retries up to 30 times with 2-second delays
  - Verifies admin exists after INSERT before exiting

## Verified Persistence Scenarios

| Operation | Data Preserved? | Admin Login? |
|-----------|-----------------|--------------|
| `docker compose stop` + `start` | ✅ Yes | ✅ Works |
| `docker compose down` + `up -d` | ✅ Yes | ✅ Works |
| `docker compose down -v` + `up -d` | ✅ Yes* | ✅ Works |
| `docker compose up -d --build` | ✅ Yes | ✅ Works |
| `docker compose restart` | ✅ Yes | ✅ Works |

*`down -v` removes the volume, but `init_admin.py` recreates the admin on startup.

## Architecture

```
entrypoint.sh
├── gunicorn --bind 0.0.0.0:5000 --workers 2 app:app &  (background)
└── python3 /app/init_admin.py                           (foreground, then exits)

init_admin.py
├── Connects to PostgreSQL via psycopg2 (autocommit=True)
├── Waits for app_user table to exist (up to 60s)
├── Checks if admin exists
├── Creates admin if not exists
├── Verifies admin was created
└── Exits (gunicorn continues running)
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/entrypoint.sh` | Starts gunicorn in background, then runs init_admin.py |
| `backend/init_admin.py` | Bulletproof admin creation with retry mechanism |
| `backend/app.py` | Flask app — NO admin creation code (removed) |
| `docker-compose.yml` | Volume configuration for PostgreSQL data |

## What NOT to Do

1. **Never** create admin via SQLAlchemy in `create_app()` — session issues with gunicorn
2. **Never** create admin BEFORE migrations — table will be recreated
3. **Never** use `db.session.commit()` in entrypoint scripts — no app context

## What TO Do

1. Use direct psycopg2 connection with `autocommit=True`
2. Run admin creation AFTER gunicorn has started
3. Retry until table exists and admin is verified
4. Keep admin creation separate from the Flask app
