# E2E_VERIFICATION_REPORT.md — `reading_progress` throttle (30/min)

Branch: `remediation/full-pass-2026-07-30`  
Date: 2026-08-08  
Throttle under test: `DEFAULT_THROTTLE_RATES['reading_progress'] = '30/min'` (commit `2b1d303`)

## How the suite was run

Mirrored CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml) `e2e` job):

1. `python manage.py migrate --noinput` + `python manage.py seed_e2e` (`npm run test:e2e:prepare`)
2. `npx playwright test` with `CI=true`, `E2E_RELAX_THROTTLE=1`, `DEBUG=True`

Note: `E2E_RELAX_THROTTLE=1` only raises the **`auth`** rate (`1000/min`). It does **not** relax `reading_progress`, so this run exercised the real **30/min** progress write limit.

Playwright `webServer` started Django on `:8000` and Vite on `:5173` (`workers: 1`, not fully parallel).

---

## Attempt 1 (aborted / non-throttle)

**Result:** 14 failed (with CI retries).

**Cause:** Missing Chromium binary  
`browserType.launch: Executable doesn't exist … chrome-headless-shell.exe`  
(Playwright browsers not installed in this environment.)

**Not a throttle regression** — no HTTP traffic reached the progress endpoint.

**Remediation:** `npx playwright install chromium` (infra only; no app code changes).

---

## Attempt 2 (authoritative)

**Command:** `npx playwright install chromium` then `npx playwright test` with the same env as above.  
**Overall:** **14 passed (2.2m)** — exit code 0.  
**Fix applied for throttle:** **None** (no 429s).

### Spec-by-spec results

| # | Spec file / test | Result | Duration |
|---|------------------|--------|----------|
| 1 | `e2e/auth-catalog.spec.ts` — register, land in library, open PD detail | **PASS** | 14.3s |
| 2 | `e2e/auth-catalog.spec.ts` — login as seeded owner, browse catalog | **PASS** | 9.8s |
| 3 | `e2e/dashboard-ratings.spec.ts` — continue card stars / comment / actions | **PASS** | 12.7s |
| 4 | `e2e/dashboard-ratings.spec.ts` — carousel → modal reviews | **PASS** | 11.6s |
| 5 | `e2e/entitlement.spec.ts` — licensed book gated in UI + API | **PASS** | 10.2s |
| 6 | `e2e/logout.spec.ts` — logout clears session / protects reader | **PASS** | 7.0s |
| 7 | `e2e/password-reset.spec.ts` — SPA password reset | **PASS** | 9.8s |
| 8 | `e2e/reader-flip.spec.ts` — page turn persists across reload | **PASS** | 7.5s |
| 9 | `e2e/reader-listen.spec.ts` — audio overlay advances `currentTime` | **PASS** | 7.1s |
| 10 | `e2e/reader-listen.spec.ts` — pause saves listen progress | **PASS** | 6.7s |
| 11 | `e2e/reader-listen.spec.ts` — toolbar Tinglash without modal hash | **PASS** | 6.4s |
| 12 | `e2e/reader-pdf.spec.ts` — PDF Next persists page | **PASS** | 6.9s |
| 13 | `e2e/reader-xss.spec.ts` — body XSS not executable | **PASS** | 5.8s |
| 14 | `e2e/shelf.spec.ts` — planned → reading → finished | **PASS** | 9.6s |

Reader / shelf / entitlement specs of interest (**8–12, 5, 14**) all passed under the live 30/min limit.

---

## Progress endpoint traffic vs 30/min

From Django `webServer` access logs during Attempt 2:

- **Zero** responses with status **429** on `/api/library/*/progress/`.
- **PUT** progress upserts (writes, throttled): on the order of **~20** across the whole ~2.2m suite for the seeded PD book, with brief clusters of a few PUTs within ~1–2s (e.g. around `02:10:45`–`02:10:47` and `02:11:00`–`02:11:01`).
- **GET** progress (unthrottled): several reads interleaved; all **200**.
- Peak write rate in any one-second window stayed **well below 30/min** (a few concurrent/overlapping heartbeats, not dozens).

**Conclusion:** E2E progress traffic is far from the 30/min ceiling. No pacing changes and no rate bump required.

### Non-throttle noise (for completeness)

Two **500** responses on progress PUT were logged as `sqlite3.OperationalError: database is locked` under concurrent local SQLite writes. Specs still passed (subsequent PUT/GET succeeded). **Unrelated to `reading_progress` throttling**; not fixed in this verification pass (out of scope: E2E-only / throttle verification).

---

## Decision

| Question | Answer |
|----------|--------|
| Did 30/min break E2E? | **No** |
| Pacing vs rate change? | **Neither** — suite green under real limit |
| Relax via `E2E_RELAX_THROTTLE`? | **No** — would be inconsistent with `review_write` and is unnecessary |

No application code was modified in this pass.
