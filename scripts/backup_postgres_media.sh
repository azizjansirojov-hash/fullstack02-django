#!/usr/bin/env bash
# Backup Postgres + media for Libro.UZ bookstore.
# Usage (from repo root, with compose running):
#   ./scripts/backup_postgres_media.sh
# Env: COMPOSE_ENV_FILE (default backend/.env), BACKUP_DIR (default ./backups)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${COMPOSE_ENV_FILE:-$ROOT/backend/.env}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/$STAMP"
mkdir -p "$OUT"

echo "Backing up to $OUT"

# Postgres dump via the db container
docker compose --env-file "$ENV_FILE" exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "$OUT/postgres.dump"

# Media volume: copy from the web container
docker compose --env-file "$ENV_FILE" exec -T web \
  tar -C /app/backend/media -czf - . \
  > "$OUT/media.tar.gz"

echo "Done."
echo "Restore Postgres:"
echo "  docker compose --env-file $ENV_FILE exec -T db pg_restore -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" --clean --if-exists < $OUT/postgres.dump"
echo "Restore media (destructive to current media):"
echo "  docker compose --env-file $ENV_FILE exec -T web tar -C /app/backend/media -xzf - < $OUT/media.tar.gz"
