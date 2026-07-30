# Libro.UZ library (Django + React)

## Product entrypoints

| Mode | URL | What you get |
|------|-----|----------------|
| **Docker (production-like)** | http://127.0.0.1:8000/ | React SPA (catalog, auth, book detail, reader) |
| **Local Vite + Django** | http://127.0.0.1:5173/ | React via Vite; Django APIs/media on :8000 |
| Immersive reader | `/library/<slug>/read/` | React SPA (flip / PDF / listen). Local `:8000` redirects to the Vite SPA. |
| Django admin | `/admin/` | Staff publishing + media generation |

## Quick start (local Vite + Django)

1. Copy `backend/.env.example` → `backend/.env` and set a strong `SECRET_KEY` (keep `DEBUG=True` for local).
2. Install backend deps: `pip install -r requirements.txt`
3. `cd backend && python manage.py migrate`
4. Install frontend deps: `cd frontend && npm install`
5. **Start both servers (one terminal):** from the repo root:
   ```bash
   npm install    # once — installs concurrently + Playwright at the root
   npm run dev
   ```
   This runs Django on **http://127.0.0.1:8000/** and Vite on **http://127.0.0.1:5173/** with labeled output. Ctrl+C stops both.
   Before start, `predev` frees ports **5173** and **8000** so a previous aborted session (orphaned `node`/`python`) cannot block Vite’s `strictPort` bind. Manual cleanup: `npm run dev:free`.

### Troubleshooting: `Port 5173 is already in use`

**What it means:** Vite is configured with `strictPort: true` (ports are pinned for Playwright `baseURL` and Django `SPA_ORIGIN`). If something is already listening on **5173**, Vite exits; `concurrently -k` then kills Django too.

**Why it keeps happening (confirmed on Windows):** Closing/killing the terminal that ran `npm run dev` **without** killing the process tree (Cursor/agent abort, terminal X button, `taskkill /PID <shell> /F` without `/T`) leaves an orphaned **`node.exe`** still bound to `127.0.0.1:5173`. Playwright’s `webServer` also starts Vite; an interrupted E2E run can leave the same orphan. Evidence pattern:

```text
netstat -ano -p TCP | findstr "LISTENING" | findstr ":5173"
# TCP  127.0.0.1:5173  0.0.0.0:0  LISTENING  <pid>
tasklist /FI "PID eq <pid>"
# node.exe
```

**Automated safeguard:** `npm run predev` → `node scripts/free-dev-ports.mjs` runs before every `npm run dev` and frees **5173** + **8000**. E2E `webServer` commands free their own port before bind. Prefer this over changing `strictPort` (Option B would drift off 5173 and break hardcoded E2E/`SPA_ORIGIN` URLs).

**Manual fix (if needed):**

```powershell
npm run dev:free
# or:
netstat -ano -p TCP | findstr "LISTENING" | findstr ":5173"
taskkill /F /T /PID <pid>
npm run dev
```

6. (Optional but required for PDF/TTS generation) Start the media worker in a second terminal:
   `cd backend && python manage.py process_generation_jobs --loop`
7. Open **http://127.0.0.1:5173/library** (Vite proxies `/api`, `/library` media+read, `/media`, `/static`, `/admin`).

### Local listen / audio checklist

If Tinglash looks “broken,” check environment before assuming a frontend bug:

1. **Both servers running** — `npm run dev` from the repo root (Django `:8000` + Vite `:5173`). A dead Django process makes `/library/media/.../audio/` fail through the Vite proxy.
2. **Media worker running** when testing newly added books — without `process_generation_jobs --loop`, `GenerationJob` rows stay `queued` and `audio_generation_status` may never become `ready`.
3. **Book actually has audio** — in admin or shell, confirm `audio_generation_status='ready'` and at least one `AudioChapter` with a real file (or a legacy `audio_file`).
4. **Launch path** — modal **Tinglash** navigates with `#autoplay=1`; toolbar **Tinglash** should reveal the bar and start playback from the same click.

**Why one command?** Vite’s dev proxy does not require Django at startup — it forwards API calls lazily. The old “backend first, then frontend” order was workflow habit, not a hard dependency. `npm run dev` starts both together; either may finish booting first.

**Alternative (Django-only command):** `cd backend && python manage.py runserver` still auto-starts Vite as a subprocess (no labeled output). Use `SKIP_VITE_AUTOSTART=1` when running Django alongside `npm run dev` from the root.

## End-to-end tests (Playwright)

Cross-stack browser tests live in [`e2e/`](e2e/) (auth, shelf, flip/PDF/listen, entitlement, logout). They hit a real Django + Vite stack on SQLite with seeded fixtures.

```bash
# From repo root (installs browsers on first run)
npm install
npx playwright install chromium
npm run test:e2e
```

What `npm run test:e2e` does:

1. `python manage.py migrate` + `python manage.py seed_e2e` (public-domain + licensed books, `e2e_owner` user, stub PDF/audio)
2. Starts Django `:8000` and Vite `:5173` (waits until ready — not blind sleeps)
3. Runs Playwright specs

Useful variants:

```bash
npm run test:e2e:ui          # Playwright UI mode
npx playwright test e2e/reader-flip.spec.ts   # one file
```

Seed credentials (local only): username `e2e_owner`, password `E2e-Passw0rd!Strong`.

The suite sets `E2E_RELAX_THROTTLE=1` on Django so per-test logins are not blocked by the normal `5/min` auth throttle. That flag is **ignored unless `DEBUG=True`**; with `DEBUG=False` Django refuses to start if the flag is set (ImproperlyConfigured).

CI runs the same suite as a **separate** required job (`e2e`) so Vitest/Django unit failures stay fast to see; E2E still must pass before merge.

## Docker

```bash
cp backend/.env.example backend/.env
# Required: strong SECRET_KEY (not the change-me placeholder) and POSTGRES_PASSWORD
# Local Compose uses USE_TLS=0 + ALLOW_CONSOLE_EMAIL=1 for HTTP smoke tests.
docker compose --env-file backend/.env up --build
```

Then open **http://127.0.0.1:8000/library** — you should see the **React** catalog (not the old Django login page as the home experience).

Compose runs:

- `web` — Gunicorn (SPA + APIs + reader)
- `worker` — `process_generation_jobs --loop` (PDF/TTS queue) — **required**
- `db` — Postgres (host port **not** published by default)

Password-reset emails use `EMAIL_*` from `.env` (console backend prints the link locally; configure SMTP for real delivery). Confirm links open Django `/password-reset/<uid>/<token>/`.

See [DEPLOY.md](DEPLOY.md) for TLS, SMTP, backups, and production checklist.
See [FOLLOWUP.md](FOLLOWUP.md) for deferred work and [frontend/MIGRATION_NOTES.md](frontend/MIGRATION_NOTES.md) for SPA migration status.
