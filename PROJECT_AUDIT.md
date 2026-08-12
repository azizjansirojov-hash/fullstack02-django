# PROJECT_AUDIT

## 1. Project Overview

### Purpose, Scope, and Target Users

This project is a full-stack **digital library management and reading platform**. It supports catalog browsing, authentication, personal library management, reader modes (flip/PDF/audio), reviews/ratings, notifications, and payment-based entitlements.

Primary target users appear to be:
- End users reading/buying books (web UI).
- Admin/operators managing content, generation jobs, and payments (Django admin + ops docs).
- Developers/QA running local, CI, and E2E pipelines.

### Tech Stack

- **Backend**
  - Python 3.12 runtime (`Dockerfile`)
  - Django 6.0.7 (`requirements.lock.txt`)
  - Django REST Framework 3.17.1 (`requirements.lock.txt`)
  - SimpleJWT 5.5.1 (`requirements.lock.txt`)
  - Gunicorn (`requirements.txt`)
  - Redis cache/throttling (`backend/backend/settings.py`)
  - PostgreSQL (Compose uses `postgres:16-alpine`, `docker-compose.yml`)
- **Frontend**
  - React 19.2.7 (`frontend/package.json`)
  - Vite 8.1.1 (`frontend/package.json`)
  - TypeScript ~5.8 (`frontend/package.json`)
  - Vitest 3.2.4 + Testing Library (`frontend/package.json`)
  - Playwright 1.62.0 (`package.json`)
  - `pdfjs-dist` and `page-flip` for reader modes (`frontend/package.json`)
- **Infra / Edge**
  - Docker + Docker Compose (`Dockerfile`, `docker-compose.yml`)
  - Nginx TLS reverse proxy templates (`deploy/nginx.conf`, `deploy/nginx.local.conf`)

### Project Structure (High-Level)

```text
fullstack02-django/
├─ backend/
│  ├─ backend/                  # Django project config (settings, urls, wsgi)
│  ├─ library/                  # Core domain: books, reader, progress, reviews, notifications
│  ├─ users/                    # Auth, JWT-cookie flows, profile endpoints
│  ├─ payments/                 # Checkout + provider webhooks + entitlement fulfillment
│  ├─ templates/legal/          # Legal pages and rights report views
│  └─ scripts/                  # Verification and helper scripts
├─ frontend/
│  ├─ src/
│  │  ├─ api/                   # Browser API client wrappers
│  │  ├─ auth/                  # Auth context and session bootstrap
│  │  ├─ components/            # UI modules (layout, library, reader, auth)
│  │  ├─ pages/                 # Route-level pages
│  │  └─ lib/                   # Shared frontend logic/hooks/utilities
│  └─ package.json
├─ e2e/                         # Playwright end-to-end tests
├─ deploy/                      # Nginx and deployment templates
├─ .github/workflows/           # CI and dependency audit workflows
├─ Dockerfile
├─ docker-compose.yml
└─ docs/*.md                    # Architecture/deployment documentation
```

---

## 2. Architecture & Design

### Architectural Pattern

The codebase is a **modular monolith**:
- Django monolith backend with app-level boundaries (`library`, `users`, `payments`).
- React SPA frontend served same-origin in production via `FRONTEND_DIST` (`backend/backend/settings.py:156-174` and route fallbacks in `backend/backend/urls.py`).
- Layered API-oriented architecture: UI -> typed API client -> DRF views/services -> ORM models -> DB.

### Data Flow

1. Browser loads React app and bootstraps auth via `/api/csrf/` and `/api/me/` (`frontend/src/auth/AuthContext.tsx:72-97`).
2. Frontend API requests include cookies and CSRF header for unsafe methods (`frontend/src/api/client.ts:31-39`).
3. DRF endpoints enforce authentication/permissions and throttles (`backend/backend/settings.py:195-214`).
4. Business logic in `library` and `payments` accesses ORM models and writes state.
5. Payment webhooks verify signatures and transition `PaymentTransaction` then entitlement (`Purchase`) state.

### Design Patterns (Good and Bad)

Good usage:
- **Service-ish separation in payments** (`payment_service.py`, provider modules in `payments/providers`).
- **Provider strategy pattern** by gateway (`payme.py`, `click.py`, base abstractions).
- **Explicit startup guards** against insecure production config (`backend/backend/settings.py:43-55`, `242-249`, `281-286`).
- **Idempotency-focused webhook tests** (`backend/payments/tests/test_webhooks_idempotency.py`).

Risky/weak usage:
- Some test “guards” mirror settings logic instead of testing real startup behavior (`backend/backend/test_settings_guards.py`).
- Catalog helper code path contains undefined symbols (dead/broken function) in `backend/library/api/catalog.py:202-223`.
- Reader-heavy modules are statically imported from route path (performance anti-pattern).

### Database Schema / Models Overview

Core relationships inferred from `backend/library/models.py` and `backend/payments/models.py`:
- `Book` -> many `BookTranslation`, `AudioChapter`, `Review`, `ReadingProgress`, `Purchase`, `GenerationJob`.
- `User` -> one `UserPreferences`; many `ReadingProgress`, `ReadingSession`, `Notification`, `PaymentTransaction`.
- `PaymentTransaction` links user/book/provider transaction lifecycle; entitlement represented via `Purchase`.

Notable constraints:
- Uniqueness on user/book combinations for progress, review, and purchase states.
- Payment transaction uniqueness/indexing around provider IDs and active transaction constraints.

---

## 3. Features Implemented

### Confirmed Working Features

- Authentication flows (register/login/logout/password reset) with cookie-based JWT session model.
- Catalog browsing, book detail pages, category/discovery UX.
- Personal library and progress tracking.
- Reader modes: flip reader, PDF reader, and audio/listen flow.
- Reviews/ratings CRUD and dashboard integration.
- Notifications feed with mark-read operations.
- Payment checkout API + webhook verification for Payme/Click + entitlement grant/revoke.
- Generation health endpoint and background generation workflow.

### Partially Implemented / Potentially Broken

- Payme statement/reconciliation method is a stub (`backend/payments/providers/payme.py:448-450`).
- Click post-paid refund/cancel relies on limited/manual pathways in docs/provider behavior (`backend/payments/providers/click.py` behavior and tests).
- Payment frontend E2E is mocked and does not validate real provider roundtrip (`e2e/payment-checkout.spec.ts:4-7`).
- Broken helper in catalog module likely unused but unsafe if invoked (`backend/library/api/catalog.py:202-223`).

### Missing Common Features (Typical for Production Library Platforms)

- No clear recommendation/search relevance engine beyond core filtering.
- No explicit admin analytics dashboard / KPI telemetry.
- No explicit multi-tenant/org model.
- No visible robust anti-fraud/risk scoring for payments.
- No centralized observability stack integration (Sentry/OTel/Datadog not evident in code/config).

---

## 4. Code Quality Assessment

### Readability, Consistency, Naming

Strengths:
- Overall naming and module boundaries are readable.
- Frontend and backend follow consistent domain naming (`BookDetailPage`, `Purchase`, `PaymentTransaction`).
- Tests are extensive and reasonably organized by feature area.

Issues:
- Mixed test philosophy: some tests validate behavior well; others re-implement target logic (weak signal).
- Some long, dense modules (reader and payment provider files) increase maintenance burden.

### Duplicated / Dead Code

- Potential dead/broken helper in `backend/library/api/catalog.py:202-223` referencing undefined `Book` and `DISPLAY_LANG`.
- Potentially test-like scripts under `backend/scripts/` are not part of standard CI command (`.github/workflows/ci.yml` runs only `manage.py test library users backend`).

### Error Handling

- Rights-report email path can propagate SMTP failures to clients (no local try/except) in `backend/library/legal_views.py:64-70`.
- Payment status polling loop in frontend can retry indefinitely under repeated failures (`frontend/src/pages/PaymentStatusPage.tsx:40-46`).

### Framework Best Practices and SOLID/DRY/KISS

- DRF + auth + throttle best practices are mostly followed.
- Some violations:
  - **DRY/Test realism**: settings guard test duplicates settings logic.
  - **KISS/Robustness**: unbounded polling behavior in payment status.
  - **Single responsibility drift** in very large reader components handling rendering + behavior + sync.

---

## 5. Security Audit

### Authentication & Authorization

Strengths:
- JWT in HttpOnly cookies with refresh and blacklist support (`backend/backend/settings.py:251-259`, auth modules).
- CSRF protections and explicit unsafe endpoint handling.
- Route guards on frontend (`RequireAuth`, `GuestOnly`) avoid rendering protected pages before auth resolution.

Findings:
- **Medium**: Frontend password reset confirm accepts `redirect_url` from API and navigates directly (`frontend/src/pages/PasswordResetConfirmPage.tsx:39-41`, `47`). Should constrain to trusted relative paths.
- **Low design-risk**: Authenticator supports header token fallback (`backend/users/authentication.py:24-28`), increasing blast radius if future endpoints skip CSRF enforcement.

### Input Validation / Sanitization

- **Medium**: Rights report endpoint only lightly validates fields and truncates input, but not strong format/content checks (`backend/library/legal_views.py:46-51`).
- Reader XSS hardening exists in pagination escaping (`frontend/src/components/reader/flipPagination.ts:117-121`), with dedicated E2E XSS test.

### SQL Injection / XSS / CSRF

- No obvious raw SQL injection vectors found in audited paths.
- CSRF posture is generally strong for browser mutation endpoints.
- XSS defenses exist in reader text rendering, but any route/deep-link values should be sanitized/allow-listed.

### Secrets / Credentials / Password Storage

- `backend/.env.example` uses placeholder secret values (acceptable template; risky if copied unmodified).
- Production startup guards reject weak secrets and wildcard host configs (`backend/backend/settings.py:43-55`).
- Password validation uses Django validators (`backend/backend/settings.py:129-141`), and storage relies on Django’s hashed password framework.

### Dependency Security

- CI blocks frontend high+ vulnerabilities and pip audit high+ in main workflow.
- Weekly dependency audit uses `continue-on-error` for some steps (`.github/workflows/dependency-audit.yml`), which can allow lingering known issues.
- Deprecated package signal in frontend lockfile (`frontend/package-lock.json` includes deprecated transitive packages).

### CORS / Env / Config Security

- Same-origin architecture minimizes CORS complexity today.
- No explicit CORS middleware/policy found; if architecture becomes split-origin, explicit secure CORS config is required.
- TLS cookie/security headers are enabled with production flags (`backend/backend/settings.py:324-331`).

---

## 6. Performance & Scalability

### Database Query Efficiency

- Catalog context appears to perform repeated heavy queryset operations and counts per request path (`backend/library/catalog_context.py:47-52`, `164-172`, `194`).
- Positive: query-budget tests exist (`backend/library/test_catalog_perf.py`).

### Caching Strategy

- Redis cache is required in production, which is good.
- Category cache TTL and invalidation behavior may churn under frequent content updates (`backend/library/catalog_context.py:30`, `33-37`; `backend/library/models.py:191-194`).

### API Response Optimization

- Notification list performs main fetch plus unread count query (`backend/library/notification_views.py:24-31`); acceptable at moderate scale but may become hot.

### Frontend Performance

**High impact issue**:
- Heavy reader dependencies are eagerly imported from app route path:
  - `frontend/src/App.tsx:17`
  - `frontend/src/pages/ReaderPage.tsx:4-5`
  - `frontend/src/components/reader/PdfReaderMode.tsx:4-5`
  - `frontend/src/components/reader/FlipBookMode.tsx:3`

Other issues:
- Full repagination/rebuild in flip mode on resize/settings changes can be expensive for long content.
- PDF mode creates wrappers for all pages upfront, even with windowed rendering.

---

## 7. Testing & Reliability

### Existing Coverage

- Backend has broad integration test coverage (auth, catalog, reader, reviews, payments, webhook idempotency).
- Frontend has substantial unit/component tests (reader, pages, reviews, notifications).
- E2E suite covers auth, entitlement, reader modes, reviews, and payment flow skeleton.

### Missing Critical Tests

- No dedicated frontend tests for:
  - `frontend/src/pages/PaymentStatusPage.tsx`
  - `frontend/src/components/library/CheckoutButton.tsx`
  - key auth page variants (login/register/reset confirm pages have sparse direct tests).
- Backend payment status endpoint negative/authorization test depth should increase.
- Payme `GetStatement`/reconciliation branch is not meaningfully tested.

### Reliability Gaps

- E2E has some timing patterns that can be flaky (`waitForTimeout` style usage in reader flows).
- Script-based tests under `backend/scripts/` can create false confidence if not integrated into CI.

---

## 8. DevOps & Deployment Readiness

### Environment and Config Management

Strengths:
- Centralized env-driven settings with strict production guards.
- Redis mandatory in prod mode; CSRF trusted origin validation is explicit.

Gaps:
- **High**: runtime container appears to run as root (no `USER` directive in `Dockerfile`).
- Python lockfile was generated with Python 3.14 while runtime/CI use 3.12 (`requirements.lock.txt:2-5`, `Dockerfile`, `.github/workflows/ci.yml`), risking reproducibility drift.

### Docker / CI-CD

- Good baseline CI: backend tests, frontend tests, E2E, npm/pip audits, smoke deploy checks.
- Dependency-audit workflow has non-blocking steps that can reduce enforcement effectiveness.

### Logging and Monitoring

- Structured logging is configured (`backend/backend/settings.py:401-446`).
- Generation health endpoint exists (`backend/library/health_views.py`).
- Missing centralized monitoring/alerting integration in repo-level config/docs.

### Production-Readiness Checklist (Current Status)

- [x] Auth + CSRF + throttles present.
- [x] Basic deployment docs and Compose setup present.
- [x] Health endpoint for generation worker present.
- [ ] Non-root container runtime.
- [ ] Stronger edge hardening (full security headers/TLS policy baseline).
- [ ] Unified and blocking dependency governance policy.
- [ ] Centralized telemetry/alerts and incident runbook depth.

---

## 9. Dependencies

### Key Dependencies (Observed)

Backend (`requirements.txt` / `requirements.lock.txt`):
- `django==6.0.7`
- `djangorestframework==3.17.1`
- `djangorestframework-simplejwt==5.5.1`
- `django-environ==0.12.0`
- `django-cors-headers==4.9.0` (listed in lockfile)
- `gunicorn==23.0.0`
- `redis==6.4.0`
- `psycopg[binary]==3.2.10`
- `bleach==6.2.0`
- `edge-tts==7.2.8`

Frontend (`frontend/package.json`):
- `react@^19.2.7`
- `react-router@8.3.0`
- `vite@^8.1.1`
- `typescript@~5.8.0`
- `vitest@^3.2.4`
- `pdfjs-dist@^4.10.38`
- `page-flip@^2.0.7`

Root tooling (`package.json`):
- `@playwright/test@1.62.0`
- `concurrently`
- `cross-env`

### Outdated / Deprecated / Risk Signals

- Deprecated transitive npm package(s) present in lockfile (e.g., deprecation marker in `frontend/package-lock.json`).
- Python lock build interpreter mismatch (`requirements.lock.txt` generated with 3.14 while runtime/CI are 3.12).
- `edge-tts` dependency is called out in architecture docs as relying on unofficial upstream behavior (operational continuity risk).

### Unused / Unnecessary Dependencies (Best-Effort)

- No obvious dead major direct dependencies found from static scan, but periodic automated unused-dependency checks are still recommended for both Python and npm.

---

## 10. Critical Issues (Priority List)

### Critical

1. **None conclusively identified** in the audited snapshot.

### High

1. **Frontend bundle/perf risk from eager reader imports**
   - Evidence: `frontend/src/App.tsx:17`, `frontend/src/pages/ReaderPage.tsx:4-5`, `frontend/src/components/reader/PdfReaderMode.tsx:4-5`, `frontend/src/components/reader/FlipBookMode.tsx:3`.
2. **Container hardening gap: runtime as root**
   - Evidence: `Dockerfile` lacks non-root `USER` in runtime stage.
3. **Dependency reproducibility risk: lock interpreter mismatch**
   - Evidence: `requirements.lock.txt:2-5` vs Python 3.12 runtime/CI.

### Medium

1. Direct navigation to backend-provided `redirect_url` in password reset confirm.
2. Unbounded frontend polling/retry in payment status page.
3. Broken helper with undefined identifiers in catalog module.
4. Rights-report API validation/error handling robustness gaps.
5. Catalog query path likely doing repeated heavy DB work.
6. Advisory-only dependency audit workflow portions.
7. Incomplete Payme statement/reconciliation implementation.

### Low

1. Documentation drift and missing referenced docs.
2. Potential cache invalidation churn in category cache strategy.
3. Route/deep-link trust assumptions in notification navigation.

---

## 11. Recommendations & Next Steps

### Quick Wins (1-2 Sprints)

1. **Add route-level lazy loading for reader stack**
   - Use `React.lazy`/`Suspense` for `ReaderPage` and split heavy modules (`pdfjs-dist`, `page-flip`).
2. **Harden redirect handling**
   - Reuse safe redirect resolver in password reset confirm page; allow-list relative internal routes only.
3. **Bound payment status polling**
   - Add max attempts/time budget + explicit failure UX and retry button.
4. **Fix/remove broken catalog helper**
   - Resolve undefined imports or delete dead code path and add tests.
5. **Run container as non-root**
   - Add dedicated app user in Docker runtime stage.
6. **Align lockfile generation with runtime Python version**
   - Regenerate `requirements.lock.txt` under Python 3.12 and enforce in CI.

### Medium-Term Improvements

1. Expand payment tests:
   - Frontend tests for checkout/status pages.
   - Backend negative authorization tests for transaction status.
   - Coverage for Payme `GetStatement` and malformed RPC paths.
2. Improve E2E stability:
   - Replace fixed timeouts with deterministic event/assertion waiting.
3. Optimize catalog and reader performance:
   - Profile queryset/annotation counts.
   - Reduce full repagination cost, improve virtualization boundaries.
4. Strengthen dependency governance:
   - Make weekly audit enforcement policy explicit; triage deprecations promptly.

### Long-Term Refactoring / Platform Hardening

1. Formalize observability:
   - Add centralized error tracking, metrics, and alerting.
2. Define security baseline as code:
   - Nginx security headers/TLS profile templates + automated checks.
3. Introduce architecture fitness tests:
   - Guard against unsafe redirects, auth bypass regressions, and expensive query regressions.

---

## Appendix: Representative Evidence Snippets

```python
# backend/library/api/catalog.py (broken helper path)
similar_qs = list(
    Book.objects.filter(
        category=book.category,
        is_published=True,
    )
)
translation = similar.get_translation(DISPLAY_LANG)
```

```python
# backend/payments/providers/payme.py (stubbed statement)
def _statement(self, rpc_id, params) -> JsonResponse:
    # Minimal stub — empty list for the requested window.
    return _rpc_result(rpc_id, {'transactions': []})
```

```tsx
// frontend/src/pages/PaymentStatusPage.tsx (unbounded polling pattern)
if (!isTerminalStatus(data.status)) {
  timeoutRef.current = window.setTimeout(pollStatus, POLL_INTERVAL_MS)
}
...
timeoutRef.current = window.setTimeout(pollStatus, POLL_INTERVAL_MS)
```

```python
# backend/backend/settings.py (strong production guard examples)
if _weak_by_marker or _weak_by_length:
    if not DEBUG:
        raise ImproperlyConfigured(...)
```

