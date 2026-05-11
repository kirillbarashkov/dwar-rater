# Database Persistence & Migration Safety

## Problem Statement
Data in PostgreSQL appears to be lost after container operations. This document provides a complete analysis and the implemented solution.

## Root Cause Analysis

### Historical Attempts (All Failed)

#### Attempt 1: `create_admin.py` in entrypoint.sh
- **What:** Created admin user BEFORE gunicorn started
- **Why it failed:** Ran before Alembic migrations. Admin was inserted into a table that was then recreated by migrations.

#### Attempt 2: `_ensure_admin()` in `app.py` via SQLAlchemy
- **What:** Created admin via SQLAlchemy session inside `create_app()`
- **Why it failed:** Gunicorn worker forking caused SQLAlchemy session to not properly commit. INSERT appeared to succeed but was rolled back.

#### Attempt 3: `init_admin.py` with psycopg2 autocommit (CURRENT - WORKS)
- **What:** Direct psycopg2 connection with `autocommit=True`, runs AFTER gunicorn starts
- **Why it works:** No ORM session interference, retries until table exists, verifies after INSERT

### Migration Safety

**Migrations DO NOT destroy data.** Alembic migrations only ALTER tables and CREATE new tables. Existing data is preserved.

The real cause of data loss is **`docker compose down -v`** which removes the Docker volume containing all PostgreSQL data.

## Verified Persistence Scenarios

| Operation | Data Preserved? | Admin Login? | Notes |
|-----------|-----------------|--------------|-------|
| `docker compose stop` → `start` | ✅ Yes | ✅ Works | Volume untouched |
| `docker compose down` → `up -d` | ✅ Yes | ✅ Works | Volume untouched |
| `docker compose down -v` → `up -d` | ✅ Yes* | ✅ Works | Volume recreated, admin auto-created |
| `docker compose up -d --build` | ✅ Yes | ✅ Works | Volume untouched |
| `docker compose restart` | ✅ Yes | ✅ Works | Volume untouched |
| **Apply new migration** | ✅ Yes | ✅ Works | ALTER TABLE preserves data |

*`down -v` removes the volume. All user data is lost, but `init_admin.py` recreates the admin user on startup.

## Implemented Safety Measures

### 1. Pre-Migration Backup
Before any Alembic migration runs, a backup is created:
```python
# In app.py, before command.upgrade()
subprocess.run(['pg_dump', '-U', user, '-d', dbname, '--no-owner', '--no-acl'])
```

### 2. Post-Migration Integrity Check
After migration completes, the system verifies data integrity:
```python
# In app.py, after command.upgrade()
result = conn.execute(text("SELECT COUNT(*) FROM app_user"))
user_count = result.scalar()
data_logger.info(f'Post-migration check: {user_count} users')
```

### 3. Admin Auto-Creation
`init_admin.py` runs on every startup:
- Connects via psycopg2 with autocommit
- Waits for app_user table (up to 60s)
- Creates admin if not exists
- Verifies creation with SELECT

### 4. Volume Protection
- Named volumes: `dwar-rater_postgres_data`, `dwar-rater_postgres_backups`
- Hourly automated backups via cron in PostgreSQL container
- Pre-migration backups before any schema change

## Architecture

```
entrypoint.sh
├── gunicorn app:app &                    ← Background: Flask app
└── python3 init_admin.py                  ← Foreground: Admin creation
    ├── psycopg2.connect(autocommit=True)
    ├── Wait for app_user table (60s max)
    ├── SELECT id FROM app_user WHERE username='admin'
    ├── INSERT if not exists
    ├── SELECT to verify
    └── Exit (gunicorn continues)

app.py (create_app)
├── db.create_all() / Alembic migrations
│   ├── Pre-migration backup (pg_dump)
│   ├── command.upgrade('head')
│   └── Post-migration integrity check
├── RBAC seed (roles, permissions)
└── _ensure_admin() ← REMOVED (was unreliable)
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/entrypoint.sh` | Starts gunicorn in background, runs init_admin.py |
| `backend/init_admin.py` | Bulletproof admin creation with psycopg2 autocommit + retry |
| `backend/app.py` | Flask app with pre/post migration safety checks |
| `docker-compose.yml` | Named volume configuration |
| `scripts/db-backup.sh` | Hourly automated backup (cron) |
| `scripts/pre-migration-backup.sh` | Manual pre-migration backup script |
| `scripts/docker-safe.sh` | Wrapper that prevents accidental `down -v` |

## What NOT to Do

1. **Never** create admin via SQLAlchemy in `create_app()` — session issues with gunicorn
2. **Never** create admin BEFORE migrations — table will be recreated
3. **Never** use `docker compose down -v` in production — destroys all data
4. **Never** use `db.session.commit()` in entrypoint scripts — no app context

## What TO Do

1. Use direct psycopg2 connection with `autocommit=True` for admin creation
2. Run admin creation AFTER gunicorn has started
3. Retry until table exists and admin is verified
4. Keep admin creation separate from the Flask app
5. Use `docker compose stop/start` or `docker compose down/up` (without `-v`)
6. Always check backups before running migrations

## Migration Workflow (Safe)

```bash
# 1. Create backup manually (optional, auto-backup runs before migration)
docker exec dwar_rater_postgres /usr/local/bin/db-backup.sh

# 2. Check current state
docker exec dwar_rater_postgres psql -U dwar -d dwar_rater -c "SELECT count(*) FROM app_user;"

# 3. Apply migration (rebuild backend)
docker compose up -d --build backend

# 4. Verify data preserved
docker exec dwar_rater_postgres psql -U dwar -d dwar_rater -c "SELECT count(*) FROM app_user;"

# 5. Check logs for pre-migration backup and integrity check
docker logs dwar-rater-backend-1 | grep -i "migration\|backup\|integrity"
```

## Emergency Recovery

If data is lost:

```bash
# 1. List available backups
docker exec dwar_rater_postgres ls -lh /backups/

# 2. Restore from latest backup
LATEST=$(docker exec dwar_rater_postgres ls -t /backups/dwar_rater_backup_*.sql.gz | head -1)
docker exec -i dwar_rater_postgres sh -c "gunzip -c $LATEST | psql -U dwar -d dwar_rater"

# 3. Or use make restore
make restore
```
