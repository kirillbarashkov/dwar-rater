#!/bin/bash
# A13: ротация резервных копий PostgreSQL.
#
# Usage: backup-rotate.sh <backup_dir> <keep_days> [--dry-run]
#
# Отдельный скрипт, а не блок внутри db-backup.sh, потому что он УДАЛЯЕТ файлы —
# такую логику надо уметь проверить в изоляции (см.
# backend/tests/test_backup_rotation.py), не поднимая базу.
#
# Защиты (каждая важна — ошибка здесь стоит всех бэкапов):
#   * удаляются только файлы вида dwar_rater_backup_*.sql.gz в самом каталоге
#     (без рекурсии) — чужие файлы и подкаталоги не трогаются;
#   * keep_days обязан быть целым > 0; пустое, нечисловое или 0/отрицательное
#     значение ВЫКЛЮЧАЕТ ротацию, а не «удаляет всё»;
#   * --dry-run только печатает, что было бы удалено.

set -euo pipefail

BACKUP_DIR="${1:-}"
KEEP_DAYS="${2:-0}"
DRY_RUN="${3:-}"

if [ -z "${BACKUP_DIR}" ]; then
    echo "usage: backup-rotate.sh <backup_dir> <keep_days> [--dry-run]" >&2
    exit 2
fi

if [ ! -d "${BACKUP_DIR}" ]; then
    echo "rotate: каталог не найден: ${BACKUP_DIR}" >&2
    exit 2
fi

if ! [[ "${KEEP_DAYS}" =~ ^[0-9]+$ ]] || [ "${KEEP_DAYS}" -le 0 ]; then
    echo "rotate: ротация выключена (keep_days='${KEEP_DAYS}')"
    exit 0
fi

removed=0
while IFS= read -r -d '' old; do
    if [ "${DRY_RUN}" = "--dry-run" ]; then
        echo "rotate: было бы удалено: $(basename "${old}")"
    else
        echo "rotate: удаляю старое: $(basename "${old}")"
        rm -f -- "${old}"
    fi
    removed=$((removed + 1))
done < <(find "${BACKUP_DIR}" -maxdepth 1 -type f \
              -name 'dwar_rater_backup_*.sql.gz' \
              -mtime "+${KEEP_DAYS}" -print0)

echo "rotate: под удаление попало ${removed} файл(ов), порог ${KEEP_DAYS} дн."
