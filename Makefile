# Dwar Rater — Safe Operations Makefile
#
# Usage:
#   make start        — Start all containers
#   make stop         — Stop containers (safe, keeps data)
#   make restart      — Restart containers (safe)
#   make backup       — Create database backup
#   make migrate      — Run Alembic migrations (with auto-backup)
#   make destroy      — Destroy everything (requires confirmation)
#   make status       — Show container and database status
#   make logs         — Show backend logs

.PHONY: start stop restart backup migrate destroy status logs

start:
	docker compose up -d

stop:
	docker compose stop

restart:
	docker compose restart

backup:
	@echo "Creating backup..."
	docker exec dwar_rater_postgres /usr/local/bin/db-backup.sh
	@echo ""
	@echo "Backups:"
	@docker exec dwar_rater_postgres ls -lh /backups/ 2>/dev/null || echo "  No backups found"

migrate:
	@echo "Running safe migration (with pre-migration backup)..."
	bash scripts/alembic-safe.sh upgrade head

status:
	@echo "=== Container Status ==="
	@docker compose ps
	@echo ""
	@echo "=== Database ==="
	@docker exec dwar_rater_postgres psql -U dwar -d dwar_rater -c "SELECT 'Tables' as metric, COUNT(*) as value FROM pg_tables WHERE schemaname='public' UNION ALL SELECT 'Backups', COUNT(*) FROM (SELECT 1 FROM pg_stat_file('/backups') LIMIT 0) t;" 2>/dev/null || echo "  DB not accessible"
	@echo ""
	@echo "=== Backup Volume ==="
	@docker exec dwar_rater_postgres ls -lh /backups/ 2>/dev/null || echo "  No backups"

logs:
	docker logs dwar-rater-backend-1 --tail 50 -f

destroy:
	@echo "=== WARNING: This will destroy ALL data ==="
	@echo ""
	@echo "Checking safety..."
	@bash scripts/pre-destroy-check.sh || (echo "" && echo "Aborted. Safety check failed." && exit 1)
	@echo ""
	@read -p "Type 'DESTROY' to confirm: " confirm; \
	if [ "$$confirm" != "DESTROY" ]; then \
		echo "Aborted."; \
		exit 1; \
	fi
	@echo "Destroying..."
	docker compose down -v
