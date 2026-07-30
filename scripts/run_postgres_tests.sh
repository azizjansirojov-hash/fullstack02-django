#!/usr/bin/env bash
# Run Postgres-only Django tests inside Docker Compose (GenerationJob race, etc.)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
docker compose --env-file backend/.env up -d db redis migrate web
docker compose --env-file backend/.env exec web python manage.py test \
  library.generation_tests.GenerationJobConcurrentEnqueueTests \
  --verbosity=2
