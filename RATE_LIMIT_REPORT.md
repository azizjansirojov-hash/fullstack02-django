# RATE_LIMIT_REPORT.md — Reading progress write throttle

Branch: `remediation/full-pass-2026-07-30`  
Date: 2026-08-08

## Step 0 — Existing pattern

| Piece | Location |
|-------|----------|
| Rates | [`backend/backend/settings.py`](backend/backend/settings.py) → `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']` |
| Class | DRF `ScopedRateThrottle` (no custom subclass file) |
| Wiring | View sets `throttle_classes = [ScopedRateThrottle]` + `throttle_scope = '…'` |
| Read vs write | [`ReviewAPIView.get_throttles`](backend/library/api/reviews.py) returns `[]` for `GET`, else `super().get_throttles()` |

Scopes already present: `auth` (`5/min`), `password_reset` (`5/min`), `rights_report` (`5/hour`), `review_write` (`10/min`).

**User vs IP:** `ScopedRateThrottle` keys by authenticated user id when logged in, else by IP. Progress views require auth → per-user.

**E2E_RELAX_THROTTLE:** Only raises `auth` to `1000/min` when `DEBUG=True`. It does **not** relax `review_write` / `password_reset` / `rights_report`. New scope follows that convention (not relaxed by E2E).

**Tests:** `test_review_write_throttle_returns_429_after_limit` patches `ScopedRateThrottle.get_rate` to `'2/min'` — same approach used here (plus `cache.clear()` between throttle tests to avoid LocMem bleed).

**Frontend:** No 429 handling in `frontend/src/api` — no UI changes.

---

## Change

| Item | Value |
|------|--------|
| Scope | `reading_progress` |
| Rate | `30/min` (headroom above ~50s heartbeat; blocks rapid-fire) |
| View | [`ReadingProgressAPIView`](backend/library/api/progress.py) |
| Applied to | PUT/POST upsert only |
| GET | Unthrottled via `get_throttles()` → `[]` |
| 429 | Default DRF (`Retry-After` present) |
| Unchanged | Fix 1 `minutes_delta` gap/ceiling; other throttle rates |

Also listed `reading_progress` (and missing `review_write`) at high rates in [`audit_full_runner.py`](backend/scripts/audit_full_runner.py) so the audit script is not blocked.

---

## Tests

| Suite | Result |
|-------|--------|
| Backend `library users backend` | OK (see commit run; includes new throttle cases) |
| Frontend `npm test -- --run` | unchanged (no FE files) |
| Typecheck | unchanged |

New cases in `library/test_activity_goal.py`:

- write throttle → 429 after patched `2/min`
- GET still 200 after write throttle exhausted

---

## Unaffected

- GET `/api/library/<slug>/progress/`
- `auth`, `password_reset`, `rights_report`, `review_write` rates
- `ReadingStatusAPIView` (no throttle added)
- No global middleware rate limiting
