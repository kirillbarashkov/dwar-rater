#!/bin/bash
# Create admin user in PostgreSQL if not exists
# Runs after database is initialized

set -e

ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-change-me-in-production}"

# Generate bcrypt hash
HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw('${ADMIN_PASS}'.encode(), bcrypt.gensalt()).decode())")

# Insert admin user if not exists
docker exec dwar_rater_postgres psql -U dwar -d dwar_rater -c "
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM app_user WHERE username = '${ADMIN_USER}') THEN
        INSERT INTO app_user (username, password_hash, role, is_active, must_change_password, created_at)
        VALUES ('${ADMIN_USER}', '${HASH}', 'admin', true, false, NOW());
        RAISE NOTICE 'Admin user created: ${ADMIN_USER}';
    ELSE
        RAISE NOTICE 'Admin user already exists: ${ADMIN_USER}';
    END IF;
END \$\$;
"
