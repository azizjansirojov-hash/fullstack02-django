#!/usr/bin/env bash
# One-time rename of Compose Postgres database/user from legacy "luma" → "libro".
# Run from the repo root with Compose already configured for the OLD names.
#
# Usage:
#   chmod +x scripts/rename_postgres_luma_to_libro.sh
#   ./scripts/rename_postgres_luma_to_libro.sh
#
# Prerequisites:
#   - docker compose stack can start with POSTGRES_* still set to luma
#   - You have enough disk for a dump under ./backups/
#   - You will update backend/.env to POSTGRES_DB=libro / POSTGRES_USER=libro afterward
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p backups
STAMP="$(date +%Y%m%d_%H%M%S)"
DUMP="backups/luma_to_libro_${STAMP}.sql"

echo "==> Dumping database 'luma' via compose service db ..."
docker compose --env-file backend/.env exec -T db \
  pg_dump -U luma -d luma --no-owner --no-acl > "$DUMP"
echo "    Wrote $DUMP"

echo "==> Stopping app services (keep volumes) ..."
docker compose --env-file backend/.env stop web worker migrate || true

echo "==> Renaming database inside Postgres (connected to maintenance DB) ..."
docker compose --env-file backend/.env exec -T db \
  psql -U luma -d postgres -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'luma' AND pid <> pg_backend_pid();
ALTER DATABASE luma RENAME TO libro;
SQL

echo "==> Creating role 'libro' (if missing) and transferring ownership ..."
# Password must match POSTGRES_PASSWORD you will put in .env — prompt via env.
: "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in the environment to the current DB password}"
docker compose --env-file backend/.env exec -T db \
  psql -U luma -d postgres -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'libro') THEN
    CREATE ROLE libro LOGIN PASSWORD '${POSTGRES_PASSWORD}';
  END IF;
END
\$\$;
ALTER DATABASE libro OWNER TO libro;
GRANT ALL PRIVILEGES ON DATABASE libro TO libro;
SQL

echo "==> Reassigning schema ownership inside libro ..."
docker compose --env-file backend/.env exec -T db \
  psql -U luma -d libro -v ON_ERROR_STOP=1 <<'SQL'
REASSIGN OWNED BY luma TO libro;
GRANT ALL ON SCHEMA public TO libro;
SQL

echo ""
echo "DONE (data side)."
echo "Next steps (manual):"
echo "  1. Edit backend/.env:"
echo "       POSTGRES_DB=libro"
echo "       POSTGRES_USER=libro"
echo "       # POSTGRES_PASSWORD unchanged (or updated to match CREATE ROLE)"
echo "  2. docker compose --env-file backend/.env up -d"
echo "  3. Verify: docker compose exec db psql -U libro -d libro -c '\\dt'"
echo ""
echo "Rollback dump is at: $DUMP"
echo "If rename fails mid-flight, restore with:"
echo "  docker compose exec -T db psql -U luma -d postgres -c \"CREATE DATABASE luma_restore;\""
echo "  docker compose exec -T db psql -U luma -d luma_restore < $DUMP"
