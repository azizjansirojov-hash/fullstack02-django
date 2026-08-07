# REMEDIATION_REPORT.md — Libro.UZ Fixes 1–5

Branch: `remediation/full-pass-2026-07-30`  
Date: 2026-08-08

Safe incremental remediation: one fix → tests → commit. Public API contracts preserved except additive fields called out below. JWT/CSRF/cookies, payment, TTS providers, and RBAC were not touched.

| Fix | Commit | Summary |
|-----|--------|---------|
| 1 | `8b1cda8` | Sanitize book body on save (bleach); confirm reader XSS escapes |
| 2 | `01f7a51` | Paginate reviews (page size 20) + additive `my_review` |
| 3 | `4bce406` | Cap `activity_timestamps` to 50 most recent |
| 4 | `06fec1d` | Require `ENVIRONMENT=staging` for console email when `DEBUG=False` |
| 5 | `5966572` | Split `api_views` / AppSidebar into submodules |

Verification after Fix 5: backend `189` tests OK (1 skipped); frontend `102` tests OK; `tsc --noEmit` clean.

---

## Fix 1 — XSS defense in depth (reader body)

**Why:** `BookTranslation.body` was stored unsanitized. The SPA does not use `dangerouslySetInnerHTML`, but defense-in-depth on persist reduces risk if a future renderer is less careful.

**What:**
- Added `bleach` and `library/body_sanitize.py` (allowlist tags, no attributes, `strip=True`).
- `BookTranslation.clean()` and `save()` sanitize `body`.
- Backend tests cover script/iframe/`on*` stripping and sanitized manifest output.
- Frontend flip pagination test asserts no executable `<script>` nodes after paginating malicious input.

**No DOMPurify:** Flip builds HTML only after `escapeHtml`; PDF fallback and listen mode render body as React text nodes. A client sanitizer would be unused noise. Documented here deliberately.

**Key files:** `backend/library/body_sanitize.py`, `backend/library/models.py`, `requirements*.txt`, flip pagination tests.

---

## Fix 2 — Review list pagination + `my_review`

**Why:** Unbounded review lists grow with popularity; shelf UI also needed the current user’s review even when it falls off page 1 (`-created_at` order).

**What:**
- `ReviewAPIView.get`: page size 20; catalog-shaped `pagination` (`page`, `num_pages`, `has_previous`, `has_next`, `previous_page`, `next_page`).
- Additive `my_review` when authenticated (serialized own review or `null`).
- Frontend: `getReviews(slug, page?)`, `useBookReviews` load-more, “Yana yuklash” in ReviewSection.

**Key files:** `backend/library/api/reviews.py` (via Fix 5 move), review hooks/types/tests.

---

## Fix 3 — Cap `activity_timestamps`

**Why:** Catalog payloads could include an unbounded timestamp list for weekly activity.

**What:** `serialize_activity_timestamps` returns at most 50 rows, ordered by `-updated_at`. No frontend change (widget only needs recent days).

**Key files:** shared serializer helper (`library/api/_common.py` after Fix 5).

---

## Fix 4 — Console email guard

**Why:** `DEBUG=False` with a console/locmem email backend is unsafe in true production; staging smoke tests still need an explicit escape hatch.

**What:** When `DEBUG=False` and backend is console/locmem, require both `ALLOW_CONSOLE_EMAIL=1` **and** `ENVIRONMENT=staging`. Compose/`.env.example` and settings guard tests updated.

**Key files:** `backend/backend/settings.py`, compose env wiring, `test_settings_guards.py` / verification tests.

---

## Fix 5 — Module split (`api_views` + AppSidebar)

**Why:** `api_views.py` and `AppSidebar.tsx` were large single modules; conservative split improves navigation without changing routes or UI behavior.

**What:**
- Implementations live under `backend/library/api/` (`_common`, `catalog`, `books`, `progress`, `reviews`).
- `api_views.py` is a thin re-export shim (`api_urls` and existing imports keep working).
- Frontend: `sidebarIcons.tsx`, `SidebarNotifications.tsx`; `AppSidebar.tsx` composes them.
- Test mock path for IntegrityError race updated to `library.api.reviews.Review`.

**Naming note:** The plan proposed `library/views/`, but that package name **shadows** existing `library/views.py` (SPA redirects). The package is therefore `library/api/`.

**Skipped (models / admin):** `models.py` and `admin.py` were not split — high risk to Django app registry, migrations, and import cycles. Out of scope for this pass.

---

## Out of scope (untouched)

- JWT / CSRF / cookie auth settings
- Payment flows
- TTS providers and generation pipelines
- RBAC / staff permissions redesign
- Splitting `models.py` / `admin.py`
- Adding DOMPurify

---

## Follow-ups (optional, not done here)

- Further file-size reduction for `models.py` / `admin.py` only with a dedicated migration-safe plan.
- If a future reader path introduces HTML injection, revisit client-side sanitization then — not before.
