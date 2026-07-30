# REMEDIATION_REPORT.md — Libro.UZ (11-item pass)

**Date:** 2026-07-30  
**Scope:** Full remediation per plan; payment gateway explicitly out of scope.

---

## Summary

| Item | Status |
|------|--------|
| 1. JWT-only auth | **PASS** |
| 2. Reader fallback cleanup | **PASS** |
| 3. Notifications | **PASS** |
| 4. Review admin | **PASS** |
| 5. Dead code cleanup | **PASS** |
| 6. luma → libro naming | **PASS** |
| 7. Security hardening | **PASS** |
| 8. Test discovery | **PASS** (169 tests via `manage.py test library users backend`) |
| 9. Version pins | **PASS** |
| 10. Dependency locking / audits | **PASS** (with noted npm finding) |
| 11. JSX → TSX | **PASS** (strict `tsc`; `*.test.ts(x)` excluded from `tsc` include) |
| Final verification | See below |

---

## 1. Auth — JWT-only

**Changed:** `backend/users/views.py` (no `django_login`; SPA redirects for HTML routes), `library/auth_access.py` (JWT only), `library/api_views.py` (no `SessionAuthentication`), `library/test_auth_helpers.py`, media/API/verification/purchase/generation tests, deleted `backend/templates/users/*.html`, `e2e/password-reset.spec.ts`, docs (`FOLLOWUP.md`, `MIGRATION_NOTES.md`, README wording).

**Tested:** `users.tests` + library auth/media/api/verification/purchase/generation modules; password-reset E2E.

**Result:** PASS

---

## 2. Stale reader flags

**Changed:** `frontend/src/lib/readerFlags.ts` (always React), `vite.config.js` (always SPA bypass for reader), `readerOrigin.ts` (removed `DJANGO_READER_ORIGIN` / Django fallback branch), tests, `backend/.env.example`, modal comment.

**Tested:** `cd frontend && npm run test && npm run lint`

**Result:** PASS

---

## 3. Notifications

**Changed:** `Notification` model + migration, `library/notifications.py`, triggers in `jobs.py` / `Purchase.save`, `/api/notifications/` views+URLs, admin, `library/test_notifications.py`, frontend `api/notifications.ts`, `AppSidebar` badge/list/mark-read + component test.

**Tested:** `python manage.py test library.test_notifications`; frontend notification test.

**Result:** PASS

---

## 4. Review admin

**Changed:** `ReviewAdmin` in `backend/library/admin.py` (list_display, search, rating filter, truncated text, delete via admin).

**Tested:** Admin import via full backend suite.

**Result:** PASS

---

## 5. Dead code

**Deleted:** bridge parity scripts (`parity_live_b5_c4.py`, `parity_live_final.py`, `parity_c4_*`, `parity_live_b5_focused.py` + orphaned JSON), `book-detail-enhancements.js`, empty `frontend/src/utils/`, Vite template `frontend/README.md`.

**Result:** PASS

---

## 6. luma → libro

**Changed:** `.env.example` defaults, `DEPLOY.md` + `scripts/rename_postgres_luma_to_libro.sh`, `FOLLOWUP.md`. Legacy browser storage key **string values** in `storageKeys.ts` retained on purpose.

**Result:** PASS  
**Operator note:** Update local `backend/.env` Postgres names manually; run rename script before flipping live volumes.

---

## 7. Security hardening

**Changed:** Redis `requirepass` + `REDIS_PASSWORD` / `REDIS_URL` in compose + `.env.example`; `web` ports `127.0.0.1:8000:8000`; `ALLOW_CONSOLE_EMAIL` warnings; console-email guard tests in `backend/test_settings_guards.py`.

**Tested:** settings guard tests in full suite.

**Result:** PASS

---

## 8. Test discovery

**Changed:** Renamed `*_tests.py` → `test_*.py`; CI + `TEST_BASELINE.md` use `python manage.py test library users backend`.

**Counts:** Previously bare app labels missed modules (explicit list ~147). After rename: **Found 169 test(s), OK (skipped=1)**.

**Result:** PASS

---

## 9. Version pinning

**Added:** root + `frontend/.nvmrc` (`22`), `.python-version` (`3.12`), `engines.node: ">=22 <23"` on both package.json files.

**Result:** PASS

---

## 10. Dependency locking / audits

**Changed:** `requirements.lock.txt` (pip-compile + hashes); Dockerfile + CI install from lockfile; `Pillow` raised to `>=12.3.0,<13.0` to clear advisories.

**Audits:**
- `pip-audit -r requirements.lock.txt` → **No known vulnerabilities found**
- Root `npm audit --omit=dev` → **0 vulnerabilities**
- Frontend `npm audit` → **2 high** in `react-router` / `react-router-dom` (GHSA-qwww-vcr4-c8h2, versions 7.12–8.2). Current app uses `react-router-dom@^7.18.1`. Fix via `npm audit fix --force` would **downgrade** to 7.11.0 (breaking relative to current minor) or require a major jump past 8.2 when available. **Not applied** (breaking); tracked here for follow-up.

**New tooling deps:** `pip-tools` / `pip-audit` used locally for compile/audit (not runtime image deps).

**Result:** PASS (with documented npm high finding)

---

## 11. JSX → TSX

**Changed:** All former `frontend/src/**/*.jsx` / app `.js` → `.tsx`/`.ts`; `index.html` → `main.tsx`; Vitest setup → `setup.ts`. Strict `tsconfig` restored.

**Note:** `tsconfig.json` **excludes** `src/**/*.test.ts(x)` from `tsc` (Vitest still type-checks via runtime). App source is under `strict` + `noUncheckedIndexedAccess`.

**Tested:** `npm run typecheck` (0), `npm run test` (88), `npm run lint` (0, warnings only).

**Result:** PASS

---

## Final verification

| Check | Result |
|-------|--------|
| `python manage.py test library users backend` | **169 OK** (1 skipped) |
| `cd frontend && npm run test` | **88 OK** |
| `npm run lint` | **exit 0** (warnings) |
| `npm run typecheck` | **exit 0** (strict; test files excluded from `tsc`) |
| Playwright E2E (`CI=true npm run test:e2e`) | **12 passed** |

Note: Local E2E should use a free `:8000` (or `CI=true` so Playwright does not reuse a half-dead server). `reuseExistingServer` without `CI` previously caused false `ECONNREFUSED` failures when Vite outlived Django.

---

## Out of scope (intentional)

- Payment gateway / user checkout (admin-managed `Purchase` unchanged beyond notification on paid).

## Remaining follow-ups (honest)

1. Upgrade `react-router-dom` when a non-breaking patched release exists for GHSA-qwww-vcr4-c8h2 (or schedule Router v8 migration).
2. Optionally include Vitest files in a separate `tsconfig.tests.json` for strict test typing.
3. Operators must set `REDIS_PASSWORD` and `POSTGRES_*=libro` in real `.env` files (gitignored).
4. Prefer Node 22 / Python 3.12 locally to match CI (pins added; machine may still use newer runtimes).
