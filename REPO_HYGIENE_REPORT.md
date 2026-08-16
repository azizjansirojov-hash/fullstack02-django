# REPO_HYGIENE_REPORT.md

Hygiene and integrity pass against `DEBUG_VERIFICATION_REPORT.md` §4.7, §5 (debug instrumentation), and §6 items 1, 9, 10, plus the throttle-test gap in §6 item 2. Date: 2026-08-16.

## 1. Summary

Missing operator docs are now real files: `PAYMENTS.md` was written from the live `payments/` implementation (it had never been in git), and `DEPLOY.md` was restored from `HEAD` then corrected so per-book `price_tiyin` is documented. `PROJECT_ANALYSIS.md` (the 16 August 2026 comprehensive audit) is committed. `PROJECT_AUDIT.md` was **not** restored; it is superseded and indexed in `AUDITS.md`. Debug NDJSON was stripped from `stamp_pdf_bytes`, `qa_runtime_verify.py` was deleted after migrating unique coverage into the real suite, and a tracked `debug-c49e1c.log` was removed. `CookieTokenRefreshAPIView` now has a 21-request 429 test; `audit_full_runner.py` relaxes `token_refresh` and `payment_checkout`; `ci_pip_audit_high.py` resolves `requirements.lock.txt` from the repo root. Backend **262** tests (1 skipped) pass; frontend **106** pass; pip-audit succeeds from both the repo root and `backend/`; npm audit high+ is clean. Prior implementation/debug working-tree changes are committed on `main`. Push result is recorded in section 4.

## 2. Per-item report (Part A, items 1–8)

### 1. `PAYMENTS.md`

- **Status:** Done
- **Files:** [`PAYMENTS.md`](PAYMENTS.md)
- **What changed:** New operator doc covering checkout, `price_tiyin` snapshot/reuse, Payme Basic `Paycom` auth (not X-Auth), GetStatement, Click MD5 Prepare/Complete, unused `CLICK_TEST_MODE`, entitlement fulfill/revoke, env guards, and the mocked E2E/certification caveat.
- **Evidence:** Grep of `PAYMENTS.md` references (`ARCHITECTURE.md`, `FOLLOWUP.md`, `settings.py`, `.env.example`, `click.py`) now resolve to this file. Content matches `payment_service.py`, `payme.py`, `click.py`, `views.py`, `entitlement.py`.

### 2. `DEPLOY.md` / `PROJECT_AUDIT.md`

- **Status:** Done with correction
- **Files:** [`DEPLOY.md`](DEPLOY.md), [`AUDITS.md`](AUDITS.md), [`FOLLOWUP.md`](FOLLOWUP.md); `PROJECT_AUDIT.md` deleted
- **What changed:** Restored `DEPLOY.md` from `HEAD` (`git checkout HEAD -- DEPLOY.md`). The HEAD copy already matched Compose (loopback `127.0.0.1:8000:8000`, `libro` Postgres, TLS overlay, `scripts/backup_postgres_media.sh`). **Correction:** env table now states that `Book.price_tiyin` can override the global catalog price and is snapshotted at checkout. `PROJECT_AUDIT.md` was last added in `a49a423` as a general audit overlapping `PROJECT_ANALYSIS.md`; it was treated as superseded, not restored. `AUDITS.md` records that judgment; `FOLLOWUP.md` points at the index.
- **Evidence:** `DEPLOY.md` present; `git ls-files PROJECT_AUDIT.md` empty after the docs commit; `AUDITS.md` lists the four audit/hygiene reports.

### 3. `PROJECT_ANALYSIS.md`

- **Status:** Done
- **Files:** [`PROJECT_ANALYSIS.md`](PROJECT_ANALYSIS.md)
- **What changed:** The original 2026-08-16 comprehensive audit (present in the working tree, never previously tracked) is now in git. Not fabricated.
- **Evidence:** `git ls-files PROJECT_ANALYSIS.md`; title and date match the document the implementation pass cited.

### 4. Implementation and debug reports

- **Status:** Done
- **Files:** [`IMPLEMENTATION_REPORT.md`](IMPLEMENTATION_REPORT.md), [`DEBUG_VERIFICATION_REPORT.md`](DEBUG_VERIFICATION_REPORT.md) (this file)
- **What changed:** Both prior handoff reports are tracked. Historical claims that `PAYMENTS.md` was missing are left intact; this report is the close-out.
- **Evidence:** Both paths are versioned in the reports commit.

### 5. Debug instrumentation

- **Status:** Done
- **Files:** [`backend/library/pdf_watermark.py`](backend/library/pdf_watermark.py); deleted `backend/qa_runtime_verify.py`; deleted tracked `debug-c49e1c.log`
- **What changed:** Removed `#region agent log` NDJSON from `stamp_pdf_bytes` (append-after-EOF behavior unchanged). Deleted scratch `qa_runtime_verify.py` after migrating: GetStatement `create_time` fallback, 21st refresh 429, CheckPerform vs snapshot after price change. Did **not** migrate the 40MB stamp timing test. Did **not** delete tracked `backend/scripts/verify_reader_bugs.py` (older helper, not this debug pass). Root `.gitignore` already has `*.log`. Deleted local `debug-d91e83.log` and the tracked `debug-c49e1c.log`.
- **Evidence:** `pdf_watermark.py` has no log I/O; ripgrep for `#region agent log` / `qa_runtime_verify` hits only historical report prose.

### 6. Token refresh throttle test

- **Status:** Done
- **Files:** [`backend/users/tests.py`](backend/users/tests.py)
- **What changed:** `CookieTokenRefreshThrottleTests.setUp` clears cache; `test_21st_refresh_returns_429` logs in, POSTs `users:api-token-refresh` 21 times, asserts 20×200 then 429. Wiring test kept.
- **Evidence:** Full suite: `test_21st_refresh_returns_429 ... ok`

### 7. `audit_full_runner.py` throttle dict

- **Status:** Done
- **Files:** [`backend/scripts/audit_full_runner.py`](backend/scripts/audit_full_runner.py)
- **What changed:** Override dict now includes `'token_refresh': '10000/min'` and `'payment_checkout': '10000/min'` so local audit runs do not 429 on those scopes.
- **Evidence:** Dict keys match `DEFAULT_THROTTLE_RATES` in `settings.py`.

### 8. `ci_pip_audit_high.py` lockfile path

- **Status:** Done
- **Files:** [`scripts/ci_pip_audit_high.py`](scripts/ci_pip_audit_high.py)
- **What changed:** `LOCKFILE = str(Path(__file__).resolve().parent.parent / 'requirements.lock.txt')`.
- **Evidence:** `python scripts/ci_pip_audit_high.py` (repo root) and `python ..\scripts\ci_pip_audit_high.py` (from `backend/`) both: `pip-audit: no HIGH/CRITICAL vulnerabilities found`.

## 3. Verification results (Part B)

### Backend suite

```text
cd backend
python manage.py test library users payments backend --verbosity=2

Ran 262 tests in 184.029s
OK (skipped=1)
System check identified no issues (0 silenced).
```

Skipped: `library.test_generation.GenerationJobConcurrentEnqueueTests.test_two_threads_create_one_active_job` (SQLite `database is locked`; pre-existing).

New tests in this pass: `test_21st_refresh_returns_429`, `test_missing_create_time_falls_back_to_created_at`, `test_check_perform_uses_snapshotted_amount_after_price_change` — all ok.

### Migrations

```text
python manage.py makemigrations --check --dry-run
No changes detected
```

### Frontend

```text
cd frontend
npm test    # vitest run

Test Files  21 passed (21)
     Tests  106 passed (106)
```

### pip-audit

```text
# repo root
python scripts/ci_pip_audit_high.py
pip-audit: no HIGH/CRITICAL vulnerabilities found
exit 0

# from backend/
python ..\scripts\ci_pip_audit_high.py
pip-audit: no HIGH/CRITICAL vulnerabilities found
exit 0
```

### npm audit

```text
cd frontend
npm audit --audit-level=high
found 0 vulnerabilities
exit 0
```

Playwright was **not** re-run in this hygiene pass (no E2E/product behavior change).

## 4. Git and GitHub state (Part C)

**Remote (no embedded credentials):**

- `origin` fetch/push: `https://github.com/azizjansirojov-hash/fullstack02-django.git`

**Branch:** `main` tracking `origin/main`. Repo history on `main` is direct pushes (no `CONTRIBUTING.md` / PR-only convention). This pass commits on `main`.

**Commits in this pass:**

| Hash | Subject |
|------|---------|
| `7b9b131` | feat: land per-book pricing, Payme GetStatement, and licensed PDF stamp |
| `fe75f50` | docs: add PAYMENTS.md, PROJECT_ANALYSIS.md, and audit index |
| `f4a43cb` | test: assert token_refresh 429 and GetStatement create_time fallback |
| `b772815` | fix: resolve pip-audit lockfile path and audit-runner throttles |
| `ff6a116` | docs: add implementation, verification, and hygiene reports |
| `f64f874` | docs: record hygiene pass commit hashes |

**Push result:** succeeded. `git push origin main` updated `origin/main` from `a49a423` to `f64f874` (`https://github.com/azizjansirojov-hash/fullstack02-django.git`).

**Working tree at report authoring:** reports still untracked until the reports commit; no media/sqlite/pyc intended.

## 5. Open items

- Payme/Click **sandbox certification** (live GetStatement + checkout) is still required; `e2e/payment-checkout.spec.ts` remains a mocked status-page test.
- Licensed PDF stamp is still a strip-able comment; visible overlay, Range/streaming, and 40–50MB download load tests remain product follow-ups (`FOLLOWUP.md`).
- Remember-me (short vs 7-day refresh) was explicitly out of this pass.
- `CLICK_TEST_MODE` is still unused in `ClickProvider` (documented in `PAYMENTS.md`, not changed).
- `override_settings` still cannot raise `token_refresh` at runtime (verification report §6 item 3); the new 429 test uses the process default `20/min`.
- `backend/scripts/verify_reader_bugs.py` still writes NDJSON to `debug-c49e1c.log` if run locally; the log file is gitignored via `*.log` and is no longer tracked.
- Human admin Save of `price_tiyin` and 15-minute access-token silent refresh were not re-smoked in a browser.
