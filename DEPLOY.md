# DEPLOY.md — Libro.UZ production & Docker

## Stack

| Service | Role |
|---------|------|
| `web` | Gunicorn — SPA (`FRONTEND_DIST`) + APIs + gated media |
| `worker` | `process_generation_jobs --loop` (PDF/TTS) — **required** |
| `db` | Postgres 16 |
| `redis` | Cache + DRF throttle counters (required when `DEBUG=False`; password required) |
| `migrate` | One-shot migrate before web/worker |

## Quick Compose

```bash
cp backend/.env.example backend/.env
# Set strong SECRET_KEY, POSTGRES_PASSWORD, and REDIS_PASSWORD (not placeholders)
# POSTGRES_DB / POSTGRES_USER defaults are now "libro" (was "luma")

docker compose --env-file backend/.env up --build
```

Open **http://127.0.0.1:8000/library** — React SPA.

Local Compose smoke tests may set `USE_TLS=0` and explicitly `ALLOW_CONSOLE_EMAIL=1` with `ENVIRONMENT=staging`.
**Production:** set `ALLOW_CONSOLE_EMAIL=0` (or omit) and configure SMTP. Never enable console email in production. Django refuses to boot with a console email backend when `DEBUG=False` unless `ALLOW_CONSOLE_EMAIL=1` **and** `ENVIRONMENT=staging`.

### Host port binding

Compose publishes `web` as **`127.0.0.1:8000:8000`** (loopback only). The process still listens on `0.0.0.0` *inside* the container so the TLS nginx overlay can reach `web:8000` on the Docker network.

To intentionally expose the app on the LAN (not recommended without a reverse proxy):

```yaml
# override in a local compose fragment
ports:
  - "8000:8000"   # all interfaces
```

## Environment variable checklist

Copy from [`backend/.env.example`](backend/.env.example). Do **not** commit real `.env` secrets.

| Variable | Notes |
|----------|--------|
| `SECRET_KEY` | Required; long random string |
| `DEBUG` | `False` in production |
| `ALLOWED_HOSTS` | Hostnames for the site |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Compose DB (defaults **`libro`**) |
| `DATABASE_URL` | Built by Compose from `POSTGRES_*` |
| `REDIS_PASSWORD` | Required for Compose Redis `--requirepass` |
| `REDIS_URL` | **Required when `DEBUG=False`**; Compose sets `redis://:${REDIS_PASSWORD}@redis:6379/1` |
| `FRONTEND_DIST` | Path to built SPA (`/app/frontend/dist` in Docker) |
| `CSRF_TRUSTED_ORIGINS` | HTTPS origins of the SPA |
| `DEFAULT_FROM_EMAIL` | Password-reset From address |
| `EMAIL_*` | SMTP for real delivery; console backend prints links locally |
| `ALLOW_CONSOLE_EMAIL` | **Must be `0` / unset in production** |
| `ENVIRONMENT` | Use `staging` only with console email smoke tests; production should omit or use `production` |
| `SPA_ORIGIN` | Absolute SPA origin for emails/redirects in Vite+Django local dev; empty/`same` = relative |
| `TTS_PROVIDER` | Default `edge` (see `ARCHITECTURE.md` TTS risk) |
| `USE_TLS` | `1` behind HTTPS terminator |

## Database migrations

Compose runs a one-shot `migrate` service before `web` / `worker`. For manual deploys:

```bash
# Inside the app image / backend venv:
cd backend
python manage.py migrate --noinput
python manage.py collectstatic --noinput   # if serving static outside the image build path
```

Verify plan before applying on production-like data:

```bash
python manage.py migrate --plan
python manage.py makemigrations --check --dry-run
```

### One-time Postgres rename (`luma` → `libro`)

If an existing volume still uses database/user **`luma`**, do **not** only change `.env` — update the database first:

```bash
chmod +x scripts/rename_postgres_luma_to_libro.sh
POSTGRES_PASSWORD='your-current-password' ./scripts/rename_postgres_luma_to_libro.sh
# Then set POSTGRES_DB=libro and POSTGRES_USER=libro in backend/.env and recreate app containers.
```

Alternative (fresh volume — data loss):

```bash
docker compose --env-file backend/.env down
# After updating .env to libro / libro:
docker volume rm fullstack02-django_postgres_data   # name may vary — check `docker volume ls`
docker compose --env-file backend/.env up --build
```

## Redis (production)

When `DEBUG=False`, Django **requires** `REDIS_URL` (shared cache for DRF throttles and regenerate quotas across Gunicorn workers). Compose sets Redis with `--requirepass` from `REDIS_PASSWORD`. Do not run multi-worker production on LocMemCache.

## TLS setup

Local HTTPS overlay (certs are **gitignored** — never commit `*.crt` / `*.key`):

```bash
bash deploy/generate_selfsigned_cert.sh
docker compose --env-file backend/.env \
  -f docker-compose.yml -f deploy/docker-compose.tls.yml up -d --build
```

See [`deploy/docker-compose.tls.yml`](deploy/docker-compose.tls.yml), [`deploy/nginx.local.conf`](deploy/nginx.local.conf), and [`deploy/nginx.conf`](deploy/nginx.conf). Production should use a real certificate (Let's Encrypt / load balancer), not the self-signed local material.

## SMTP / email

- Local/dev: console backend prints password-reset links in the process log.
- Staging smoke with `DEBUG=False`: only with `ALLOW_CONSOLE_EMAIL=1` and `ENVIRONMENT=staging`.
- Production: real SMTP (`EMAIL_HOST_*`), `ALLOW_CONSOLE_EMAIL=0`. Confirm reset links open `/password-reset/<uid>/<token>/` (SPA).

## Backups

Use [`scripts/backup_postgres_media.sh`](scripts/backup_postgres_media.sh) with Compose running:

```bash
chmod +x scripts/backup_postgres_media.sh
./scripts/backup_postgres_media.sh
# Writes backups/<UTC-stamp>/postgres.dump and media.tar.gz
```

Restore hints are printed by the script (`pg_restore` + media `tar` extract). Store backups off the app host.

## Rollback plan

1. **Before deploy:** take a backup (`scripts/backup_postgres_media.sh`) and note the running image/tag or git SHA.
2. **App-only rollback:** redeploy the previous image/SHA; keep the same DB volume if migrations were not applied.
3. **If migrations already ran:** restore Postgres from the pre-deploy `postgres.dump`, then redeploy the previous app image. Restore media from `media.tar.gz` if media schema/files diverged.
4. **Compose tip:** pin image digests or git tags in your deploy pipeline so rollback is a known artifact, not “latest”.
5. **Smoke after rollback:** `/library/`, login, `/health/generation/`, and one gated media URL.

## Production checklist

- [ ] Strong `SECRET_KEY`, Postgres password, and `REDIS_PASSWORD`
- [ ] `DEBUG=False`, `REDIS_URL` set (with password)
- [ ] `ALLOW_CONSOLE_EMAIL=0` + real SMTP
- [ ] TLS terminated (nginx or load balancer); CSRF origins match HTTPS
- [ ] `worker` service running (generation queue)
- [ ] Media volume persisted (`media_data`)
- [ ] Backups for Postgres + media
- [ ] Health: `GET /health/generation/`
- [ ] Confirm password-reset email links open `/password-reset/<uid>/<token>/` (SPA)

## Local Vite + Django (dev)

```bash
npm install          # repo root
npm run dev          # Django :8000 + Vite :5173
# optional second terminal:
cd backend && python manage.py process_generation_jobs --loop
```

See [README.md](README.md) for port conflicts and E2E.

## Gated media

`/library/media/...` must remain auth-gated (JWT cookie). Never expose book PDF/audio under open `/media/`.

## Dependency vulnerability policy

| Gate | Blocks merge? |
|------|---------------|
| CI `dependency-audit` on PR/push: pip HIGH/CRITICAL (`scripts/ci_pip_audit_high.py`) + `npm audit --prefix frontend --audit-level=high` | **Yes** |
| Weekly `dependency-audit.yml` (all severities) | **No** (advisory) |

See also [README.md](README.md).
