# REMEDIATION_REPORT_2.md — Libro.UZ cleanup pass

**Date:** 2026-07-30  
**Scope:** (1) legacy `luma-*` browser-storage migration, (2) react-router GHSA-qwww-vcr4-c8h2, (3) independent re-verification of `REMEDIATION_REPORT.md`.

All pass/fail numbers below were observed in **this** session (not copied from the prior report).

---

## 1. Safe removal / migration of legacy `luma-*` storage keys

### Assessment of prior state

Canonical keys were already `librouz_*`. Legacy **source** strings still present:

| Legacy (browser may still hold) | Canonical |
|---------------------------------|-----------|
| `luma-intro-seen` (+ `libro-intro-seen`) | `librouz_intro_seen` |
| `luma-theme` / `libro-theme` | `librouz_theme` |
| `luma-sidebar-collapsed` / `libro-sidebar-collapsed` | `librouz_sidebar_collapsed` |
| `luma-reader:speed` / `libro-reader:speed` | `librouz_reader_speed` |
| `luma-reader:settings` / `libro-reader:settings` | `librouz_reader_settings` |
| `luma-locale` / `libro-locale` | `librouz_locale` |
| `luma-reader:<slug>:page` / `libro-reader:<slug>:page` | `librouz_reader_<slug>_page` |
| `luma-reader:<slug>:mode` / `libro-reader:<slug>:mode` | `librouz_reader_<slug>_mode` |

(On-read migration via `storageGet` already existed; this pass adds **bootstrap** migration so legacy keys are copied and deleted once up front.)

### Changes

| File | Change |
|------|--------|
| [`frontend/src/lib/storageKeys.ts`](frontend/src/lib/storageKeys.ts) | Added `migrateLegacyStorageKey`, `migrateAllLegacyBrowserStorage` (fixed pairs + slug pattern scan); kept defensive on-read migrate |
| [`frontend/src/main.tsx`](frontend/src/main.tsx) | Calls `migrateAllLegacyBrowserStorage()` before theme/UI reads |
| [`frontend/src/lib/locale.ts`](frontend/src/lib/locale.ts) | Uses shared `LOCALE_KEY` / `LOCALE_KEY_LEGACY` from `storageKeys` |
| [`frontend/src/lib/storageKeys.test.ts`](frontend/src/lib/storageKeys.test.ts) | New tests: migrate + delete old key; no overwrite; fresh user; bootstrap pattern keys |
| [`backend/static/library/css/library.css`](backend/static/library/css/library.css) | Comment `Luma Library` → `Libro.UZ library` |
| [`frontend/MIGRATION_NOTES.md`](frontend/MIGRATION_NOTES.md) | Documents bootstrap migration |

### Remaining `luma` hits (intentional)

| Location | Why preserved |
|----------|----------------|
| `storageKeys.ts` / `.test.ts` / `main.tsx` comment | **Required** as migration *source* key names so existing browsers keep prefs/progress |
| [`DEPLOY.md`](DEPLOY.md), [`FOLLOWUP.md`](FOLLOWUP.md), [`scripts/rename_postgres_luma_to_libro.sh`](scripts/rename_postgres_luma_to_libro.sh) | One-time Postgres rename procedure / history — left untouched per instructions |
| `MIGRATION_NOTES.md` | Documents the migration behavior |

### Tested (this session)

```text
cd frontend
npm run test       → 19 files, 93 passed (includes 5 new storageKeys tests)
npm run lint       → exit 0 (pre-existing warnings only)
npm run typecheck  → exit 0
```

### Result

**PASS**

---

## 2. react-router high advisory GHSA-qwww-vcr4-c8h2

### Advisory assessment (does it apply here?)

- **Vulnerable path:** CSRF bypass in **unstable React Server Components (RSC)** server handlers (`generateRenderResponse` / related RSC action processing). Actions could run before a 400 CSRF response.
- **Official note (GitHub advisory):** “This only affects your application if you are using the unstable RSC APIs.”
- **This codebase:** SPA with `BrowserRouter` / `Routes` / `Navigate` / `Outlet` / `useNavigate` / `useParams` only. Grep for `unstable_`, `routeRSC`, `HydratedRouter`, `.rsc` under `frontend/src` → **no matches**.
- **Practical exposure:** **Not exercised** by Libro.UZ’s client-side router usage. Still upgraded to the patched 7.x release for audit hygiene.

### Fix chosen

- **Patched 7.x (non-breaking):** GitHub advisory lists patched as **`>= 7.18.2`** (and `>= 8.3.0` for v8).
- Installed **`react-router-dom@7.18.2`** (pulls `react-router@7.18.2`).
- No Router v8 migration required.

### `npm audit` honesty

After upgrade, `npm audit` in `frontend/` **still reports** the advisory with range `7.12.0 - 8.2.0` and suggests `audit fix --force` → **downgrade to 7.11.0**.

That conflicts with the **updated GitHub advisory** (patched `>= 7.18.2`). Conclusion: **npm’s advisory range metadata is stale**; installed `7.18.2` matches the official patched floor. We did **not** downgrade.

### Tested (this session)

```text
npm ls react-router-dom  → 7.18.2
CI=true npm run test:e2e → 12 passed (2.0m)
  (covers login/logout, shelf, entitlement, flip/PDF/listen, password-reset, dashboard)
```

### Result

**PASS** (code fixed to patched 7.18.2; npm audit UI may still false-flag until registry metadata catches up)

---

## 3. Independent verification of prior remediation

### Git change scope

Remediation work is largely **uncommitted** on `main` (branch also **ahead 16** of `origin/main` with earlier product commits). Observed in this session:

```text
git diff --stat HEAD   → ~75 files in the tracked diff summary
                         (thousands of insertions/deletions; includes SPA migration,
                          JWT-only auth, notifications, Docker/security, test renames, TSX, etc.)
git ls-files --others --exclude-standard → **~219** meaningful untracked source paths
                         (excluding `backend/media`, backups, Playwright artifacts)
                         including notifications modules, `test_*.py`, Dockerfile,
                         `.nvmrc`, `REMEDIATION_REPORT*.md`, etc.
```

There is **no single “pre-remediation commit”** isolating only the 11-item pass; reviewers should inspect the working tree + untracked files, not assume a clean commit range.

### Fresh suite re-runs (this session)

| Suite | Command | Observed result |
|-------|---------|-----------------|
| Backend | `python manage.py test library users backend` | **Found 169, OK (skipped=1)** |
| Frontend unit | `npm run test` | **93 passed** / 19 files |
| Lint | `npm run lint` | **exit 0** |
| Typecheck | `npm run typecheck` | **exit 0** |
| E2E | `CI=true npm run test:e2e` | **12 passed** |

Prior report claimed 88 frontend tests; **current count is 93** after storageKeys tests (+5). Backend 169 and E2E 12 match.

### Manual / scripted spot-checks (this session)

#### a) Login / logout — no Django `sessionid` (JWT-only)

Ran against live `runserver` + seeded `e2e_owner` via [`scripts/spotcheck_auth_notifications.py`](scripts/spotcheck_auth_notifications.py):

| Check | Observed |
|-------|----------|
| Cookies after login | `access_token`, `refresh_token`, `csrftoken` only |
| `sessionid` present | **False** |
| `Set-Cookie` mentions `sessionid` | **False** |
| After logout `/api/me/` | `{"authenticated":false,"user":null}` |

**PASS** — confirms JWT-only claim from prior report.

#### b) Real notification (not stub)

1. Marked `Purchase` for `e2e_owner` + `e2e-licensed` → `paid` via `manage.py shell` (save hook).
2. DB: `notif_count 1`, message `"E2E Pullik Kitob" xaridingiz tasdiqlandi.`
3. `GET /api/notifications/?page=1` as JWT user: `unread_count 1`, `first_type purchase_paid`.

**PASS** — prior “real Notification system” claim holds.

#### c) Flip / PDF / listen after TSX

Covered by this session’s E2E run (`reader-flip`, `reader-pdf`, `reader-listen` all **ok** in the 12-passed suite). No separate console scrape beyond Playwright success.

**PASS**

### Regressions vs prior PASS claims

None found in the re-run suites or spot-checks above. Caveats that remain honest:

1. **npm audit** may still list GHSA-qwww-vcr4-c8h2 despite installed **7.18.2** (stale range metadata).
2. Legacy `luma-*` **string literals remain** only as migration sources (required) + Postgres rename docs.
3. Prefer `CI=true` for local Playwright so `reuseExistingServer` does not attach to a half-dead Django (lesson from prior remediation session).

### Result

**PASS** (prior remediation claims re-validated in this session)

---

## Summary

| Task | Status |
|------|--------|
| 1. Legacy storage migration + luma cleanup | **PASS** (93 FE tests) |
| 2. react-router GHSA fix → 7.18.2 | **PASS** (E2E 12; npm audit may still warn) |
| 3. Independent re-verification | **PASS** (169 BE / 93 FE / 12 E2E + cookie & notification spot-checks) |

### New dependency / tooling

- `react-router-dom` pinned to **7.18.2** (was 7.18.1).
- Spot-check helper: `scripts/spotcheck_auth_notifications.py` (HTTP only; optional for operators).
