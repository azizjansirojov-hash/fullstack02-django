# Production deploy checklist (Libro.UZ bookstore)

This stack is a **commercial bookstore**. Treat secrets, TLS, SMTP, and media
backups as mandatory before inviting real customers.

## Required environment

Copy [`backend/.env.example`](backend/.env.example) → `backend/.env` and set:

| Variable | Requirement |
|----------|-------------|
| `SECRET_KEY` | Long random string (not `change-me…`) |
| `DEBUG` | `False` in production |
| `ALLOWED_HOSTS` | Explicit hosts — **never** `*` |
| `POSTGRES_PASSWORD` | Strong password (Compose has **no** default) |
| `EMAIL_BACKEND` + `EMAIL_HOST_*` | Real SMTP when `DEBUG=False` |
| `USE_TLS` | `1` when terminating HTTPS in front of Gunicorn |

Startup **fails loudly** if production uses a weak `SECRET_KEY`, `ALLOWED_HOSTS=*`,
or a console email backend without `ALLOW_CONSOLE_EMAIL=1`.

## Docker

```bash
# Interpolation reads backend/.env for POSTGRES_* and SECRET_KEY
docker compose --env-file backend/.env up --build
```

Services:

- `web` — Gunicorn (SPA + APIs + reader) on `:8000`
- `worker` — `process_generation_jobs --loop` (PDF/TTS). **Required.**
- `db` — Postgres 16
- `redis` — shared cache for DRF throttles and generation quotas across Gunicorn workers

Local Compose defaults `USE_TLS=0` so HTTP on localhost works. For a public
host, put TLS in front (below) and set `USE_TLS=1` in `.env`.

## Redis (shared cache)

Gunicorn runs with **2 workers**. Django's default LocMemCache is **per-process**,
so auth/password-reset throttles and regenerate quotas would not be shared.

Compose sets `REDIS_URL=redis://redis:6379/1`. When `REDIS_URL` is set, Django
uses `RedisCache`. Local `runserver` without Redis keeps LocMem (fine for a
single process). Do not scale Gunicorn workers without Redis.

## TLS termination (required for real users)

Gunicorn speaks **HTTP** on `:8000`. Terminate TLS with nginx or Caddy, then
proxy to the web container. See [`deploy/nginx.conf`](deploy/nginx.conf).

When TLS is enabled:

- Set `USE_TLS=1` so Django enables `SECURE_SSL_REDIRECT`, HSTS, and secure cookies
- Forward `X-Forwarded-Proto: https` (sample nginx config does this)
- Put your real hostname in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`

## SMTP (password reset)

Console email is **local-only**. Production must use SMTP:

```env
DEBUG=False
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
EMAIL_USE_TLS=True
ALLOW_CONSOLE_EMAIL=0
```

## Generation worker

If the worker is down, `GenerationJob` rows stay `queued`. Staff can check:

- Django admin → Books / Generation jobs (stale queue warnings)
- `GET /health/generation/` (staff session or JWT)

## Backups

See [`scripts/backup_postgres_media.sh`](scripts/backup_postgres_media.sh) and
restore notes at the bottom of that script. Back up **Postgres and media** —
regenerating TTS for a full catalog is slow and rights-sensitive.

## TTS vendor risk

`TTS_PROVIDER=edge` uses unofficial `edge-tts`. Configure `TTS_PROVIDER` so a
paid provider module can be added later without rewriting callers. Do not market
narration SLAs on edge-tts alone.
