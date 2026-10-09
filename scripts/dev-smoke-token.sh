#!/usr/bin/env bash
# One-off session token for dev smoke checks (never for prod).
#
# Why this exists: the documented recipe lived only in the project skill, so every
# long smoke session re-typed it — and got bitten by it twice (a 1-hour token dies
# between smokes and the UI silently redirects to /login, which reads as a broken
# frontend). Creating the token through a file also avoids `psql -c` shell-escaping.
#
# Usage:
#   scripts/dev-smoke-token.sh create [name] [hours]   # default: smoke 3
#   scripts/dev-smoke-token.sh drop   [name]
#   scripts/dev-smoke-token.sh list
#
# The DB stores ONLY sha256(name); the raw name is what goes into the request:
#   localStorage.setItem('auth_token', '<name>')
#   curl -H 'Authorization: Bearer <name>' ...
set -euo pipefail

ACTION="${1:-create}"
TOKEN="${2:-smoke}"
HOURS="${3:-3}"

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "error: .env not found — run from the project repo (needs POSTGRES_USER/POSTGRES_PASSWORD)" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

DB="${POSTGRES_DB:-dwar_rater}"

if [[ -z "${POSTGRES_USER:-}" || -z "${POSTGRES_PASSWORD:-}" ]]; then
  echo "error: POSTGRES_USER / POSTGRES_PASSWORD are not set in .env" >&2
  exit 1
fi

psql_run() {
  docker compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" postgres \
    psql -U "$POSTGRES_USER" -d "$DB" -v ON_ERROR_STOP=1 "$@"
}

case "$ACTION" in
  create)
    if ! [[ "$HOURS" =~ ^[0-9]+$ ]] || [[ "$HOURS" -lt 1 ]]; then
      echo "error: hours must be a positive integer" >&2
      exit 1
    fi
    # DELETE + INSERT on purpose: ON CONFLICT DO NOTHING would keep a row whose
    # expiry has already passed, and the token would look created but be dead.
    psql_run <<SQL
DELETE FROM session_token WHERE token_hash = encode(sha256('${TOKEN}'::bytea), 'hex');

INSERT INTO session_token (user_id, token_hash, expires_at)
SELECT u.id, encode(sha256('${TOKEN}'::bytea), 'hex'), NOW() + INTERVAL '${HOURS} hour'
FROM app_user u JOIN role r ON r.id = u.role_id
WHERE r.name = 'admin' ORDER BY u.id LIMIT 1;

SELECT count(*) AS active_tokens FROM session_token
WHERE token_hash = encode(sha256('${TOKEN}'::bytea), 'hex') AND expires_at > NOW();
SQL
    echo
    echo "ready: Authorization: Bearer ${TOKEN}  (valid ${HOURS}h)"
    echo "browser: localStorage.setItem('auth_token', '${TOKEN}')"
    ;;
  drop)
    psql_run <<SQL
DELETE FROM session_token WHERE token_hash = encode(sha256('${TOKEN}'::bytea), 'hex');
SQL
    echo "dropped: ${TOKEN}"
    ;;
  list)
    psql_run <<'SQL'
SELECT u.username, left(t.token_hash, 12) AS hash, t.expires_at,
       (t.expires_at > NOW()) AS active
FROM session_token t LEFT JOIN app_user u ON u.id = t.user_id
ORDER BY t.expires_at DESC LIMIT 10;
SQL
    ;;
  *)
    echo "usage: $0 {create|drop|list} [name] [hours]" >&2
    exit 1
    ;;
esac
