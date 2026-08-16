# SECURITY_HARDENING_REPORT.md

**Date:** 16 August 2026  
**Scope:** Content Security Policy + related browser headers; licensed PDF visible overlay and forensic markers.

---

## 1. Summary

**CSP:** Enforcing `Content-Security-Policy` is shipped (not Report-Only). Django 6’s built-in `ContentSecurityPolicyMiddleware` is the source of truth for every response Django serves (runserver, Gunicorn, tests, production behind nginx). Vite’s dev server sets a looser DEBUG-only policy on SPA HTML because local/E2E HTML is not served by Django. `django-csp` was not added: Django 6.0.7 already provides `SECURE_CSP` / nonce plumbing; a third-party package would duplicate that and fight the lockfile.

**Watermarking:** `stamp_pdf_bytes` no longer appends a strip-able `% LibroUZ-license:` comment after `%%EOF`. Licensed downloads get a visible ReportLab overlay merged onto every page (pypdf) plus Info, catalog, and XMP identifiers. Public-domain files remain byte-for-byte unmodified. Entitlement order is unchanged: `is_published` → `user_can_access_book` → file exists → stamp.

**Confidence:** High that headers are present, that the SPA E2E walkthrough fires no `securitypolicyviolation` events under the Vite DEBUG policy, that Django admin login/list/change work under the admin policy, and that stamped ReportLab PDFs parse in pypdf with extractable overlay text. Medium on production SPA CSP (Vite HMR tokens are not in the Django policy; production HTML is hashed modules only — not browser-tested with `FRONTEND_DIST` in this pass). Low on “DRM”: this is attribution, not encryption.

---

## 2. Part A — CSP report

### Choice of implementation

Custom settings + Django 6 middleware, not `django-csp`. Justification: this repo is already on Django 6.0.7, which ships `django.middleware.csp.ContentSecurityPolicyMiddleware`, `SECURE_CSP`, and `SECURE_CSP_REPORT_ONLY`. Adding `django-csp` would be a second CSP stack and a hashed lockfile compile. `pip-compile` currently fails on this machine (`pip-tools` 7.4.1 vs pip 26: `cannot import name 'stdlib_pkgs'`), so avoiding an extra dependency was also operationally safer.

`SECURE_CSP_REPORT_ONLY` is `{}` (no Report-Only header). Enforcement is on.

### Final policy values

**Django (production SPA, legal HTML, APIs, media) — enforcing:**

```
default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob:; media-src 'self' blob:; worker-src 'self' blob:; connect-src 'self'; frame-src 'none'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'
```

**Django `/admin/` — enforcing (path override):**

```
default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob:; media-src 'self' blob:; worker-src 'self' blob:; connect-src 'self'; frame-src 'none'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'
```

**Vite DEBUG SPA (`frontend/vite.config.js` `server.headers`) — enforcing:**

```
default-src 'self'; script-src 'self' 'unsafe-eval' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: blob:; media-src 'self' blob:; worker-src 'self' blob:; connect-src 'self' ws://127.0.0.1:5173 ws://localhost:5173 http://127.0.0.1:5173 http://localhost:5173 http://127.0.0.1:8000 http://localhost:8000; frame-src 'none'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'
```

DEBUG Django HTML (legal pages, admin) does **not** get Vite’s `unsafe-eval` / HMR `connect-src`. Those tokens are only on the Vite origin.

### Directive-by-directive justification

| Directive | Sources | Why |
|-----------|---------|-----|
| `default-src` | `'self'` | Fail closed; everything else is explicit. |
| `script-src` | `'self'` (Django); plus `'unsafe-eval' 'unsafe-inline'` on Vite only | SPA and legal JS are files under `/assets` or `/static`. Vite `@vitejs/plugin-react` injects an inline preamble and uses eval for HMR; without those tokens the SPA does not boot (verified: first E2E run failed with “can't detect preamble”). Production Django policy does not include them. |
| `style-src` | `'self'` + `https://fonts.googleapis.com`; Vite also `'unsafe-inline'`; admin `'unsafe-inline'` | Google Fonts CSS in `frontend/index.html` and `templates/base.html`. Vite HMR injects `<style>`. Django 6.0.7 admin changelist still emits a `<style>` block (`admin/change_list.html`). Legal inline `style=` attributes were moved to `static/legal/legal.css`. |
| `font-src` | `'self'` `https://fonts.gstatic.com` `data:` | Sora/Fraunces from Google; possible data-URI fallbacks. |
| `img-src` | `'self'` `data:` `blob:` | Covers under `/media/covers/`, SVG/icons, canvas exports. |
| `media-src` | `'self'` `blob:` | Chapter MP3s from `/library/media/…`; no microphone TTS. |
| `worker-src` | `'self'` `blob:` | `pdfjs-dist` worker (`PdfReaderMode.tsx` sets `workerSrc` to a Vite URL; some PDF.js builds blob the worker). Playwright confirmed canvases render with zero CSP violations. |
| `connect-src` | `'self'` (+ Vite WS/HTTP localhost) | `frontend/src/api/client.ts` only `fetch`es same-origin `/api/*` (proxied). Payme/Click are **top-level navigations** (`window.location.assign` in `CheckoutButton.tsx`), not XHR. Vite HMR needs `ws://127.0.0.1:5173` because `'self'` does not match the `ws:` scheme. |
| `frame-src` | `'none'` | Checkout is not an iframe. Mocked payment E2E still passed. |
| `frame-ancestors` | `'none'` | Matches `XFrameOptionsMiddleware` / `X_FRAME_OPTIONS = 'DENY'`. |
| `object-src` | `'none'` | No plugins / `<object>` PDFs. |
| `base-uri` | `'self'` | Blocks `<base>` hijack. |
| `form-action` | `'self'` | Admin logout, legal form (JS posts to `/api/rights-report/`). Gateway checkout is not a form POST. |

### Other headers

- `Referrer-Policy: strict-origin-when-cross-origin` via `SECURE_REFERRER_POLICY` (SecurityMiddleware). Django’s default was `same-origin`.
- `X-Content-Type-Options: nosniff` set explicitly (`SECURE_CONTENT_TYPE_NOSNIFF = True`; SecurityMiddleware already defaulted True).
- `Permissions-Policy` denying camera, microphone, geolocation, payment, USB, motion sensors, `browsing-topics`; allowing `fullscreen=(self)` (PDF reader) and `autoplay=(self)` (listen mode). Set by `BrowserHardeningMiddleware`. TTS is `<audio src>` of our files, not `getUserMedia`.

### Where the header is set (source of truth)

| Environment | CSP owner | Why |
|-------------|-----------|-----|
| Production (nginx → Gunicorn) | **Django only** | Per-path admin vs SPA policy; nginx cannot mint a matching nonce if we add one later. Duplicate `add_header Content-Security-Policy` would be undefined. `deploy/nginx.conf` keeps HSTS only and comments this decision. |
| Django runserver / tests | Django | Same middleware. |
| Local/E2E Vite `:5173` | **Vite `server.headers`** | SPA HTML never hits Django in dual-stack mode. |

### Verification evidence

- Django: `backend/backend/test_security_headers.py` — `/terms/` enforcing CSP (no Report-Only, no script `unsafe-inline`/`unsafe-eval`), rights-report HTML has no `<script>` block, admin login/changelist/add form use the admin policy.
- Playwright `e2e/csp-hardening.spec.ts`: `document.addEventListener('securitypolicyviolation')` on login, register, catalog, public-domain detail, PDF reader (canvas count > 0), flip, listen, mocked `/payment/status/…`, and Django `/admin/` login → index → book changelist → change form. **Zero violations** on the passing run.
- Payme/Click: existing mocked `e2e/payment-checkout.spec.ts` plus CSP walkthrough of the status page. No iframe/`form-action` to `checkout.paycom.uz` / `my.click.uz` is required for the current `location.assign` flow.

### Directives not fully locked down

1. **Vite DEBUG `script-src 'unsafe-inline' 'unsafe-eval'`** — required for React Refresh preamble + HMR. Follow-up: production already omits them; optionally hash the Vite preamble or use `plugin-react` nonce if local CSP must be as strict as prod.
2. **Admin `style-src 'unsafe-inline'`** — Django 6.0.7 changelist `<style>` plus staff `mark_safe` color spans in `library/admin.py`. Follow-up: move admin inline CSS to a file; stop using inline `style=` in `mark_safe`.
3. **Google Fonts** — third-party CSS/font. Follow-up: self-host Sora/Fraunces and drop `fonts.googleapis.com` / `fonts.gstatic.com`.

---

## 3. Part B — Watermark/DRM report

### What shipped

`library/pdf_watermark.py` `stamp_pdf_bytes` (same name, same call site in `BookPdfMediaView`):

1. **Visible overlay** — ReportLab draws semi-transparent diagonal repeats plus a footer line containing `LibroUZ-license: {email}|purchase:{id} {UTC timestamp} #{sha256[:16]}`. Merged onto every page with pypdf `merge_page`. This is page content (text operators), not a comment or optional content group.
2. **Structural markers** — document Info `/LibroUZ-License`; catalog `/LibroUZ` `/LicenseId` + `/LicenseHash`; XMP `librouz:licenseId` / `librouz:licenseHash` (`https://libro.uz/ns/pdf/1.0/`).

**Library choice:** ReportLab (already locked) for drawing; **pypdf 6.14.2** for merge/metadata (pure Python, used in the prior debug pass to catch the `startxref` bug). pikepdf/PyMuPDF would need extra native libs; not justified for this pass.

`pypdf` was added to `requirements.txt` and `requirements.lock.txt` (wheel + sdist sha256 from PyPI). Full `pip-compile --generate-hashes` was **not** re-run: pip-tools 7.4.1 is incompatible with pip 26 on this host.

### What this can and cannot survive

| Attack / process | Visible overlay | Info / catalog / XMP |
|------------------|-----------------|----------------------|
| Opening in a normal viewer / print / screenshot | Survives as pixels (screenshot does not remove it from the photo; it also does not keep a machine-readable ID unless OCR) | N/A |
| Deleting a trailing PDF comment in a text editor | Survives (no longer a trailing comment) | Survives |
| Cropping page edges | Diagonal repeats help; a tight crop of body text can still remove most of the overlay | Survives |
| “Save as” / print to PDF / some online compressors | Often flattened into the page (good) **or** rasterized without text (OCR needed) | **Often stripped** |
| Metadata-stripping tools / `exiftool` / re-export | Overlay may remain | **Likely gone** |
| Re-typesetting / copying text into a new document | Gone | Gone |

This is **not** encryption, Adobe DRM, or a watermark that survives a determined re-typeset. It identifies a leak if the file is shared in a form that keeps page content and/or metadata.

### Generation-time vs download-time

Still **download-time** in `BookPdfMediaView`. Unique per purchase (and timestamp) cannot be pre-generated once per title without a per-purchase object-storage cache (out of scope).

### Performance (realistic large file)

Fixture: 1-page ReportLab PDF + 42 MiB embedded file (`pad.bin`), **44,041,723** input bytes.

| Method | Wall time | tracemalloc peak | Output size |
|--------|-----------|------------------|-------------|
| Old comment-append | **9.5 ms** | 44.0 MB | 44,041,772 |
| New overlay + markers (after copying attachments) | **69.0 ms** | 93.7 MB | 44,044,348 |

The overlay itself is tens of milliseconds; cost is dominated by rewriting the whole file (peak ~2× input). pypdf does not stream this. HTTP Range is still not offered on stamped responses (full `BytesIO`).

**Mitigation in this pass:** copy embedded files so a large attachment is not silently dropped (an early measurement showed 3.8 KB output because `append()` dropped `/EmbeddedFiles`). **Not done:** async job / object-storage pre-stamp / streaming merge — needs a larger design.

### Entitlement ordering (unchanged)

`BookPdfMediaView.get`:

1. `_published_book` → 404 if unpublished  
2. `user_can_access_book` → 403  
3. missing `pdf_file` → 404  
4. public-domain → `FileResponse` of the original file (no stamp)  
5. licensed → load purchase, then `stamp_pdf_bytes`

Verified by `test_stamp_not_called_without_purchase_or_when_unpublished` (`patch` on `library.media_views.stamp_pdf_bytes`: 403 and 404, `assert_not_called`).

### Watermark tests

| Test | Result |
|------|--------|
| `test_licensed_pdf_embeds_purchase_identifier` | pass (extract_text + Info) |
| `test_two_purchases_embed_different_identifiers` | pass |
| `test_stamp_real_pdf_remains_parseable_with_startxref` | pass (replaces comment-append startxref test; real ReportLab PDF) |
| `test_visible_overlay_is_page_content_not_trailing_comment` | pass (rewrite, text on both pages) |
| `test_public_domain_pdf_is_not_watermarked` | pass (byte-identical to stored file) |
| `test_stamp_not_called_without_purchase_or_when_unpublished` | pass |
| `test_stamp_preserves_embedded_file_attachment` | pass |

No desktop PDF GUI in this environment; overlay presence is from pypdf `extract_text` (repeated license strings on each page). PDF.js in Playwright rendered canvases for the **public-domain** E2E book (unwatermarked, as designed).

---

## 4. Full verification results

### Backend

```text
cd backend
python manage.py test library users payments backend --verbosity=1

Ran 269 tests in 339.310s
OK (skipped=1)
```

Skipped: `library.test_generation.GenerationJobConcurrentEnqueueTests.test_two_threads_create_one_active_job` (SQLite `database is locked`; pre-existing).

Targeted watermark + headers (earlier in the pass): 21 tests, OK.

### Playwright

First full run after Vite CSP without `unsafe-inline` **failed** (React Refresh preamble blocked). After adding Vite-only `unsafe-inline`/`unsafe-eval`:

```text
npx playwright test
  20 passed (2.2m)
```

That includes `e2e/csp-hardening.spec.ts` (catalog/detail/PDF.js/flip/listen/checkout status/admin) and the previous 15 product specs.

### Stamp microbench

See §3 table (44 MB input, 69 ms overlay vs 9.5 ms comment-append).

---

## 5. Open items / recommendations for next pass

1. **Pre-stamp architecture** — per-purchase overlay in object storage (or a worker queue) so Gunicorn does not hold ~2× file RAM and can restore Range / `X-Accel-Redirect`.
2. **Streaming merge** — pypdf cannot; pikepdf/qpdf might, at the cost of a native dependency.
3. **Remove Vite DEBUG `unsafe-inline`/`unsafe-eval`** — only needed for HMR; production Django policy already omits them. Confirm a `FRONTEND_DIST` Docker smoke with the strict policy (hashed `index.html` scripts only).
4. **Admin CSP** — eliminate changelist `<style>` and `mark_safe(..., style=)` so `/admin/` can share `style-src 'self'`.
5. **Self-host fonts** — drop Google Fonts from CSP.
6. **Upgrade pip-tools** so `pip-compile --generate-hashes` works on pip 26; recompile the whole lockfile instead of hand-inserting `pypdf==6.14.2`.
7. **Visible overlay UX** — Helvetica cannot render non-Latin emails; consider Noto (already used by `pdf_service.py`) if purchaser emails may be non-ASCII.
8. **Do not over-claim DRM** — still no encryption; full `body` JSON on the reader manifest remains an exfil path for entitled users (`PROJECT_ANALYSIS.md`).

---

*End of security-hardening pass report.*
