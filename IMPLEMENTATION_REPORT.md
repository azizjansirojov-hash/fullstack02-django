# IMPLEMENTATION_REPORT.md

### 1. Summary

This pass implemented all eight scoped items: CI now runs the `payments` app tests; Payme `GetStatement` returns real `PaymentTransaction` rows in the requested millisecond window; refresh JWT lifetime is a flat **7 days** (remember-me was not implemented); `CookieTokenRefreshAPIView` is throttled at `20/min`; the unused `_serialize_similar_books` helper was removed from `library/api/catalog.py`; `FOLLOWUP.md` no longer claims payments are admin-only; books can override catalog price via `price_tiyin`; licensed PDF downloads get a per-purchase embedded identifier at serve time. Scope reductions: no remember-me (item 3); watermark is an embedded PDF comment at download time, not a visible overlay or generation-time stamp (item 8). Backend tests: **258 ran, 1 skipped, 0 failed**. Frontend was not changed; `vitest` was not run. `PROJECT_ANALYSIS.md` is not in the repo (the pass used the task file list and current code).

### 2. Per-item report

#### 1. CI payments coverage gap

- **Status**: Done
- **Files changed**: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
- **What changed**: The backend-tests job now runs `python manage.py test library users payments backend`. Existing `payments` tests were already passing when exercised (34 tests before new statement/checkout cases).
- **Tests added/updated**: None for CI itself. `payments` tests were run locally under the new invocation.
- **Any tradeoffs or follow-up work needed**: None.

#### 2. Payme `GetStatement` returns empty

- **Status**: Done
- **Files changed**: [`backend/payments/providers/payme.py`](backend/payments/providers/payme.py), [`backend/payments/tests/test_payme_statement.py`](backend/payments/tests/test_payme_statement.py)
- **What changed**: `_statement` reads `from`/`to` as epoch milliseconds, includes Payme rows with a non-empty `provider_transaction_id`, uses `raw_payload.create_time` when present (else `created_at`), inclusive window, Payme Merchant API transaction shape (`id`, `time`, `amount`, `account.order_id`, times, `transaction`, `state`, `reason`). Shared `_payme_state` / `_statement_create_time` helpers also used by `CheckTransaction`.
- **Tests added/updated**: `backend/payments/tests/test_payme_statement.py` — empty window, single tx, multiple ordered txs, inclusive boundaries, skip rows without a Payme id.
- **Any tradeoffs or follow-up work needed**: Filtering is in Python over Payme txs with a provider id (no JSON `create_time` index). Fine at current volume; add a DB time filter if statement windows grow large.

#### 3. Refresh token TTL is too long (30 days)

- **Status**: Done with scope reduction
- **Files changed**: [`backend/backend/settings.py`](backend/backend/settings.py)
- **What changed**: `SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']` is `timedelta(days=7)`. Cookie `max_age` already follows this via `users/auth.py`. **Remember-me was not implemented** (confirmed for this pass): every login gets the same 7-day refresh cookie.
- **Tests added/updated**: None (no test asserted 30 days).
- **Any tradeoffs or follow-up work needed**: Users who want “stay signed in” vs short sessions cannot opt in. Next pass: login flag + ~1 day default / 7 day opt-in, and matching cookie `max_age`.

#### 4. Missing throttle on token refresh

- **Status**: Done
- **Files changed**: [`backend/users/views.py`](backend/users/views.py), [`backend/backend/settings.py`](backend/backend/settings.py), [`backend/users/tests.py`](backend/users/tests.py)
- **What changed**: `CookieTokenRefreshAPIView` uses `ScopedRateThrottle` with scope `token_refresh` at `20/min`. When `E2E_RELAX_THROTTLE=1` and `DEBUG=True`, that scope is raised to `1000/min` alongside `auth` so Playwright on a shared CI IP does not 429.
- **Tests added/updated**: `CookieTokenRefreshThrottleTests` in `backend/users/tests.py` (scope + class wiring).
- **Any tradeoffs or follow-up work needed**: Production remains 20/min. LocMemCache still makes throttle counters per-process without Redis (existing production constraint).

#### 5. Dead code cleanup

- **Status**: Done
- **Files changed**: [`backend/library/api/catalog.py`](backend/library/api/catalog.py)
- **What changed**: Removed unused `_serialize_similar_books` (it referenced `Book` / `DISPLAY_LANG` that were not imported). The working helper remains in `library/api/books.py`.
- **Tests added/updated**: None. Existing `SimilarBooksAPITests` still cover book detail.
- **Any tradeoffs or follow-up work needed**: None.

#### 6. Docs drift

- **Status**: Done
- **Files changed**: [`FOLLOWUP.md`](FOLLOWUP.md)
- **What changed**: Removed “admin-marked only / checkout out of scope”. Documented that Payme/Click checkout and webhooks exist (`payments/`, `PAYMENTS.md`). Kept TTS, notifications, i18n, roles, dependency audit. Added remember-me and visible PDF overlay as open follow-ups from this pass.
- **Tests added/updated**: None.
- **Any tradeoffs or follow-up work needed**: None.

#### 7. Per-book pricing

- **Status**: Done
- **Files changed**: [`backend/library/models.py`](backend/library/models.py), [`backend/library/migrations/0025_book_price_tiyin.py`](backend/library/migrations/0025_book_price_tiyin.py), [`backend/payments/payment_service.py`](backend/payments/payment_service.py), [`backend/payments/views.py`](backend/payments/views.py), [`backend/library/api/_common.py`](backend/library/api/_common.py), [`backend/library/admin.py`](backend/library/admin.py), [`backend/payments/tests/test_checkout_api.py`](backend/payments/tests/test_checkout_api.py), [`backend/payments/tests/test_entitlement_flow.py`](backend/payments/tests/test_entitlement_flow.py)
- **What changed**: Nullable `Book.price_tiyin`. `book_price_tiyin(book=None)` / `require_book_price_tiyin(book=None)` use the book override when it is a positive integer, else `settings.BOOK_PRICE_TIYIN`. Checkout snapshots that amount. Catalog/detail JSON `book_price_tiyin` uses the same resolver. Admin fieldset includes `price_tiyin`. **`payments/entitlement.py` was not changed** — it only fulfills/revokes purchases and has no price logic.
- **Tests added/updated**: `test_custom_book_price_used_at_checkout`, `test_missing_custom_price_falls_back_to_global`. `cache.clear()` in checkout and entitlement flow `setUp` so extra checkout POSTs do not trip `payment_checkout` 10/min across the suite.
- **Any tradeoffs or follow-up work needed**: Reused pending/created transactions keep the original snapshotted amount (existing behavior). `0` or invalid `price_tiyin` falls back to global.

#### 8. Basic DRM / content protection for licensed books

- **Status**: Done with scope reduction
- **Files changed**: [`backend/library/pdf_watermark.py`](backend/library/pdf_watermark.py), [`backend/library/media_views.py`](backend/library/media_views.py), [`backend/library/test_purchase_access.py`](backend/library/test_purchase_access.py)
- **What changed**: At download time, `BookPdfMediaView` stamps **licensed** PDFs with a PDF comment `% LibroUZ-license: {email}|purchase:{id}`. Public-domain files are streamed unchanged. No new PDF-merge dependency; identifier is embedded, not a visible page overlay. Generation pipeline (`library/jobs.py` / `pdf_service.py`) is unchanged.
- **Tests added/updated**: `test_licensed_pdf_embeds_purchase_identifier`, `test_two_purchases_embed_different_identifiers`, `test_public_domain_pdf_is_not_watermarked`.
- **Any tradeoffs or follow-up work needed**: Each licensed PDF download reads the whole file into memory (no HTTP Range on stamped responses). Comment can be stripped by a determined user. Next pass: `pypdf` (or similar) visible overlay, optional caching of stamped bytes, Range support.

### 3. Test run results

Command (from `backend/`):

```text
python manage.py test library users payments backend --verbosity=1
```

Result:

```text
Ran 258 tests in 99.354s
OK (skipped=1)
Found 258 test(s).
System check identified no issues (0 silenced).
```

- **Frontend**: not run (`vitest run`) — no frontend files changed.
- **Skipped**: `library.test_generation.GenerationJobRaceTests.test_two_threads_create_one_active_job` — `skipTest` on SQLite (`database is locked`); intended to run on Postgres. Pre-existing, not introduced by this pass.

Tests updated to match new behavior:

- New Payme statement and watermark tests (intended coverage).
- Checkout tests for per-book price.
- `cache.clear()` in two payments test classes so the extra checkout calls do not 429 under `payment_checkout` 10/min (LocMemCache is process-global across TestCases).

### 4. Migration notes

- **[`backend/library/migrations/0025_book_price_tiyin.py`](backend/library/migrations/0025_book_price_tiyin.py)**
  - Adds nullable `Book.price_tiyin`.
  - Also `AlterField` on `Notification.type` to include `purchase_refunded` (already on the model since a prior pass; `0019_notification` still listed only `audio_ready` / `purchase_paid`). Included so `makemigrations --check` is clean — schema-compatible choice update, not a new column.

`python manage.py makemigrations --check --dry-run` → **No changes detected**.

### 5. Open items / recommendations for next pass

This pass did **not** implement the rest of the living backlog (and `PROJECT_ANALYSIS.md` was missing from the tree). Carry forward:

- Remember-me: ~1 day refresh by default, 7 days only if the user opts in.
- Visible PDF watermark / overlay merge; optional stamp cache; HTTP Range for stamped PDFs.
- Notification preferences + transactional email/push (in-app `Notification` already exists).
- Second TTS provider behind `TTS_PROVIDER`.
- Residual `.jsx` → TypeScript; real multi-locale catalog copy.
- Custom reader/publisher roles (staff/superuser only today).
- Production Redis required for consistent DRF throttle counters across Gunicorn workers (already enforced when `DEBUG=False`).
- Dependency-audit weekly workflow remains advisory; PR CI already blocks high/critical.
- Django legal-page static assets vs SPA branding sync.
- Index/time-window query for Payme `GetStatement` if merchant volume grows.
- Checkout reuse of pending txs does not refresh amount when `price_tiyin` changes after the first attempt.
