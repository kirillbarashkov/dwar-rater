#!/bin/bash
#
# Safe Docker Compose wrapper
# Prevents accidental data loss from `docker compose down -v`
#
# Usage:
#   ./scripts/docker-safe.sh up -d
#   ./scripts/docker-safe.sh down
#   ./scripts/docker-safe.sh down -v    # requires confirmation + backup check
#

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${PROJECT_DIR}/.env"

# Check if -v flag is present
if echo "$*" | grep -q "\-v"; then
    echo "=== SAFE DOCKER COMPOSE: Destructive operation detected ==="
    echo ""
    
    # Check ALLOW_VOLUME_DESTRUCTION flag
    if [ -f "$ENV_FILE" ]; then
        ALLOW=$(grep -E '^ALLOW_VOLUME_DESTRUCTION=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'" || echo "false")
        if [ "$ALLOW" != "true" ]; then
            echo "[BLOCKED] ALLOW_VOLUME_DESTRUCTION is not set to 'true' in .env"
            echo ""
            echo "To allow volume destruction:"
            echo "  1. Create a backup: docker exec dwar_rater_postgres /usr/local/bin/db-backup.sh"
            echo "  2. Set ALLOW_VOLUME_DESTRUCTION=true in .env"
            echo "  3. Run: $0 $*"
            echo ""
            echo "Or run directly (not recommended): docker compose $*"
            exit 1
        fi
    fi
    
    # Check if database has data
    if docker ps --format '{{.Names}}' | grep -q dwar_rater_postgres; then
        ROW_COUNT=$(docker exec dwar_rater_postgres psql -U dwar -d dwar_rater -t -c "SELECT COALESCE(SUM(n_live_tup), 0) FROM pg_stat_user_tables;" 2>/dev/null | tr -d ' ' || echo "0")
        
        if [ "$ROW_COUNT" -gt 0 ]; then
            echo "[WARNING] Database has ~$ROW_COUNT rows"
            echo ""
            read -p "Are you sure you want to destroy the volume? Type 'YES' to confirm: " confirm
            if [ "$confirm" != "YES" ]; then
                echo "Aborted."
                exit 1
            fi
        fi
    fi
    
    echo "[PROCEEDING] Volume destruction allowed"
fi

# Execute docker compose with all arguments
cd "$PROJECT_DIR"
docker compose "$@"
