# Migration Notes — Django Templates → React (Vite)

## What was moved

| From Django | To React |
|-------------|----------|
| `templates/base.html` chrome | `src/components/layout/AppShell.tsx` + `Constellation.tsx` (auth pages) |
| `templates/users/login.html` | `src/pages/LoginPage.jsx` |
| `templates/users/register.html` | `src/pages/RegisterPage.jsx` |
| `templates/users/password_reset.html` (request) | `src/pages/PasswordResetPage.jsx` |
| `static/users/css/auth.css` | `src/assets/css/auth.css` |
| `static/users/js/constellation.js` | `src/components/layout/Constellation.tsx` |
| `static/users/js/auth.js` login flow | React state in `LoginPage` + `src/api/auth.ts` |
| `templates/library/catalog.html` | Dashboard routes: `HomePage`, `DiscoverPage`, `CollectionsPage`, `MyLibraryPage` + `src/components/library/*` |
| `templates/library/book_detail.html` | `src/pages/BookDetailPage.jsx` |
| `static/library/css/library.css` | `src/assets/css/library.css` |
| `static/library/js/catalog.js` (shelves + launch modal) | React state in `ReaderLaunchModal` + dashboard pages |
| Immersive reader (flip / PDF / listen) | `ReaderPage` → `FlipReaderView` / `PdfReaderMode` |

## Still on Django

| Surface | Why |
|---------|-----|
| `/library/media/...` | Auth-gated PDF/audio streams (relative URLs + JWT cookie; Vite proxy in dev) |
| `/password-reset/<uid>/<token>/` | SPA confirm (Django redirects to SPA when not using FRONTEND_DIST) |
| `/admin/` | Publishing + generation jobs |
| Legal HTML pages (`/terms/`, `/privacy/`, rights report) | Still render Django templates extending `templates/base.html` |

> **Note:** The Django HTML immersive reader (`book_read.html` + static reader JS) has been **removed**. `/library/<slug>/read/` redirects to or serves the React SPA. There is no HTML reader fallback.

## Django static assets (final state)

SPA routes own CSS/JS under `frontend/src/assets/` and React components. **Removed** unused duplicate `backend/static/library/css/library.css` (no template references).

**Intentionally kept** for legal/`base.html` chrome only:

| Path | Used by |
|------|---------|
| `backend/static/users/css/auth.css` | `templates/base.html` |
| `backend/static/users/css/logo.css` | `templates/base.html` |
| `backend/static/users/js/constellation.js` | `templates/base.html` |
| `backend/static/users/js/auth.js` | `templates/base.html` |
| `backend/static/brand/`, `fonts/`, `audio/` | Branding, PDF fonts, TTS silence stub (not SPA CSS duplicates) |

Migration for **SPA-owned routes is complete**. Remaining Django CSS/JS is legal-page chrome, not a second catalog/reader stack.


## React reader (default)

| Piece | Location |
|-------|----------|
| Route | `/library/:slug/read` → `src/pages/ReaderPage.jsx` (`RequireAuth`) |
| Feature flag | Removed — React reader is the only implementation |
| Manifest API | `GET /api/library/<slug>/reader/` — body, audio_sync, gated media URLs (entitlement required) |
| Launch helper | `buildReadHref()` in `src/lib/readerOrigin.ts` |

Media auth: no signed tokens — relative `/library/media/...` URLs proxied to Django with HttpOnly JWT cookies (`credentials: include`).

### Phase 3 parity (complete)

- [x] Side-by-side flip / PDF / listen overlay
- [x] Entitlement parity
- [x] Progress API cross-reader (`chapter_id` / `position` preservation)
- [x] Off-screen sentence highlight without auto page-turn
- [x] Mobile viewport
- [x] PDF render-phase stall fallback
- [x] Measure-box CSS scoping fix

## Production serving (Docker)

With `FRONTEND_DIST` set, Django serves the built SPA at **`/`** (not `/app/`):

- `/`, `/login/`, `/register/`, `/password-reset/`, `/library/`, `/library/<slug>/` → `index.html`
- `/library/<slug>/read/` → React `index.html`
- `/library/media/...`, `/api/...`, `/admin/` → Django
- Reader links use same-origin when `VITE_DJANGO_ORIGIN` is empty at build time (see Dockerfile)

## Auth model

- JWT HttpOnly cookies (`access_token`, `refresh_token`) only; Django sessions are not created by auth APIs.
- CSRF via cookie + `X-CSRFToken` on unsafe methods
- Local Vite proxy: `/api`, `/media`, `/admin`, `/static`, `/library` → `:8000`
- Browser storage keys use `librouz_*` prefix. Legacy `luma-*` / `libro-*` keys are migrated once at SPA bootstrap (`migrateAllLegacyBrowserStorage` in `main.tsx`) and deleted.

## How to run (dev)

From the **repo root** (recommended — one terminal, labeled output):

```bash
npm install          # once
npm run dev          # Django :8000 + Vite :5173; Ctrl+C stops both
```

Optional media worker (PDF/TTS queue) in a second terminal:

```bash
cd backend
python manage.py process_generation_jobs --loop
```

Open **http://127.0.0.1:5173/library**.

## Catalog → reader handoff

Continue / Listen / Start over open `/library/<slug>/read/?mode=...` (React same-origin by default).

## Checklist

- [x] Login / register / password-reset request — React
- [x] Catalog / dashboard — React
- [x] Book detail — React
- [x] Reader PDF / flip / listen — React
- [x] Production: SPA at `/` via `FRONTEND_DIST` (Docker)
- [x] Password-reset confirm — React (`PasswordResetConfirmPage`)
- [x] JWT-only authentication for SPA APIs and media
- [x] Removed obsolete Django auth templates
