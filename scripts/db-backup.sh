#!/bin/bash
# PostgreSQL backup script — runs inside the container via cron
# Creates timestamped dumps with retention policy

set -e

BACKUP_DIR="/backups"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="dwar_rater_backup_${TIMESTAMP}.sql.gz"
FILEPATH="${BACKUP_DIR}/${FILENAME}"

echo "[$(date)] Starting backup: ${FILENAME}"

# Create backup
pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --no-owner --no-acl | gzip > "${FILEPATH}"

if [ $? -eq 0 ]; then
    SIZE=$(du -h "${FILEPATH}" | cut -f1)
    echo "[$(date)] Backup created: ${SIZE}"
else
    echo "[$(date)] Backup FAILED"
    rm -f "${FILEPATH}"
    exit 1
fi

# Cleanup old backups
echo "[$(date)] Cleaning up backups older than ${RETENTION_DAYS} days"
find "${BACKUP_DIR}" -name "dwar_rater_backup_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

echo "[$(date)] Backup complete"
