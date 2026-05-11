#!/bin/bash
# Pre-migration backup script
# Runs BEFORE any Alembic migration to ensure data can be recovered

set -e

BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="pre_migration_${TIMESTAMP}.sql.gz"
FILEPATH="${BACKUP_DIR}/${FILENAME}"

echo "[$(date)] Pre-migration backup starting..."

mkdir -p "$BACKUP_DIR"

# Create backup
pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --no-owner --no-acl | gzip > "${FILEPATH}"

if [ $? -eq 0 ]; then
    SIZE=$(du -h "${FILEPATH}" | cut -f1)
    echo "[$(date)] Pre-migration backup created: ${FILENAME} (${SIZE})"
else
    echo "[$(date)] WARNING: Pre-migration backup failed!"
    rm -f "${FILEPATH}"
fi

echo "[$(date)] Pre-migration backup complete"
