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
#   make fe           — Rebuild only the frontend container
#   make be           — Rebuild only the backend container

.PHONY: start stop restart backup migrate destroy status logs restore fe be

# A25: значения из .env, а не хардкод «-U dwar -d dwar_rater».
PG_USER := $(shell sed -n 's/^POSTGRES_USER=//p' .env 2>/dev/null | head -1)
PG_DB := $(shell sed -n 's/^POSTGRES_DB=//p' .env 2>/dev/null | head -1)
PG_USER := $(if $(PG_USER),$(PG_USER),dwar)
PG_DB := $(if $(PG_DB),$(PG_DB),dwar_rater)

start:
	docker compose up -d

# Пересборка ТОЛЬКО изменённого сервиса (TD-4): полная сборка backend+frontend ~13
# минут, а правится обычно один — гонять оба незачем.
fe:
	@echo "Rebuilding frontend only..."
	docker compose build frontend && docker compose up -d frontend
	@echo "Frontend rebuilt. Hard-refresh the browser (Ctrl+F5)."

be:
	@echo "Rebuilding backend only..."
	docker compose build backend && docker compose up -d backend
	@echo "Backend rebuilt."

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
	@docker compose exec -T postgres psql -U "$(PG_USER)" -d "$(PG_DB)" -c "\
	  SELECT 'Tables' AS metric, COUNT(*)::text AS value FROM pg_tables WHERE schemaname='public' \
	  UNION ALL SELECT 'Users', COUNT(*)::text FROM app_user \
	  UNION ALL SELECT 'Backups (sql.gz)', COUNT(*)::text FROM pg_ls_dir('/backups') AS f(name) WHERE name LIKE '%.sql.gz'"
	@echo ""
	@echo "=== Backup Volume ==="
	@docker compose exec -T postgres ls -lh /backups/ 2>/dev/null | tail -5 || echo "  No backups"

logs:
	docker logs dwar-rater-backend-1 --tail 50 -f

restore:
	@echo "=== Restore from latest backup ==="
	@LATEST=$$(docker compose exec -T postgres ls -t /backups/dwar_rater_backup_*.sql.gz 2>/dev/null | head -1); \
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
	docker compose exec -T postgres sh -c "gunzip -c $$LATEST | psql -U $(PG_USER) -d $(PG_DB)"; \
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
