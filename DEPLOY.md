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

Local Compose typically uses `USE_TLS=0` and `ALLOW_CONSOLE_EMAIL=1` for HTTP smoke tests.
**Production:** set `ALLOW_CONSOLE_EMAIL=0` and configure SMTP. Django refuses to boot with a console email backend when `DEBUG=False` unless `ALLOW_CONSOLE_EMAIL=1`.

### Host port binding

Compose publishes `web` as **`127.0.0.1:8000:8000`** (loopback only). The process still listens on `0.0.0.0` *inside* the container so the TLS nginx overlay can reach `web:8000` on the Docker network.

To intentionally expose the app on the LAN (not recommended without a reverse proxy):

```yaml
# override in a local compose fragment
ports:
  - "8000:8000"   # all interfaces
```

### TLS overlay

See [`deploy/docker-compose.tls.yml`](deploy/docker-compose.tls.yml) and [`deploy/nginx.conf`](deploy/nginx.conf). Generate a local cert with [`deploy/generate_selfsigned_cert.sh`](deploy/generate_selfsigned_cert.sh) when needed.

## Environment variables (critical)

| Variable | Notes |
|----------|--------|
| `SECRET_KEY` | Required; long random string |
| `DEBUG` | `False` in production |
| `ALLOWED_HOSTS` | Hostnames for the site |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Compose DB (defaults **`libro`**) |
| `DATABASE_URL` | Built by Compose from `POSTGRES_*` |
| `REDIS_PASSWORD` | Required for Compose Redis `--requirepass` |
| `REDIS_URL` | Required when `DEBUG=False`; Compose sets `redis://:${REDIS_PASSWORD}@redis:6379/1` |
| `FRONTEND_DIST` | Path to built SPA (`/app/frontend/dist` in Docker) |
| `CSRF_TRUSTED_ORIGINS` | HTTPS origins of the SPA |
| `DEFAULT_FROM_EMAIL` | Password-reset From address |
| `EMAIL_*` | SMTP for real delivery; console backend prints links locally |
| `ALLOW_CONSOLE_EMAIL` | **Must be `0` in production** |
| `SPA_ORIGIN` | Absolute SPA origin for emails/redirects in Vite+Django local dev; empty/`same` = relative |
| `TTS_PROVIDER` | Default `edge` |

Copy from [`backend/.env.example`](backend/.env.example). Do **not** commit real `.env` secrets.

### One-time Postgres rename (`luma` → `libro`)

If an existing volume still uses database/user **`luma`**, do **not** only change `.env` — update the database first:

```bash
# Exact runnable helper (dump + ALTER DATABASE + role):
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

## Production checklist

- [ ] Strong `SECRET_KEY`, Postgres password, and `REDIS_PASSWORD`
- [ ] `DEBUG=False`, `REDIS_URL` set (with password)
- [ ] `ALLOW_CONSOLE_EMAIL=0` + real SMTP
- [ ] TLS terminated (nginx or load balancer); `JWT_COOKIE_SECURE` / CSRF origins match HTTPS
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
