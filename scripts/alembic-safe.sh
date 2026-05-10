#!/bin/bash
# Alembic wrapper — creates a backup BEFORE applying migrations.
# If migration fails, offers restore from the pre-migration backup.
#
# Usage:
#   ./scripts/alembic-safe.sh upgrade head
#   ./scripts/alembic-safe.sh downgrade -1

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="${PROJECT_DIR}/backend"

echo "=== Alembic Safe Migration ==="
echo ""

# Pre-migration backup
echo "[1/3] Creating pre-migration backup..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKEND_DIR}/instance/pre_migration_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKEND_DIR}/instance"

# Try Docker first, then direct psql
if docker ps --format '{{.Names}}' | grep -q dwar_rater_postgres; then
    docker exec dwar_rater_postgres pg_dump \
        -U "${POSTGRES_USER:-dwar}" \
        -d "${POSTGRES_DB:-dwar_rater}" \
        --no-owner --no-acl | gzip > "$BACKUP_FILE"
else
    # Fallback: direct psql if running locally
    PGPASSWORD="${POSTGRES_PASSWORD:-change-me-in-production}" pg_dump \
        -h "${POSTGRES_HOST:-localhost}" \
        -p "${POSTGRES_PORT:-5432}" \
        -U "${POSTGRES_USER:-dwar}" \
        -d "${POSTGRES_DB:-dwar_rater}" \
        --no-owner --no-acl | gzip > "$BACKUP_FILE"
fi

if [ $? -eq 0 ] && [ -s "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "  Backup created: $(basename "$BACKUP_FILE") ($SIZE)"
else
    echo "  [WARNING] Backup failed or empty, continuing without backup"
    rm -f "$BACKUP_FILE"
    BACKUP_FILE=""
fi

echo ""
echo "[2/3] Running migration: alembic $@"

# Run alembic
cd "$BACKEND_DIR"
if ! alembic "$@"; then
    echo ""
    echo "[FAILED] Migration failed!"

    if [ -n "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
        echo ""
        echo "[3/3] Restoring from pre-migration backup..."
        if docker ps --format '{{.Names}}' | grep -q dwar_rater_postgres; then
            gunzip -c "$BACKUP_FILE" | docker exec -i dwar_rater_postgres psql \
                -U "${POSTGRES_USER:-dwar}" \
                -d "${POSTGRES_DB:-dwar_rater}"
        else
            gunzip -c "$BACKUP_FILE" | PGPASSWORD="${POSTGRES_PASSWORD:-change-me-in-production}" psql \
                -h "${POSTGRES_HOST:-localhost}" \
                -p "${POSTGRES_PORT:-5432}" \
                -U "${POSTGRES_USER:-dwar}" \
                -d "${POSTGRES_DB:-dwar_rater}"
        fi
        echo "  Database restored from $(basename "$BACKUP_FILE")"
    else
        echo "  No backup available for restore."
    fi
    exit 1
fi

echo ""
echo "[3/3] Migration completed successfully"
echo "  Pre-migration backup kept at: $BACKUP_FILE"
echo "  To restore if needed: gunzip -c $BACKUP_FILE | psql -U dwar -d dwar_rater"
