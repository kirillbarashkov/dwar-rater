#!/bin/bash
# Pre-destroy check — prevents accidental data loss before docker compose down -v
# Run this BEFORE any destructive Docker operation.
#
# Usage:
#   ./scripts/pre-destroy-check.sh
#
# If ALLOW_VOLUME_DESTRUCTION=true in .env, skips all checks.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_DIR}/.env"

echo "=== Pre-Destroy Safety Check ==="
echo ""

# Check 0: Override flag
if [ -f "$ENV_FILE" ]; then
    ALLOW_DESTRUCTION=$(grep -E '^ALLOW_VOLUME_DESTRUCTION=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'" || echo "false")
    if [ "$ALLOW_DESTRUCTION" = "true" ]; then
        echo "[SKIP] ALLOW_VOLUME_DESTRUCTION=true — all checks bypassed"
        exit 0
    fi
fi

echo "[CHECK 1] ALLOW_VOLUME_DESTRUCTION is not true (default: false)"

# Check 2: Is PostgreSQL running with data?
echo ""
echo "[CHECK 2] Checking PostgreSQL for existing data..."

DB_COUNT=$(docker exec dwar_rater_postgres psql -U "${POSTGRES_USER:-dwar}" -d "${POSTGRES_DB:-dwar_rater}" -t -c "
SELECT COUNT(*) FROM (
    SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'public'
) t;
" 2>/dev/null | tr -d ' ' || echo "0")

if [ "$DB_COUNT" -gt 0 ]; then
    TABLE_COUNT=$(docker exec dwar_rater_postgres psql -U "${POSTGRES_USER:-dwar}" -d "${POSTGRES_DB:-dwar_rater}" -t -c "
    SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';
    " 2>/dev/null | tr -d ' ' || echo "0")

    ROW_COUNT=$(docker exec dwar_rater_postgres psql -U "${POSTGRES_USER:-dwar}" -d "${POSTGRES_DB:-dwar_rater}" -t -c "
    SELECT SUM(n_live_tup) FROM pg_stat_user_tables;
    " 2>/dev/null | tr -d ' ' || echo "0")

    echo "  Tables: $TABLE_COUNT"
    echo "  Estimated rows: $ROW_COUNT"

    if [ "$ROW_COUNT" -gt 0 ]; then
        echo "  [BLOCKED] Database has $ROW_COUNT rows across $TABLE_COUNT tables!"
        echo "  Run a backup first: docker exec dwar_rater_postgres /usr/local/bin/db-backup.sh"
        echo "  Or set ALLOW_VOLUME_DESTRUCTION=true in .env to bypass."
        exit 1
    else
        echo "  [OK] Database has tables but no data"
    fi
else
    echo "  [OK] No tables found in database"
fi

# Check 3: Is there a recent backup?
echo ""
echo "[CHECK 3] Checking for recent backups..."

BACKUP_COUNT=$(docker exec dwar_rater_postgres find /backups -name "dwar_rater_backup_*.sql.gz" 2>/dev/null | wc -l | tr -d ' ')

if [ "$BACKUP_COUNT" -eq 0 ]; then
    echo "  [WARNING] No backups found in /backups volume"
    echo "  Consider creating one: docker exec dwar_rater_postgres /usr/local/bin/db-backup.sh"
    echo ""
    read -p "Continue anyway? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "Aborted."
        exit 1
    fi
else
    LATEST=$(docker exec dwar_rater_postgres ls -t /backups/dwar_rater_backup_*.sql.gz 2>/dev/null | head -1)
    if [ -n "$LATEST" ]; then
        LATEST_DATE=$(docker exec dwar_rater_postgres stat -c %Y "$LATEST" 2>/dev/null || echo "0")
        NOW=$(date +%s)
        AGE_HOURS=$(( (NOW - LATEST_DATE) / 3600 ))
        echo "  Latest backup: $(basename "$LATEST") ($AGE_HOURS hours ago)"
        if [ "$AGE_HOURS" -gt 24 ]; then
            echo "  [WARNING] Latest backup is older than 24 hours"
        else
            echo "  [OK] Recent backup exists"
        fi
    fi
fi

echo ""
echo "=== All checks passed ==="
echo "You can safely run: docker compose down -v"
