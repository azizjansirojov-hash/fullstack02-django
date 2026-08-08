# FOLLOWUP.md — technical debt & roadmap

Living list of deferred work. Seeded from `PROJECT_OVERVIEW.md` Appendix B and Known Issues, **excluding payment/checkout implementation** (commerce remains admin-marked purchases only — out of scope for the current remediation pass).

## Still open (non-payment)

- Second TTS provider behind `TTS_PROVIDER` before treating edge-tts as a production SLA (see `ARCHITECTURE.md`).
- Keep Django legal-page static assets in sync with SPA branding, or intentionally slim further after confirming no template references remain.
- Act on dependency audit findings (PR CI blocks high/critical; weekly workflow remains advisory) — see README / DEPLOY policy once landed.
- Notification preferences + push/email.
- Continue converting residual `.jsx` under `frontend/src` to TypeScript.
- Real multi-locale catalog copy (if ever needed beyond Uzbek); keep `LANGUAGE_CODE = 'uz'` until then.
- Roles: Django staff/superuser only — no custom reader/publisher roles (product decision pending).

## Explicitly deferred / out of this pass

- **Payment gateway / checkout / Purchase creation flows** — purchases stay admin-marked (`Purchase.status = paid`). Do not implement checkout in remediation workstreams that exclude commerce.

## Recently completed (prior remediation)

- JWT-only auth (SPA + gated media); Django HTML auth templates removed
- Real `Notification` model + `/api/notifications/` + sidebar wiring
- `Review` registered in Django admin for moderation
- Bridge parity scripts and unused `book-detail-enhancements.js` deleted
- Compose/docs Postgres defaults renamed `luma` → `libro` (see DEPLOY.md rename script)
- Reader HTML-fallback flags/comments removed

## i18n

Locale infrastructure is ready (`frontend/src/lib/locale.ts`); UI strings remain Uzbek-hardcoded.
