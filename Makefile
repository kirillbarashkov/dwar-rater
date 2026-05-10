# Dwar Rater — Safe Operations Makefile
#
# Usage:
#   make start        — Start all containers
#   make stop         — Stop containers (safe, keeps data)
#   make restart      — Restart containers (safe)
#   make backup       — Create database backup
#   make migrate      — Run Alembic migrations (with auto-backup)
#   make destroy      — Destroy everything (requires confirmation + backup)
#   make status       — Show container and database status
#   make logs         — Show backend logs
#   make restore      — Restore from latest backup

.PHONY: start stop restart backup migrate destroy status logs restore

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

restore:
	@echo "=== Restore from latest backup ==="
	@LATEST=$$(docker exec dwar_rater_postgres ls -t /backups/dwar_rater_backup_*.sql.gz 2>/dev/null | head -1); \
	if [ -z "$$LATEST" ]; then \
		echo "No backups found!"; \
		exit 1; \
	fi; \
	echo "Latest backup: $$LATEST"; \
	read -p "Restore from this backup? Type 'YES' to confirm: " confirm; \
	if [ "$$confirm" != "YES" ]; then \
		echo "Aborted."; \
		exit 1; \
	fi; \
	echo "Restoring..."; \
	docker exec dwar_rater_postgres sh -c "gunzip -c $$LATEST | psql -U dwar -d dwar_rater"; \
	echo "Restore complete"

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
