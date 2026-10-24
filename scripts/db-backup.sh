#!/bin/bash
# PostgreSQL backup script — runs inside the container via cron
# Creates timestamped dumps, проверяет целостность и ротирует старые (A13).

# pipefail обязателен: без него `$?` после пайпа `pg_dump | gzip` — это код
# возврата gzip, поэтому упавший pg_dump (битый дамп) проходил как успешный.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-0}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="dwar_rater_backup_${TIMESTAMP}.sql.gz"
FILEPATH="${BACKUP_DIR}/${FILENAME}"

echo "[$(date)] Starting backup: ${FILENAME}"

# Create backup. Проверка через `if !` — при set -e + pipefail пайплайн
# завершит скрипт раньше, чем дойдёт до `$?`, и обрезанный файл остался бы
# лежать в каталоге бэкапов как «валидный».
if ! pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --no-owner --no-acl | gzip > "${FILEPATH}"; then
    echo "[$(date)] Backup FAILED (pg_dump or gzip)"
    rm -f "${FILEPATH}"
    exit 1
fi

SIZE=$(du -h "${FILEPATH}" | cut -f1)
echo "[$(date)] Backup created: ${SIZE}"

# Проверка целостности: обрезанный gzip — это тоже провал, просто заметный
# позже, когда бэкап понадобится.
if ! gunzip -t "${FILEPATH}" 2>/dev/null; then
    echo "[$(date)] Backup FAILED: gzip integrity check"
    rm -f "${FILEPATH}"
    exit 1
fi

# A13: ротация старых дампов. Значение читается из BACKUP_KEEP_DAYS;
# при пустом/неверном/нулевом скрипт ротации сам откажется что-либо удалять.
ROTATE_SCRIPT="$(dirname "$0")/backup-rotate.sh"
# Запуск через bash, а не как исполняемый файл: на Windows git не хранит
# бит исполнения, и проверка -x молча отключила бы ротацию.
if [ -f "${ROTATE_SCRIPT}" ]; then
    bash "${ROTATE_SCRIPT}" "${BACKUP_DIR}" "${KEEP_DAYS}" \
        || echo "[$(date)] Rotation skipped (exit $?)"
else
    echo "[$(date)] Rotation skipped: ${ROTATE_SCRIPT} not found"
fi

echo "[$(date)] Backup complete"
