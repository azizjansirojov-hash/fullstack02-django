# DEBUG_VERIFICATION_REPORT.md

Verification pass against `IMPLEMENTATION_REPORT.md` (2026-08-16). Evidence is from commands actually run in this working tree, not from the implementation report’s narrative.

## 1. Executive summary

`IMPLEMENTATION_REPORT.md` is **mostly accurate** on the eight scoped items: the listed files contain the claimed changes, CI now invokes `payments`, GetStatement is served through the Payme webhook, refresh cookies are 7 days, `token_refresh` is registered at `20/min` and does 429 on the 21st call, catalog no longer defines `_serialize_similar_books`, `FOLLOWUP.md` no longer says checkout is out of scope, per-book `price_tiyin` is snapshotted at checkout (including pending reuse), and licensed PDFs get a per-purchase `LibroUZ-license:` marker after entitlement checks.

It is **not** safe to stamp this pass “done, ship” without caveats. Three process/doc gaps are real: `PROJECT_ANALYSIS.md` is absent (the implementation report admitted this); `IMPLEMENTATION_REPORT.md` itself is **untracked**; `PAYMENTS.md` is cited everywhere but **does not exist**; `DEPLOY.md` and `PROJECT_AUDIT.md` are **deleted in the working tree** while still in git HEAD. One functional bug was found and fixed here: inserting the watermark comment *immediately before* `%%EOF` made pypdf raise `PdfReadError: startxref not found` on a real `PdfWriter` PDF. After appending the comment *after* the original bytes, pypdf parsed a stamped 1-page PDF successfully. Automated backend (258 tests × 2, then +1 regression test), frontend (106), and targeted Playwright (6) are green. Full browser smoke of checkout → Payme/Click sandbox, admin price edit, and 15-minute access-token expiry was **not** done by a human in this pass.

**Verdict:** implementation claims are largely true; treat the watermark fix as required before licensed PDF downloads; restore missing docs (`PAYMENTS.md`, `DEPLOY.md`) before calling the tree release-ready.

## 2. Report reconciliation table

| Item | Claimed status | Verified status | Discrepancy |
| --- | --- | --- | --- |
| 1. CI payments coverage | Done | **Done** | None on the workflow line. CI still uses `--verbosity=1` (report’s sample matches CI, not the `--verbosity=2` this pass used). |
| 2. Payme GetStatement | Done | **Done** | Existing tests already POST `payments:payme-webhook` (not `_statement` in isolation). Fallback when `raw_payload` lacks `create_time` was **claimed but untested**; runtime check confirmed it. |
| 3. Refresh TTL 7 days (no remember-me) | Done with scope reduction | **Done with scope reduction** | Cookie `max-age` is 604800, matching `SIMPLE_JWT`. No remember-me flag (as claimed). |
| 4. Token refresh throttle | Done | **Done, tests incomplete** | Scope is registered; 21st request **does** 429. Repo tests only assert class wiring. `override_settings` cannot raise the rate; `E2E_RELAX_THROTTLE=1` works at **import** time with `DEBUG=True`. |
| 5. Dead `_serialize_similar_books` in catalog | Done | **Done** | Gone from `library/api/catalog.py`. Still used in `library/api/books.py`. |
| 6. Docs drift (FOLLOWUP) | Done | **Done with process issues** | FOLLOWUP no longer says admin-only checkout. `PAYMENTS.md` is missing. `DEPLOY.md` / `PROJECT_AUDIT.md` deleted in WT. `IMPLEMENTATION_REPORT.md` untracked. `PROJECT_ANALYSIS.md` never in repo. |
| 7. Per-book `price_tiyin` | Done | **Done** | Custom price, global fallback, pending snapshot, admin `name="price_tiyin"`, CheckPerform uses snapshotted amount. |
| 8. PDF watermark (comment, not overlay) | Done with scope reduction | **Done after fix** | Identifier is per email+purchase UUID. Public-domain bytes unmodified. Original insert-before-`%%EOF` **corrupted** pypdf parse; fixed by append-after-file. |

## 3. Test execution log

### Backend suite run 1

```text
cd backend
python manage.py test library users payments backend --verbosity=2

Ran 258 tests in 117.121s
OK (skipped=1)
System check identified no issues (0 silenced).
```

Skipped: `library.test_generation.GenerationJobConcurrentEnqueueTests.test_two_threads_create_one_active_job` — SQLite `database is locked` (pre-existing, as claimed).

### Backend suite run 2 (order / flake check)

```text
python manage.py test library users payments backend --verbosity=2

Ran 258 tests in 229.035s
OK (skipped=1)
```

Same 258 / 1 skipped / 0 failed. Slower wall clock, not a flake. `cache.clear()` in checkout/entitlement `setUp` is present; no 429 failures across the two full runs.

### Migrations

```text
python manage.py makemigrations --check --dry-run
No changes detected
```

`library/migrations/0025_book_price_tiyin.py` exists and was applied in both test DBs (`Applying library.0025_book_price_tiyin... OK`).

### Frontend

```text
cd frontend
npm test    # vitest run

Test Files  21 passed (21)
     Tests  106 passed (106)
Duration  26.00s
```

Frontend already types `book_price_tiyin?: number | null` (`frontend/src/types/library.ts`) and uses it on `BookDetailPage`. No contract break observed.

### E2E (Playwright)

First attempt: **6 failed** in ~1ms each — Chromium missing (`chrome-headless-shell.exe` not installed). After `npx playwright install chromium`:

```text
npm run test:e2e:prepare
npx playwright test e2e/entitlement.spec.ts e2e/reader-xss.spec.ts e2e/payment-checkout.spec.ts e2e/auth-catalog.spec.ts e2e/logout.spec.ts

  6 passed (56.5s)
```

`seed_e2e ok owner=e2e_owner pd=e2e-public-domain licensed=e2e-licensed`. Guest SPA hits `POST /api/token/refresh/` → **401** (no cookie), not 429. There is **no** spec that waits out access-token expiry or asserts a 7-day refresh cookie.

`e2e/payment-checkout.spec.ts` only mocks transaction status and visits `/payment/status/...` unauthenticated. It does **not** exercise real checkout or webhooks.

### Dependency audit

```text
# from backend/ (wrong cwd vs CI)
python ..\scripts\ci_pip_audit_high.py
ERROR:pip_audit._cli:invalid requirements input: requirements.lock.txt
pip-audit failed without JSON output
exit 2

# from repo root (how CI runs it)
python scripts/ci_pip_audit_high.py
pip-audit: no HIGH/CRITICAL vulnerabilities found
exit 0

cd frontend
npm audit --audit-level=high
found 0 vulnerabilities
exit 0
```

### Extra runtime module (not in CI invocation)

`python manage.py test qa_runtime_verify` plus `library.test_purchase_access` after the watermark fix: watermark/pricing/statement/admin/throttle-429/guards **ok**; `test_relaxed_rate_allows_21_refreshes` **ok** only when the process is started with `E2E_RELAX_THROTTLE=1` and `DEBUG=True`.

## 4. Findings

### 4.1 Payme GetStatement

**How:** Read `payme.py` `_statement`; ran existing `PaymeGetStatementTests` (webhook POST); added `qa_runtime_verify.QaPaymeStatementTests.test_statement_shape_and_missing_create_time_fallback` with `raw_payload` missing `create_time`.

**Result:** Pass

**Evidence:** Webhook JSON `jsonrpc=2.0`, `result.transactions[]` keys: `id`, `time`, `amount`, `account.order_id`, `create_time`, `perform_time`, `cancel_time`, `transaction`, `state`, `reason`. Fallback row: `time`/`create_time` == `int(created_at.timestamp()*1000)` when `create_time` absent (`debug-d91e83.log` hypothesis A). Inclusive window / skip empty Payme id covered by existing tests.

**Bug:** None. Coverage gap only (fallback now exercised).

### 4.2 Refresh TTL + throttle

**How:** Login API cookie inspect; 22 POSTs to `users:api-token-refresh`; subprocess `django.setup()` with `E2E_RELAX_THROTTLE=1` / `DEBUG=False`; 21 refreshes with process-level 1000/min.

**Result:** Pass with caveat

**Evidence:**

- `SIMPLE_JWT['REFRESH_TOKEN_LIFETIME']` = 7 days; login cookie `max-age` = **604800** (`debug-d91e83.log` hypothesis B).
- Attempt 20 = 200, attempt 21 = **429** `Request was throttled. Expected available in 60 seconds.` (hypothesis C).
- `token_refresh: 20/min` is in `DEFAULT_THROTTLE_RATES` (`settings.py`). Unregistered-scope footgun **does not apply**.
- `E2E_RELAX_THROTTLE=1` + `DEBUG=False` → `ImproperlyConfigured` at `settings.py:221` (hypothesis F).
- Same env + `DEBUG=True` → rates `token_refresh=1000/min`, `auth=1000/min`; 21 refreshes **no 429**.
- Caveat: `override_settings(REST_FRAMEWORK=...)` did **not** change live throttle (21st still 429 at 1000/min override). Relaxation is import-time mutation, which is what E2E/CI actually do.

**Not covered:** waiting 7 days / forging JWT `exp`; no Playwright assertion on `Max-Age`.

### 4.3 Per-book pricing (`price_tiyin`)

**How:** Checkout API with `price_tiyin=250000` and `None`; second checkout after changing price; admin GET change form; Payme `CheckPerformTransaction` with 999000 vs snapshotted 250000.

**Result:** Pass

**Evidence:**

- Custom checkout `amount_tiyin=250000`, `PaymentTransaction.amount=250000`.
- `price_tiyin=None` → `100000` (`BOOK_PRICE_TIYIN` under `@override_settings`).
- After raising book price to 999000, reused pending tx still `amount=250000`, same `transaction_id`.
- CheckPerform with 999000 → error `-31001`; with 250000 → `{"allow": true}` (`debug-d91e83.log` hypothesis D). Completing payment therefore stays on the **snapshot**, not the new catalog price (report tradeoff confirmed).
- Admin HTML contains `name="price_tiyin"` (fieldset is actually rendered).

**Not covered:** clicking Save in a live `/admin/` session (form field presence only).

### 4.4 PDF watermarking / DRM

**How:** Two JWT users download licensed PDF; public-domain download vs stored file bytes; unpublished licensed slug; `stamp_pdf_bytes` on ~40MB buffer; pypdf `PdfWriter`/`PdfReader`.

**Result:** Fail then **Pass after fix**

**Evidence (pre-fix):** Real pypdf PDF tail `startxref\n256\n%%EOF\n` became `startxref\n256\n\n% LibroUZ-license: ...\n%%EOF\n` → `PdfReadError: startxref not found`. Toy `%PDF-1.4 licensed` tests still passed (no xref).

**Fix:** `library/pdf_watermark.py` `stamp_pdf_bytes` now **appends** the comment after the original bytes. Regression: `test_stamp_appends_after_eof_preserving_startxref`. Post-fix log: `parser: pypdf-real`, `parsed_ok: true`, size 482.

**Other checks:** Two buyers’ bodies differ; markers `email|purchase:{id}`; public-domain `public_unmodified: true`, no `LibroUZ-license:`; unpublished → **404** (`_published_book` before stamp); licensed without purchase still 403 in existing tests. Order in `BookPdfMediaView.get`: published → `user_can_access_book` → file exists → then stamp. No auth bypass.

**Performance:** `stamp_pdf_bytes` on **41,943,086** input bytes: **~31–71 ms**, +47 bytes, peak = full file in memory. This is **not** a full HTTP 50MB download through Gunicorn/nginx and does not restore `Range`. Report’s “reads whole file, no Range” is confirmed as behavior; cost of the stamp itself is small vs I/O.

### 4.5 CI config

**How:** `git diff .github/workflows/ci.yml`; string presence of the test command; job keys parsed from the file. PyYAML is **not** installed; GitHub `actionlint` not available.

**Result:** Pass with caveat (no dedicated YAML linter binary)

**Evidence:** Diff is exactly adding `payments` to `python manage.py test library users payments backend --verbosity=1`. Job names: `dependency-audit`, `frontend-tests`, `backend-tests`, `e2e`. File is standard GHA YAML and loaded by git/diff without structural breakage.

### 4.6 Dead code

**How:** ripgrep `_serialize_similar_books` over the repo.

**Result:** Pass

**Evidence:** Only `IMPLEMENTATION_REPORT.md` (prose) and `backend/library/api/books.py` (live helper). No remaining `catalog.py` definition or import.

### 4.7 FOLLOWUP.md / docs

**How:** grep `admin-marked`, `out of scope`, `checkout out of scope` in `*.md`; `git ls-files "*.md"`; working-tree existence checks.

**Result:** Pass with process failures

**Evidence:** No remaining “payments out of scope / admin-marked only” in README, ARCHITECTURE, FOLLOWUP. ARCHITECTURE and FOLLOWUP correctly describe Payme/Click checkout. They (and `settings.py` error strings) still point at **`PAYMENTS.md` and `DEPLOY.md`**, which are missing from the working tree (`PAYMENTS.md` is not in git at all; `DEPLOY.md` is `D` in `git status`). `PROJECT_AUDIT.md` also deleted in WT (`git ls-files` still lists it). `IMPLEMENTATION_REPORT.md` is `??` untracked. `PROJECT_ANALYSIS.md` is absent (implementation pass said so).

### 4.8 Security re-check

**How:** Code order in `media_views.py`; `DEFAULT_THROTTLE_RATES`; existing `ProductionSettingsRejectionTests` + `backend.test_settings_guards` in both full suite runs; E2E_RELAX subprocess.

**Result:** Pass (this pass did not loosen guards)

**Evidence:** Weak SECRET_KEY / `ALLOWED_HOSTS=*` / missing Redis / console email / CSRF wildcards still fail closed when `DEBUG=False` (tests `ok` in both 258-test runs). Watermark is after entitlement. `token_refresh` rate is registered. `audit_full_runner.py` still omits `token_refresh` in its local throttle override dict (script-only drift, not production settings).

### 4.9 Manual smoke / core flows

**How:** Playwright specs above as a stand-in for register/login/catalog/entitlement/logout/notifications list; Django tests for reviews/progress remain in the 258-run; **no** Docker Compose, **no** live `/admin/` click-through, **no** 15-minute wait for access JWT expiry.

**Result:** Pass with caveat (automated subset only)

**Evidence:** Register → catalog → public-domain detail **ok**. Login owner → catalog **ok**. Licensed without purchase → UI blocked + reader API 403 **ok**. Logout → login redirect **ok**. Notifications `GET /api/notifications/?page=1` 200 during those flows. XSS flip reader **ok**. Checkout E2E is a stub. PDF listen/flip of a public-domain book in the browser was **not** re-run (`reader-pdf` / `reader-listen` / `reader-flip` not in this subset).

## 5. Bugs found and fixed in this pass

1. **Licensed PDF stamp broke `startxref` for strict parsers**  
   - **Where:** `backend/library/pdf_watermark.py` `stamp_pdf_bytes` (was insert-before-last-`%%EOF`).  
   - **Why in-scope:** Monetary/DRM claim “file is not corrupted” was false for pypdf; fix is a few-line change, not a redesign.  
   - **Regression test:** `PurchaseMediaAccessTests.test_stamp_appends_after_eof_preserving_startxref`.  
   - **Debug instrumentation** is still in `stamp_pdf_bytes` (`#region agent log` → `debug-d91e83.log`) and should be removed after this report is accepted.

## 6. Bugs found and NOT fixed (handed back)

1. **Docs process:** Restore `DEPLOY.md` (deleted in WT, still in git), restore or rewrite `PAYMENTS.md` (referenced, never in git), restore `PROJECT_AUDIT.md` if it was not meant to vanish, commit `IMPLEMENTATION_REPORT.md` if it is the handoff artifact. Do not leave FOLLOWUP pointing at missing files.  
2. **Throttle tests in `users/tests.py` only check `throttle_scope` / class list** — they would not catch an unregistered rate or a throttle that never fires. A 21× POST test belongs in CI.  
3. **`override_settings` cannot raise `token_refresh`** — anyone testing relax via TestCase overrides will get a false negative. Document or test via subprocess/env like CI.  
4. **No Range / full-file RAM on licensed PDF** — quantified stamp CPU is tens of ms at ~40MB; production risk is still buffering the whole file per download (as the implementation report warned). Needs product/perf decision, not a drive-by cache.  
5. **Watermark is strip-able** (append comment). Visible overlay still open.  
6. **Pending checkout amount freeze** — confirmed; if product wants “always latest catalog price”, that is a design change.  
7. **`e2e/payment-checkout.spec.ts` is not a payment test** — mocked status page only. Real Payme/Click sandbox certification still required.  
8. **No E2E for silent refresh inside 7 days** — SPA does call `/api/token/refresh/` (401 when logged out). Expiry window unproven in browser.  
9. **`backend/scripts/audit_full_runner.py`** throttle dict omits `token_refresh` / `payment_checkout`.  
10. **Local `pip-audit` from `backend/` fails** because `LOCKFILE = 'requirements.lock.txt'` is repo-root relative — CI is fine; a developer running the script in `backend/` is not.

## 7. Confidence assessment

- **High confidence (~80%)** that the eight implementation items exist in code, that the Django suite is stable across two full runs, that frontend unit tests still pass, that GetStatement/pricing/throttle-429/cookie max-age/E2E_RELAX guard behave as claimed, and that the watermark parse bug is fixed for pypdf-generated files.  
- **Medium (~15%)** on “safe for production PDF DRM”: only pypdf was used, not Adobe/Chrome/iOS Preview; stamp is still a trivial comment; 40MB was in-process, not a 50MB HTTPS download under Gunicorn workers.  
- **Low (~5%) remaining:** live merchant certification, human admin price edit + subsequent checkout, access-token silent refresh after 15 minutes, Docker Compose production-like boot with Redis, and restoring the missing markdown files.

**Still want a human before production:** Payme/Click sandbox GetStatement + checkout certification; open a stamped licensed PDF in Chrome and a mobile viewer; restore `DEPLOY.md`/`PAYMENTS.md`; strip debug NDJSON from `pdf_watermark.py`; optionally load-test concurrent 40–50MB licensed downloads.
