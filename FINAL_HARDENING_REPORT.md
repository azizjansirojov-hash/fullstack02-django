# FINAL_HARDENING_REPORT.md

**Date:** 16 August 2026  
**Scope:** Close-out of 22 backlog items from `PROJECT_ANALYSIS.md`, `IMPLEMENTATION_REPORT.md`, `DEBUG_VERIFICATION_REPORT.md`, `REPO_HYGIENE_REPORT.md`, and `SECURITY_HARDENING_REPORT.md`.

---

## 1. Executive summary

This pass closed the remaining infrastructure, payments-application, auth/security, and honesty-docs items. Route-level lazy loading splits the PDF reader (~410 kB) and PDF.js worker (~1.4 MB) from login/catalog; SPA hashed assets go through WhiteNoise; My Library is paginated; catalog search uses Postgres `SearchVector` with SQLite `icontains`; PDFs support HTTP Range (licensed files via a local stamp cache keyed by purchase + source token); nginx body size matches Django’s 100 MB audio cap. Application-level Payme checkout → webhook → entitlement is covered in Playwright with dummy merchant keys. Real Payme/Click sandbox certification is **Blocked** (no merchant credentials, Compose also cannot start without `SECRET_KEY`). Remember-me sets JWT `exp` (1 day default / 7 days opt-in) and survives refresh rotation. Progress heartbeats and reviews require entitlement; **planned** wishlist remains allowed without purchase. Argon2 is the primary hasher; default anon/user throttles exist; `provider_transaction_id` is uniquely constrained when non-empty; disposable domains use a vendored blocklist (~8k); audio is sniffed with mutagen. Production Django CSP no longer allows Google Fonts or admin `unsafe-inline`; Vite DEBUG still needs `'unsafe-inline'` / `'unsafe-eval'` for HMR (**scope reduction**). `pip-compile` 7.6.1 regenerated the hashed lockfile. Concurrent generation race remains **Blocked** for Postgres evidence (SQLite skip is documented; `docker compose ps` fails interpolation without secrets). Suites after this pass: backend **288 ran, 1 skipped, 0 failed**; frontend **106 passed**; Playwright **22 passed**; `makemigrations --check` clean; pip-audit no HIGH/CRITICAL (pypdf advisories non-blocking); npm audit high **0**. This is closer to production-ready for a staged launch, but it is **not** certified against live money or independently security-reviewed.

---

## 2. Per-item report (Parts A–D)

### Part A — Performance and infrastructure

#### A1. Route-level `React.lazy`

- **Status:** Done
- **Files changed:** `frontend/src/App.tsx`
- **What changed and why:** All page components are `lazy()` + `Suspense`. Layout/auth providers stay eager so the shell does not wait on pdfjs/page-flip.
- **Tests added/updated:** Existing `e2e/csp-hardening.spec.ts` (PDF worker still allowed).
- **Evidence:** `npm run build` (16 Aug 2026):

```text
dist/assets/index-BV4q0xCd.js                       215.04 kB │ gzip:  67.89 kB
dist/assets/LoginPage-BNAXVf6H.js                     6.59 kB
dist/assets/ReaderPage-XJPtwF6i.js                  409.88 kB │ gzip: 118.63 kB
dist/assets/pdf.worker.min-yatZIOMy.mjs           1,375.83 kB
✓ built in 314ms
```

CSP E2E: `ok 2 … PDF.js worker renders under worker-src` in the 22-pass full suite.

#### A2. WhiteNoise for SPA assets

- **Status:** Done
- **Files changed:** `backend/backend/settings.py`, `backend/backend/urls.py`, `backend/backend/test_spa_assets.py`, `DEPLOY.md`
- **What changed and why:** `WHITENOISE_ROOT = FRONTEND_DIST` when that directory exists. Removed `django.views.static.serve` for `/assets/`. `_spa_index` remains for HTML client routes. Covers still use `serve`.
- **Tests added/updated:** `SpaAssetWhiteNoiseTests` — urlconf does not `static.serve` dist assets; WhiteNoise serves `/assets/app.js` from a fixture tree.
- **Evidence:** `python manage.py test backend.test_spa_assets` is included in the 288-test run. `urls.py` comment: `/assets/*` is served by WhiteNoise.

#### A3. Paginate `MyLibraryAPIView`

- **Status:** Done
- **Files changed:** `backend/library/api/catalog.py`, `frontend/src/api/library.ts`, `frontend/src/types/library.ts`, `frontend/src/pages/MyLibraryPage.tsx`, `backend/library/test_api.py`
- **What changed and why:** Each status bucket is `{ results, pagination }` with catalog `PAGE_SIZE = 24`. `?status=` / `?page=` honor the bucket. Frontend “Yana yuklash” loads the next page.
- **Tests added/updated:** Fixture with `PAGE_SIZE + 5` reading rows: page 1 length 24, `count` 29, `has_next` true.
- **Evidence:** `MyLibraryAPITests` in `backend/library/test_api.py` (suite 288 OK).

#### A4. Postgres FTS + SQLite fallback

- **Status:** Done
- **Files changed:** `backend/library/catalog_context.py`
- **What changed and why:** `connection.vendor == 'postgresql'` uses `SearchVector`/`SearchRank` on `author_name` and translation `title`/`summary`. Otherwise `icontains`. No `CREATE EXTENSION` migration (would break SQLite CI).
- **Tests added/updated:** Existing catalog search tests still pass on SQLite.
- **Evidence:** CI/local search quality is substring `icontains`. Ranking is Postgres-only and was not measured against a live Postgres in this environment.

#### A5. HTTP Range (public PDF + licensed stamp cache)

- **Status:** Done
- **Files changed:** `backend/library/media_views.py`, `backend/library/pdf_watermark.py` (overlay timestamp uses `purchase.paid_at`), `backend/library/test_media_range.py`, `backend/library/test_purchase_access.py`
- **What changed and why:** Public-domain PDF uses `serve_ranged_file`. Licensed PDFs stamp once into `MEDIA_ROOT/pdf_stamps/` (gitignored with `backend/media/`), keyed by purchase id + source file token; then Range. First miss is still a full pypdf rewrite. Entitlement order unchanged: published → `user_can_access_book` → file exists → serve/stamp.
- **Tests added/updated:** `PublicDomainPdfRangeTests` (`Range: bytes=0-10` → 206 + `Accept-Ranges`); purchase-access stamp tests still pass.
- **Evidence:** Included in backend 288. Stamp cache is local filesystem, not object storage.

#### A6. Nginx body size 100m

- **Status:** Done
- **Files changed:** `deploy/nginx.conf`, `deploy/nginx.local.conf`, `DEPLOY.md`
- **What changed and why:** `client_max_body_size 100m` so the proxy is not stricter than `AUDIO_MAX_BYTES` (100 MB). PDF cap stays 50 MB.
- **Tests added/updated:** None (config).
- **Evidence:** Both nginx files contain `client_max_body_size 100m`.

---

### Part B — Payments

#### B1. Application-level payment E2E

- **Status:** Done
- **Files changed:** `e2e/payment-checkout.spec.ts`, `e2e/helpers/auth.ts`, `playwright.config.ts`
- **What changed and why:** Spec hits real Django checkout + Payme JSON-RPC CheckPerform → Create → Perform with dummy keys (`DEBUG=True`). Asserts status paid and licensed reader 200. Isolation: `e2e_owner` still 403. Mocked status-page UI test remains. **Not** Payme sandbox.
- **Tests added/updated:** Two new tests in `payment-checkout.spec.ts`.
- **Evidence:** Full Playwright run:

```text
ok 2 … Payme JSON-RPC fulfill grants licensed reader access
ok 3 … e2e_owner licensed book remains unpurchased (seed isolation)
22 passed (2.6m)
```

#### B2. Real sandbox certification

- **Status:** Blocked
- **Files changed:** `PAYMENTS.md` (operator runbook)
- **What changed and why:** No merchant credentials in this environment. Runbook lists env vars, checkout hosts (`test.paycom.uz` vs `checkout.paycom.uz`), webhook URLs, GetStatement, Click Prepare/Complete, pass criteria.
- **Tests added/updated:** None that hit live gateways.
- **Evidence:** Certification is not claimed. See §4.

#### B3. Remove `CLICK_TEST_MODE`

- **Status:** Done
- **Files changed:** `backend/backend/settings.py`, `.env.example`, `PAYMENTS.md`, `DEPLOY.md`
- **What changed and why:** Click Shop API checkout is always `https://my.click.uz/services/pay`. Test vs live is the merchant account, not a Django flag.
- **Tests added/updated:** Settings no longer reference the flag (boot tests still pass).
- **Evidence:** Repo grep after change: no `CLICK_TEST_MODE` in settings.

#### B4. Price snapshot comment only

- **Status:** Done (behavior unchanged; product follow-up in §5)
- **Files changed:** `backend/payments/models.py`, `backend/payments/views.py`, `backend/payments/migrations/0003_alter_paymenttransaction_amount.py`
- **What changed and why:** Help text / comments: `PaymentTransaction.amount` is snapshotted at checkout; reused pending rows keep that amount. No reuse-pending behavior change.
- **Tests added/updated:** Existing `test_check_perform_uses_snapshotted_amount_after_price_change`.
- **Evidence:** Comment-only; checkout reuse tests still pass.

---

### Part C — Security / auth

#### C1. Remember-me

- **Status:** Done
- **Files changed:** `backend/users/auth.py`, `backend/users/views.py`, `backend/users/serializers.py`, `backend/backend/settings.py`, `frontend/src/pages/LoginPage.tsx`, `backend/users/tests.py`
- **What changed and why:** Default refresh **1 day**. `remember_me: true` → **7 days** on JWT `exp` (`rm` claim) and cookie `max-age`. `CookieTokenRefreshAPIView` re-issues with the same lifetime so rotation cannot upgrade a 1-day session.
- **Tests added/updated:** Login `Max-Age` 86400 vs 604800; refresh preserves TTL.
- **Evidence:** `RememberMeTests` in `backend/users/tests.py` (288 OK).

#### C2. Progress / reviews vs entitlement

- **Status:** Done (product exception documented in §5)
- **Files changed:** `backend/library/api/progress.py`, `backend/library/api/reviews.py`, `backend/library/test_api.py`
- **What changed and why:** Review POST/PUT/DELETE and non-wishlist progress writes require `user_can_access_book` (403 otherwise). **Exception:** `planned` wishlist PUT is allowed without purchase.
- **Tests added/updated:** `EntitlementWritePolicyTests` — licensed unpaid → 403 on progress heartbeat / review POST; public-domain and entitled → 200; planned without purchase → 200.
- **Evidence:** Included in backend 288.

#### C3. Argon2

- **Status:** Done
- **Files changed:** `backend/backend/settings.py`, `requirements.txt`, `requirements.lock.txt`, `backend/users/tests.py`
- **What changed and why:** `PASSWORD_HASHERS` leads with `Argon2PasswordHasher`, then PBKDF2. Django upgrades PBKDF2 hashes on login.
- **Tests added/updated:** New user hash starts with `argon2`; PBKDF2 user still authenticates and upgrades.
- **Evidence:** Lockfile `argon2-cffi==25.1.0`. Suite 288 OK.

#### C4. Default throttles

- **Status:** Done
- **Files changed:** `backend/backend/settings.py`, `backend/scripts/audit_full_runner.py`
- **What changed and why:** `DEFAULT_THROTTLE_CLASSES` = Anon + User (`anon: 120/min`, `user: 300/min`). `E2E_RELAX_THROTTLE` + `DEBUG` also raises `anon`/`user` to `1000/min`. Fail-closed: `E2E_RELAX_THROTTLE=1` with `DEBUG=False` still `ImproperlyConfigured`. Scoped views stay scoped-only.
- **Tests added/updated:** Existing E2E throttle boot tests; Playwright 22 passed under relax.
- **Evidence:** Settings block at `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`.

#### C5. Unique `provider_transaction_id`

- **Status:** Done
- **Files changed:** `backend/payments/models.py`, `backend/payments/migrations/0002_uniq_provider_transaction_id.py`, `backend/payments/tests/test_provider_transaction_unique.py`
- **What changed and why:** Partial `UniqueConstraint` on `(provider, provider_transaction_id)` where id ≠ `''`. Empty strings still allowed.
- **Tests added/updated:** Second non-empty duplicate raises `IntegrityError`.
- **Evidence:** `makemigrations --check --dry-run` → `No changes detected`.

#### C6. Disposable email + enumeration

- **Status:** Done with accepted tradeoff (enumeration in §5)
- **Files changed:** `backend/users/disposable_email.py`, `backend/users/data/disposable_email_blocklist.txt`, `backend/users/serializers.py`, `backend/users/tests.py`
- **What changed and why:** Vendored snapshot of [disposable-email-domains](https://github.com/disposable-email-domains/disposable-email-domains). Distinct “email already exists” kept (no always-200 verify-email UX).
- **Tests added/updated:** Register rejects a blocklisted domain.
- **Evidence:** Loader reads the data file; existing uniqueness messages unchanged.

#### C7. Audio content validation

- **Status:** Done
- **Files changed:** `backend/library/validators.py`, `backend/library/models.py`, `backend/library/migrations/0026_…` (audio validators), library tests
- **What changed and why:** `AudioContentValidator` via mutagen; wired on `Book.audio_file` and `AudioChapter.audio_file`. Size/extension checks kept. **Bugfix during this pass:** PDF header check had been inverted (`if header.startswith('%PDF-')` raised); restored `if not startswith`.
- **Tests added/updated:** Renamed PDF as `.mp3` rejected; real WAV accepted.
- **Evidence:** Backend 288 after the PDF-validator fix (0 failed).

#### C8. CSP follow-ups

- **Status:** Done with scope reduction
- **Files changed:** `backend/backend/security_headers.py`, `backend/static/admin/css/libro_admin.css`, `backend/templates/admin/change_list.html`, `backend/templates/admin/base_site.html`, `backend/library/admin.py`, `frontend/index.html`, `backend/templates/base.html`, `frontend/public/fonts/`, `backend/static/fonts/`, `frontend/vite.config.js`, `backend/backend/test_security_headers.py`
- **What changed and why:** Self-hosted Sora/Fraunces WOFF2; Google Fonts origins dropped from Django + Vite CSP. Admin inline styles moved to CSS; changelist template without `<style>`; `admin_csp_policy()` equals SPA (`style-src 'self'`). **Vite DEBUG still has `'unsafe-inline'` / `'unsafe-eval'`** — `@vitejs/plugin-react` HMR preamble; production Django policy omits them.
- **Tests added/updated:** Django CSP tests; `e2e/csp-hardening.spec.ts` (5 tests including admin).
- **Evidence:** Full suite `ok … Django admin login/list/change work under admin CSP`. Vite tokens remain in `vite_dev_csp_header()`.

#### C9. Lockfile hygiene

- **Status:** Done
- **Files changed:** `requirements.lock.txt` (full `pip-compile`), environment pip-tools **7.4.1 → 7.6.1**
- **What changed and why:** Host pip 26.2.1 broke pip-tools 7.4.1 (`stdlib_pkgs`). Recompiled with `--allow-unsafe --generate-hashes`. Includes argon2-cffi, mutagen, pypdf. Not hand-edited hashes.
- **Tests added/updated:** N/A (install + suite).
- **Evidence:** Lockfile header: `pip-compile --allow-unsafe --generate-hashes --output-file=requirements.lock.txt requirements.txt`. Installed: `pip-tools 7.6.1`, `pip 26.2.1`. Suite 288 after install.

---

### Part D — Docs and honesty

#### D1. `CONTENT_PROTECTION.md`

- **Status:** Done
- **Files changed:** `CONTENT_PROTECTION.md`, links in `PAYMENTS.md`, `FOLLOWUP.md`
- **What changed and why:** Honest note: overlay + metadata, **no** encryption; entitled manifest returns full `body` JSON; audio/PDF download after purchase; what survives stripping vs re-typeset.
- **Tests added/updated:** None.
- **Evidence:** File exists at repo root; FOLLOWUP points to it.

#### D2. `verify_reader_bugs.py`

- **Status:** Done
- **Files changed:** `backend/scripts/verify_reader_bugs.py`
- **What changed and why:** Module docstring: manual debug helper, not CI/production. Log `debug-c49e1c.log` covered by `.gitignore` `*.log`.
- **Tests added/updated:** None.
- **Evidence:** `.gitignore` line `*.log`.

#### D3. Concurrent generation test

- **Status:** Done (skip message) / **Blocked** (Postgres evidence)
- **Files changed:** `backend/library/test_generation.py`
- **What changed and why:** Expanded skip: SQLite writer lock vs `SELECT FOR UPDATE`; uniqueness still covered by `GenerationJobUniquenessTests`. Command for a human: `DATABASE_URL=postgres://... python manage.py test library.test_generation.GenerationJobConcurrentEnqueueTests`.
- **Tests added/updated:** Skip text only.
- **Evidence:** Suite: `OK (skipped=1)` — that skip. `docker compose ps` failed: `required variable SECRET_KEY is missing a value`. No Postgres race run in this environment.

---

## 3. Full verification results

Commands run after all parts (16 August 2026, this machine).

**Backend** (`backend/`):

```text
python manage.py test library users payments backend --verbosity=1
Ran 288 tests in 29.966s
OK (skipped=1)
```

Skipped: `GenerationJobConcurrentEnqueueTests.test_two_threads_create_one_active_job` (SQLite).

**Migrations:**

```text
python manage.py makemigrations --check --dry-run
No changes detected
```

**Frontend** (`frontend/`):

```text
npm test
Test Files  21 passed (21)
Tests  106 passed (106)
```

**Vite production build:** success; reader/worker split as in A1.

**E2E** (repo root, `npx playwright test`, Playwright `webServer` dummy payment env):

```text
Running 22 tests using 1 worker
22 passed (2.6m)
```

**Intermediate failure (fixed):** First full-ish run with payments enabled failed `e2e/entitlement.spec.ts` looking for disabled “Sotib olish kerak”. With `PAYMENTS_ENABLED=1` the detail page shows `CheckoutButton` instead. Spec now accepts either the disabled button or the checkout group. Re-run: entitlement + CSP 6/6; later full suite 22/22.

**Dependency audit:**

```text
python scripts/ci_pip_audit_high.py
advisory (non-blocking): pypdf==6.14.2 PYSEC-2026-3655
advisory (non-blocking): pypdf==6.14.2 PYSEC-2026-3656
pip-audit: no HIGH/CRITICAL vulnerabilities found

npm audit --prefix frontend --audit-level=high
found 0 vulnerabilities
```

---

## 4. Blocked items — what a human needs to do

### B2. Live Payme / Click sandbox certification

This environment has **no** live merchant credentials. Dummy-key Playwright is not certification.

1. Obtain Payme test cash-register id + Merchant API password, and Click test merchant / service / secret.
2. Expose a public HTTPS origin (gateways will not call `localhost`). Tunnel or staging.
3. Set env from `PAYMENTS.md` (including `PAYME_TEST_MODE=1` until production checkout is certified). With `DEBUG=False`, all five merchant fields are required at boot.
4. Register webhooks: Payme `POST /api/payments/payme/webhook/`; Click Prepare/Complete paths in `PAYMENTS.md`.
5. Pass criteria: SPA checkout lands on `https://test.paycom.uz/{base64}`; Perform creates `Purchase.status=paid`; reader + PDF succeed; `GetStatement` returns the Payme id; Click via `my.click.uz` Prepare/Complete; cancel/refund paths as documented.
6. Record merchant ticket / certification IDs in ops notes (not this repo).

### D3. Postgres concurrent enqueue evidence

SQLite cannot reproduce the `select_for_update` race. A human with Compose/Postgres:

1. Provide compose `--env-file` with `SECRET_KEY` (and the rest of `x-app-environment`) so `docker compose` interpolates. Today: `docker compose ps` → `SECRET_KEY is missing a value`.
2. Start Postgres from Compose.
3. Run:

```text
DATABASE_URL=postgres://<user>:<pass>@127.0.0.1:5432/<db> python manage.py test library.test_generation.GenerationJobConcurrentEnqueueTests
```

Expect the test to **run** (not skip) and pass: two threads → one active `GenerationJob`.

---

## 5. Deferred items — product decisions needed

### Pending-transaction price freeze (B4)

Checkout **reuses** created/pending rows and keeps the snapshotted `amount`. If catalog price changes, the user still pays the old amount until that row expires/cancels. **Recommendation:** a product “price changed — start a new checkout” flow. Not implemented.

### Progress / reviews entitlement (C2)

Chosen policy: paid-store writes require access; public-domain still allowed via `user_can_access_book`. **Wishlist exception:** `status=planned` without purchase is allowed so unpaid users can bookmark. Reversible: drop the exception if wishlist should also be entitled-only. There are **no** “sample reviews from non-buyers.”

### Register enumeration (C6)

Distinct “email already exists” vs other validation errors remains. Full always-200 + verify-email is a larger UX change, not done. Disposable probing is a second oracle; username uniqueness still leaks. **Accepted tradeoff** unless product wants slower enumeration-resistant signup.

### Vite DEBUG CSP (C8)

Production Django CSP has no `'unsafe-inline'` / `'unsafe-eval'` and no Google Fonts. Local/E2E Vite HTML still needs those script tokens for HMR. Do not treat Vite headers as the production policy.

### Stamp cache vs object storage (A5)

Local `MEDIA_ROOT/pdf_stamps/` is enough for single-node Gunicorn. Multi-node or large PDFs still want object-storage pre-stamp so workers do not hold 2× file RAM on cache miss.

---

## 6. Final state of the codebase

**What is solid:** entitlement order, JWT production boot guards, fail-closed `E2E_RELAX_THROTTLE`, hashed lockfile compile, CSP on Django responses, paginated library, ranged media, application payment webhooks with tests, Argon2, unique provider ids, honest content-protection docs.

**Is this production-ready for real money and licensed files?** Not as a senior-engineer sign-off. It is ready for a **staging** deploy once a human finishes Payme/Click certification and Postgres is the database under load. Still required before live:

1. **Live payment gateway certification** (Blocked B2) — dummy keys do not prove settlement, statement, or refund with the real merchant.
2. **Load testing** — stamp-cache first miss, FTS on Postgres, WhiteNoise + Gunicorn + nginx 100m uploads, throttle behavior with Redis (LocMemCache is per-process).
3. **Independent security review** — someone other than this implementer should read entitlement, cookie JWT, CSP, watermark claims, and the full-manifest JSON exfil path in `CONTENT_PROTECTION.md`.
4. **pypdf advisories** PYSEC-2026-3655 / 3656 — non-blocking in CI script; decide upgrade/pin with a human.
5. **Postgres race test** (Blocked D3) and FTS ranking smoke on real data.

Do not market overlay watermarks as DRM. Do not claim Payme/Click certification from this report.
